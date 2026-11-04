from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.errors import AuthMissingError
from app.core.security import (
    ROLE_SALES_REP,
    ClerkClient,
    ClerkUserProfile,
    CurrentUser,
    resolve_current_user,
)
from app.repositories.app_users import AppUserRepository

bearer_scheme = HTTPBearer(auto_error=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CurrentUser:
    if credentials is None or not credentials.credentials.strip():
        raise AuthMissingError()
    client: ClerkClient = request.app.state.clerk_client
    clerk_user_id = await run_in_threadpool(
        client.verify_session_token, credentials.credentials
    )
    users = AppUserRepository(session)

    # Fast path: known user — skip Clerk Users API (was making search feel stuck)
    existing = await users.get_by_clerk_user_id(clerk_user_id)
    if existing is not None:
        now = datetime.now(timezone.utc)
        if existing.last_seen_at is None or (now - existing.last_seen_at).total_seconds() >= 60:
            existing.last_seen_at = now
            await session.commit()
        return CurrentUser(
            user_id=existing.id,
            clerk_user_id=existing.clerk_user_id,
            email=existing.email,
            role=existing.role or ROLE_SALES_REP,
        )

    profile = await run_in_threadpool(client.fetch_user_profile, clerk_user_id)
    return await resolve_current_user(clerk_user_id, profile, users, session)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
