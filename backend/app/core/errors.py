from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"
    message = "Something went wrong on the server."

    def __init__(self, message: str | None = None, details: dict[str, Any] | None = None) -> None:
        self.message = message or type(self).message
        self.details = details or {}
        super().__init__(self.message)


class AuthMissingError(AppError):
    status_code = 401
    code = "AUTH_MISSING"
    message = "Authentication is required."


class AuthInvalidError(AppError):
    status_code = 401
    code = "AUTH_INVALID"
    message = "Authentication failed."


class AuthExpiredError(AppError):
    status_code = 401
    code = "AUTH_EXPIRED"
    message = "Sign in again."


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "The requested item was not found."

    def __init__(self, resource: str, message: str | None = None) -> None:
        super().__init__(message, {"resource": resource})


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_body("VALIDATION_ERROR", "The request is not valid.", {"errors": exc.errors()}),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(status_code=exc.status_code, content=error_body(code, detail))
