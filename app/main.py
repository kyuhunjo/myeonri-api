from __future__ import annotations

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import saju, user, consult, calendar, logs, rbac, auth_google
from app.core.config import settings
from app.core.database import close_pool
from app.core.auth import APIKeyMiddleware

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
app.include_router(calendar.router)
app.include_router(logs.router)
app.include_router(rbac.router)


@app.on_event("shutdown")
async def shutdown():
    await close_pool()


@app.get("/health")
async def health():
    logger.info("Health check called")
    return {"status": "ok", "version": settings.APP_VERSION}
