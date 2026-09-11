from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://tracker:tracker@localhost:5433/tracker"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cors_origins: list[str] = ["http://localhost:5173"]

    # Base URL of the SPA, used to build the invitation accept link.
    frontend_base_url: str = "http://localhost:5173"
    invite_expiry_days: int = 7

    # SendGrid API key for real invitation email delivery. Unset by default —
    # local dev and tests run with no key, which skips sending entirely and
    # falls back to the accept_url returned in the API response.
    sendgrid_api_key: str | None = None
    # Must be a sender SendGrid has verified for this account (Settings ->
    # Sender Authentication -> Single Sender Verification) — SendGrid rejects
    # sends from an unverified address regardless of API key validity.
    email_from_address: str = "invites@example.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
