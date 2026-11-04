from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _encode_database_url(value: str) -> str:
    """Support passwords with #/? and force the asyncpg driver."""
    if "://" not in value:
        return value
    prefix, rest = value.split("://", 1)
    if "@" not in rest:
        driver = "postgresql+asyncpg" if prefix in {"postgresql", "postgres"} else prefix
        return f"{driver}://{rest}"
    creds, hostpart = rest.rsplit("@", 1)
    if ":" not in creds:
        user, password = creds, ""
    else:
        user, password = creds.split(":", 1)
    driver = "postgresql+asyncpg" if prefix in {"postgresql", "postgres", "postgresql+asyncpg"} else prefix
    if driver == "postgresql":
        driver = "postgresql+asyncpg"
    return f"{driver}://{quote_plus(user)}:{quote_plus(password)}@{hostpart}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["local", "production"] = "local"
    log_level: str = "INFO"
    database_url: str
    clerk_secret_key: str
    cors_allowed_origins: str = "http://localhost:5173"
    demo_as_of_date: str = "2026-11-04"

    @field_validator("database_url")
    @classmethod
    def use_asyncpg_driver(cls, value: str) -> str:
        return _encode_database_url(value)

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
