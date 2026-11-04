import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import protected_router, public_router
from app.core.config import Settings, get_settings
from app.core.database import create_engine, create_session_factory
from app.core.errors import AppError, error_body, register_exception_handlers
from app.core.logging import configure_logging, request_id_var
from app.core.security import ClerkClient

logger = logging.getLogger("app")


async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = uuid.uuid4().hex
    token = request_id_var.set(request_id)
    started = time.perf_counter()
    try:
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled error")
            response = JSONResponse(
                status_code=500,
                content=error_body("INTERNAL_ERROR", AppError.message),
            )
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s -> %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        return response
    finally:
        request_id_var.reset(token)


def create_app(settings: Settings | None = None) -> FastAPI:
    # Load .env from backend/ or repo root when running uvicorn from backend/
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    engine = create_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("API starting (env=%s)", settings.app_env)
        # Warm Signal Scout tables so first search is not a long migration
        try:
            from app.services.f7_signal_scout import ensure_f7_tables

            async with app.state.session_factory() as session:
                await ensure_f7_tables(session)
            logger.info("Signal Scout tables ready")
        except Exception:
            logger.exception("Signal Scout table warm-up skipped")
        yield
        await engine.dispose()

    app = FastAPI(title="AI Revenue Recovery API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.clerk_client = ClerkClient(settings.clerk_secret_key, settings.cors_origins)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(request_context)
    register_exception_handlers(app)

    app.include_router(public_router)
    app.include_router(protected_router)
    return app


app = create_app()
