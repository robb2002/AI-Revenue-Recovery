"""Clerk session verification — same pattern as Sales Intelligence, single role SALES_REP."""

from __future__ import annotations

import json
import logging
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from threading import Lock

import jwt
from jwt import PyJWKClient
from jwt.exceptions import ExpiredSignatureError, PyJWKClientConnectionError, PyJWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthExpiredError, AuthInvalidError
from app.repositories.app_users import AppUserRepository

logger = logging.getLogger(__name__)

CLERK_USERS_URL = "https://api.clerk.com/v1/users"
ROLE_SALES_REP = "SALES_REP"
_PROFILE_CACHE_TTL_SECONDS = 300.0
_JWKS_TIMEOUT_SECONDS = 4


@dataclass(frozen=True)
class CurrentUser:
    user_id: uuid.UUID
    clerk_user_id: str
    email: str
    role: str


@dataclass(frozen=True)
class ClerkUserProfile:
    clerk_user_id: str
    email: str


class ClerkClient:
    def __init__(self, secret_key: str, authorized_parties: list[str]) -> None:
        self._secret_key = secret_key
        self._authorized_parties = frozenset(authorized_parties)
        self._profile_cache: dict[str, tuple[float, ClerkUserProfile]] = {}
        self._profile_lock = Lock()
        self._jwks_clients: dict[str, PyJWKClient] = {}
        self._jwks_lock = Lock()

    def _jwks_for_token(self, token: str) -> PyJWKClient:
        """Use the token issuer's JWKS (Clerk Frontend API) — faster/more reliable than api.clerk.com."""
        try:
            unverified = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": False},
                algorithms=["RS256"],
            )
        except PyJWTError as exc:
            raise AuthInvalidError() from exc
        iss = str(unverified.get("iss") or "").rstrip("/")
        if not iss.startswith("https://"):
            raise AuthInvalidError()
        jwks_url = f"{iss}/.well-known/jwks.json"
        with self._jwks_lock:
            client = self._jwks_clients.get(jwks_url)
            if client is None:
                client = PyJWKClient(
                    jwks_url,
                    headers={"User-Agent": "ai-revenue-recovery-backend"},
                    lifespan=3600,
                    timeout=_JWKS_TIMEOUT_SECONDS,
                )
                self._jwks_clients[jwks_url] = client
            return client

    def verify_session_token(self, token: str) -> str:
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                jwks = self._jwks_for_token(token)
                signing_key = jwks.get_signing_key_from_jwt(token)
                claims = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256"],
                    options={"require": ["exp", "sub"]},
                    leeway=5,
                )
                authorized_party = claims.get("azp")
                if authorized_party and authorized_party not in self._authorized_parties:
                    raise AuthInvalidError()
                return str(claims["sub"])
            except ExpiredSignatureError as exc:
                raise AuthExpiredError() from exc
            except AuthInvalidError:
                raise
            except PyJWKClientConnectionError as exc:
                last_exc = exc
                logger.error(
                    "Could not fetch Clerk signing keys (attempt %s): %s",
                    attempt + 1,
                    type(exc).__name__,
                )
                time.sleep(0.25)
            except PyJWTError as exc:
                raise AuthInvalidError() from exc
        logger.error("Clerk JWKS failed after retry: %s", type(last_exc).__name__ if last_exc else "?")
        raise AuthInvalidError() from last_exc

    def fetch_user_profile(self, clerk_user_id: str) -> ClerkUserProfile:
        now = time.monotonic()
        with self._profile_lock:
            cached = self._profile_cache.get(clerk_user_id)
            if cached is not None and cached[0] > now:
                return cached[1]

        profile = self._fetch_user_profile_uncached(clerk_user_id)
        with self._profile_lock:
            self._profile_cache[clerk_user_id] = (now + _PROFILE_CACHE_TTL_SECONDS, profile)
        return profile

    def _fetch_user_profile_uncached(self, clerk_user_id: str) -> ClerkUserProfile:
        request = urllib.request.Request(
            f"{CLERK_USERS_URL}/{urllib.parse.quote(clerk_user_id, safe='')}",
            headers={
                "Authorization": f"Bearer {self._secret_key}",
                "User-Agent": "ai-revenue-recovery-backend",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.error("Clerk user fetch failed: %s", type(exc).__name__)
            raise AuthInvalidError() from exc

        return ClerkUserProfile(clerk_user_id=clerk_user_id, email=_primary_email(payload))


def _primary_email(payload: dict) -> str:
    addresses = payload.get("email_addresses") or []
    primary_id = payload.get("primary_email_address_id")
    for address in addresses:
        if address.get("id") == primary_id and address.get("email_address"):
            return str(address["email_address"])
    for address in addresses:
        if address.get("email_address"):
            return str(address["email_address"])
    return ""


async def resolve_current_user(
    clerk_user_id: str,
    profile: ClerkUserProfile,
    users: AppUserRepository,
    session: AsyncSession,
) -> CurrentUser:
    # Single-role MVP: ignore Clerk publicMetadata.role — every signed-in user is SALES_REP.
    email = profile.email or f"{clerk_user_id}@unknown.local"
    user = await users.upsert_from_clerk(clerk_user_id, email, ROLE_SALES_REP)
    await session.commit()
    return CurrentUser(
        user_id=user.id,
        clerk_user_id=user.clerk_user_id,
        email=user.email,
        role=user.role,
    )
