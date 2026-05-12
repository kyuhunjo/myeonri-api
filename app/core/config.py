from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


class Settings:
    # MySQL
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "mysql-service.default.svc.cluster.local")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "appuser")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "apppassword")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "appdb")

    # CORS
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS",
        "https://imjoe24.com,https://myeonri.imjoe24.com,http://localhost:5173",
    ).split(",")

    # Groq
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    # Server
    APP_NAME: str = "Myeonri API"
    APP_VERSION: str = "2.0.0"

    # API Key Authentication
    API_KEY: str = os.getenv("API_KEY", "")

    # Logging
    LOG_TAIL_DEFAULT: int = int(os.getenv("LOG_TAIL_DEFAULT", "100"))
    LOG_TAIL_MAX: int = int(os.getenv("LOG_TAIL_MAX", "1000"))

    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv(
        "GOOGLE_REDIRECT_URI",
        "https://api.imjoe24.com/auth/google/callback",
    )

    # JWT for frontend token
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 1

    # Frontend URL
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "https://imjoe24.com")


settings = Settings()
