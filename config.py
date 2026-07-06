import os


APP_ENV = os.getenv("APP_ENV", "development")
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "dev-change-me")
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "lecture_notes_session")
CSRF_COOKIE_NAME = os.getenv("CSRF_COOKIE_NAME", "lecture_notes_csrf")
SESSION_DAYS = int(os.getenv("SESSION_DAYS", "30"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "500"))
RATE_LIMIT_AUTH_PER_MINUTE = int(os.getenv("RATE_LIMIT_AUTH_PER_MINUTE", "10"))
RATE_LIMIT_AI_PER_MINUTE = int(os.getenv("RATE_LIMIT_AI_PER_MINUTE", "20"))
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ALLOW_DEV_PASSWORD_RESET = os.getenv("ALLOW_DEV_PASSWORD_RESET", "true").lower() in {"1", "true", "yes"}
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/notes.db")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")


def require_production_secret() -> None:
    if APP_ENV == "production" and APP_SECRET_KEY == "dev-change-me":
        raise RuntimeError("APP_SECRET_KEY must be set in production")
