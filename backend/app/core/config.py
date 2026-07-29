from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loaded from environment variables / a .env file (not committed —
    see .env.example for the shape). Never hardcode secrets here."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://commuteos:commuteos@localhost:5432/commuteos"

    # Signing key for JWT access tokens. Must be overridden via env var
    # outside local dev - this default is intentionally not secret.
    secret_key: str = "dev-only-insecure-secret-change-me"
    access_token_expire_minutes: int = 60 * 24 * 7  # 1 week


settings = Settings()
