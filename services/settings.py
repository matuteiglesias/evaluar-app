import os


class ConfigurationError(RuntimeError):
    """Raised when runtime configuration is unsafe or incomplete."""


def _boolean(name, default):
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be a boolean")


def _integer(name, default):
    try:
        return int(os.getenv(name) or default)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an integer") from error


def _float(name, default):
    try:
        return float(os.getenv(name) or default)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a number") from error


def runtime_settings(root_path):
    environment = (os.getenv("APP_ENV") or "production").strip().lower()
    if environment not in {"development", "test", "staging", "production"}:
        raise ConfigurationError("APP_ENV must be development, test, staging, or production")
    production_like = environment in {"staging", "production"}
    return {
        "APP_ENV": environment,
        "DEBUG": False,
        "SECRET_KEY": os.getenv("SECRET_KEY"),
        "GOOGLE_CLIENT_ID": os.getenv("GOOGLE_CLIENT_ID"),
        "GOOGLE_CLIENT_SECRET": os.getenv("GOOGLE_CLIENT_SECRET"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "AI_EVALUATION_ENABLED": _boolean("AI_EVALUATION_ENABLED", True),
        "FIREBASE_ENABLED": _boolean("FIREBASE_ENABLED", True),
        "GOOGLE_APPLICATION_CREDENTIALS": os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        "EXERCISES_ROOT": os.getenv("EXERCISES_ROOT") or os.path.join(root_path, "exercises"),
        "SESSION_PERMANENT": False,
        "SESSION_TYPE": os.getenv("SESSION_TYPE") or "filesystem",
        "SESSION_FILE_DIR": os.getenv("SESSION_FILE_DIR") or "/tmp/flask_session",
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": os.getenv("SESSION_COOKIE_SAMESITE") or "Lax",
        "SESSION_COOKIE_SECURE": _boolean("SESSION_COOKIE_SECURE", production_like),
        "MAX_CONTENT_LENGTH": _integer("MAX_CONTENT_LENGTH", 64 * 1024),
        "MAX_ANSWER_LENGTH": _integer("MAX_ANSWER_LENGTH", 8_000),
        "MAX_TEACHER_QUESTION_LENGTH": _integer("MAX_TEACHER_QUESTION_LENGTH", 2_000),
        "MAX_FEEDBACK_LENGTH": _integer("MAX_FEEDBACK_LENGTH", 2_000),
        "RATELIMIT_STORAGE_URI": os.getenv("RATELIMIT_STORAGE_URI") or "memory://",
        "LOGIN_RATE_LIMIT": os.getenv("LOGIN_RATE_LIMIT") or "10 per minute",
        "ANSWER_RATE_LIMIT": os.getenv("ANSWER_RATE_LIMIT") or "5 per minute",
        "FEEDBACK_RATE_LIMIT": os.getenv("FEEDBACK_RATE_LIMIT") or "10 per minute",
        "TEACHER_HELP_RATE_LIMIT": os.getenv("TEACHER_HELP_RATE_LIMIT") or "5 per minute",
        "HTTP_CONNECT_TIMEOUT": _float("HTTP_CONNECT_TIMEOUT", 3.05),
        "HTTP_READ_TIMEOUT": _float("HTTP_READ_TIMEOUT", 10),
    }


def validate_settings(config):
    if config.get("TESTING"):
        return
    missing = []
    secret = config.get("SECRET_KEY") or ""
    if (
        len(secret) < 32
        or len(set(secret)) < 12
        or secret.lower() in {"your_secret_key", "change-me"}
    ):
        missing.append("SECRET_KEY (at least 32 high-entropy, non-placeholder characters)")
    if config.get("APP_ENV") in {"staging", "production"}:
        if not config.get("GOOGLE_CLIENT_ID"):
            missing.append("GOOGLE_CLIENT_ID")
        if not config.get("GOOGLE_CLIENT_SECRET"):
            missing.append("GOOGLE_CLIENT_SECRET")
        if config.get("AI_EVALUATION_ENABLED") and not config.get("OPENAI_API_KEY"):
            missing.append("OPENAI_API_KEY (required while AI_EVALUATION_ENABLED=true)")
        if not config.get("SESSION_COOKIE_SECURE"):
            missing.append("SESSION_COOKIE_SECURE=true")
    if config.get("SESSION_COOKIE_SAMESITE") not in {"Lax", "Strict", "None"}:
        missing.append("SESSION_COOKIE_SAMESITE (Lax, Strict, or None)")
    if missing:
        raise ConfigurationError("Invalid runtime configuration: " + ", ".join(missing))
