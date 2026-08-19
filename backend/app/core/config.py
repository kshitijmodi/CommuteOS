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

    # Phase 3 LLM phrasing (see llm_phrasing.py/chat_ai.py). None until set
    # via .env - phrasing falls back to a deterministic template when
    # unset, so the rest of the app works without this configured.
    #
    # Switched from Groq (llama-3.1-8b-instant) to the real Anthropic API
    # 2026-08-19 - llama-3.1-8b-instant was found to be fully decommissioned
    # (a direct call to Groq's API returned "model_not_found"), which had
    # been silently invisible because every LLM call here already falls
    # back to a deterministic template on any failure - every phrased
    # answer had quietly been template-only for at least ~2.5 weeks (the
    # default hadn't been touched since 2026-07-31) with no visible error
    # anywhere. This is a real Anthropic API key (console.anthropic.com,
    # billed per-token) - NOT the same credential as a claude.ai Pro/Team
    # subscription login, which has no supported way to authenticate
    # server-side backend calls at all.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"

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
