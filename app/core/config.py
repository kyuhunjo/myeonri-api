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
        "https://myeonri.imjoe24.com,http://localhost:5173",
    ).split(",")

    # Groq
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # Server
    APP_NAME: str = "Myeonri API"
    APP_VERSION: str = "2.0.0"


settings = Settings()
