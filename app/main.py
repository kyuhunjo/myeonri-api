from __future__ import annotations

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import saju, user, consult, calendar, logs, rbac, auth_google, daily, compatibility, profile, history
from app.core.config import settings
from app.core.database import get_pool, close_pool
from app.core.auth import APIKeyMiddleware
from app.utils.constants import load_heavenly_stems, load_earthly_branches

# 파일 로깅 설정
LOG_FILE = "/var/log/myeonri/api.log"
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)s %(name)s: %(message)s"
))
logging.getLogger().addHandler(file_handler)
logging.getLogger().setLevel(logging.INFO)

# uvicorn access log도 파일로
uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.addHandler(file_handler)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
)

# 애플리케이션 로거
logger = logging.getLogger("myeonri-api")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key Authentication
app.add_middleware(APIKeyMiddleware)

# Routers
app.include_router(auth_google.router)
app.include_router(saju.router)
app.include_router(user.router)
app.include_router(consult.router)
app.include_router(daily.router)
app.include_router(compatibility.router)
app.include_router(profile.router)
app.include_router(history.router)
app.include_router(calendar.router)
app.include_router(logs.router)
app.include_router(rbac.router)


@app.on_event("startup")
async def startup():
    """앱 시작 시 천간/지지 데이터 DB 로드"""
    try:
        await load_heavenly_stems()
        await load_earthly_branches()
        logger.info("Constants loaded from DB on startup")
    except Exception as e:
        logger.warning(f"Failed to load constants from DB: {e}")


@app.on_event("shutdown")
async def shutdown():
    await close_pool()


@app.get("/health")
async def health():
    logger.info("Health check called")
    return {"status": "ok", "version": settings.APP_VERSION}
