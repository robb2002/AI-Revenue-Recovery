import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Text, Uuid, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.repositories.base import Base


class AppUser(Base):
    __tablename__ = "app_users"
    __table_args__ = {"schema": "revenue_recovery"}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    clerk_user_id: Mapped[str] = mapped_column(Text, unique=True)
    email: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, server_default="SALES_REP")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AppUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_clerk_user_id(self, clerk_user_id: str) -> AppUser | None:
        return await self._session.scalar(
            select(AppUser).where(AppUser.clerk_user_id == clerk_user_id)
        )

    async def upsert_from_clerk(self, clerk_user_id: str, email: str, role: str) -> AppUser:
        user = await self.get_by_clerk_user_id(clerk_user_id)
        now = datetime.now(timezone.utc)
        if user is None:
            user = AppUser(
                clerk_user_id=clerk_user_id,
                email=email,
                role=role,
                last_seen_at=now,
            )
            self._session.add(user)
        else:
            user.email = email
            user.role = role
            # Throttle last_seen writes (~1/min) — AUTHENTICATION.md
            if user.last_seen_at is None or (now - user.last_seen_at).total_seconds() >= 60:
                user.last_seen_at = now
            user.updated_at = now
        await self._session.flush()
        return user
