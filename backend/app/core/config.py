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

    # Phase 3 LLM phrasing (see llm_phrasing.py). None until set via .env -
    # phrasing falls back to a deterministic template when unset, so the
    # rest of the app works without this configured.
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"

    # NJ Transit developer account - pending approval, see
    # app/transit/njt.py and OPEN_QUESTIONS.md. Unused until implemented.
    njt_username: str | None = None
    njt_password: str | None = None


settings = Settings()
