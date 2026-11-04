import logging

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger("app.database")

POOL_SIZE = 2


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        pool_size=POOL_SIZE,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={
            # extensions = pgvector operators/types on Supabase
            "server_settings": {"search_path": "revenue_recovery,extensions,public"}
        },
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
