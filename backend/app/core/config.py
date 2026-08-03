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

    # NJ Transit developer account - approved 2026-08-01, see
    # app/transit/njt_rail.py and OPEN_QUESTIONS.md.
    njt_username: str | None = None
    njt_password: str | None = None

    # Firebase service account credentials (JSON), for sending real push
    # notifications - see app/notify_service.py. The whole service account
    # key file's contents as a single-line JSON string, never committed -
    # same secret-handling pattern as GROQ_API_KEY/NJT_*. None until set,
    # in which case send_push logs instead of sending (see that module).
    firebase_credentials_json: str | None = None

    # Shared secret for POST /internal/run-commute-job (see
    # routers/internal.py) - the external GitHub Actions cron trigger
    # authenticates with this instead of a per-user JWT, since it isn't
    # acting on behalf of any one user. None disables the endpoint
    # entirely (returns 503) rather than accepting an unauthenticated
    # call to a job that sends real push notifications to every user.
    internal_job_secret: str | None = None


settings = Settings()
