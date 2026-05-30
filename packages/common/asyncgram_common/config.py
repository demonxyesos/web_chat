import os


def env_str(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def cors_origins() -> list[str]:
    raw = env_str("CORS_ORIGINS")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]


JWT_SECRET = env_str("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(env_str("ACCESS_TOKEN_EXPIRE_MINUTES", "60") or "60")
REDIS_URL = env_str("REDIS_URL", "redis://127.0.0.1:6379/0")
DATABASE_URL = env_str("DATABASE_URL", "sqlite:///./database.db")

AUTH_SERVICE_URL = env_str("AUTH_SERVICE_URL", "http://127.0.0.1:8001")
CHAT_SERVICE_URL = env_str("CHAT_SERVICE_URL", "http://127.0.0.1:8002")
