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
        "https://imjoe24.com,https://m.imjoe24.com,https://myeonri.imjoe24.com,https://mmyeonri.imjoe24.com,http://localhost:5173",
    ).split(",")

    # Groq
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    # Server
    APP_NAME: str = "Myeonri API"
    APP_VERSION: str = "2.0.0"

    # ── portal-idp JWT 검증 (2026-07-20 추가) ──
    # API_KEY는 하위 호환용으로만 유지 (FE는 Bearer JWT 사용)
    API_KEY: str = os.getenv("API_KEY", "")

    # portal-idp IdP 설정
    JWKS_URL: str = os.getenv(
        "JWKS_URL",
        "https://idp.imjoe24.com/.well-known/jwks.json",
    )
    AUTH_ISSUER: str = os.getenv("AUTH_ISSUER", "https://idp.imjoe24.com")
    # audience: 콤마 구분 여러 값 허용 ("imjoe24-services,external-partners")
    AUTH_AUDIENCE: str | list[str] | None = os.getenv("JWT_AUDIENCE", "imjoe24-services")
    if AUTH_AUDIENCE and isinstance(AUTH_AUDIENCE, str) and "," in AUTH_AUDIENCE:
        AUTH_AUDIENCE = [a.strip() for a in AUTH_AUDIENCE.split(",")]

    # Logging
    LOG_TAIL_DEFAULT: int = int(os.getenv("LOG_TAIL_DEFAULT", "100"))
    LOG_TAIL_MAX: int = int(os.getenv("LOG_TAIL_MAX", "1000"))

    # ── Google OAuth (폐지 예정 — 2026-07-20부터 auth_google.py는 미사용) ──
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv(
        "GOOGLE_REDIRECT_URI",
        "https://api.myeonri.imjoe24.com/auth/google/callback",
    )

    # JWT (이전 HS256 토큰용 — 이제 portal-idp RS256 JWT 사용)
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 1

    # Frontend URL
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "https://myeonri.imjoe24.com")

    # Weather / Sunrise APIs
    OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")
    SUNRISE_API_KEY: str = os.getenv("SUNRISE_API_KEY", "")


settings = Settings()
