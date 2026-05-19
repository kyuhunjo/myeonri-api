from __future__ import annotations

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import time

from starlette.middleware.base import BaseHTTPMiddleware

from app.api import saju, user, consult, calendar, logs, rbac, auth_google, daily, compatibility, profile, influence, mbti, personality, diary, stats
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
app.include_router(influence.router)
app.include_router(mbti.router)
app.include_router(personality.router)
app.include_router(profile.router)
app.include_router(calendar.router)
app.include_router(logs.router)
app.include_router(rbac.router)
app.include_router(diary.router)
app.include_router(stats.router)


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


# 접속 로깅 미들웨어
@app.middleware("http")
async def log_access(request: Request, call_next):
    """모든 API 요청을 access_logs 테이블에 기록"""
    start = time.time()

    # 응답 처리 전에 요청 정보 읽기 (본문은 스트림이라 미리 읽지 않음)
    path = request.url.path
    method = request.method

    response = await call_next(request)

    duration_ms = int((time.time() - start) * 1000)

    # 정적 파일, 헬스체크, docs 등은 기록하지 않음
    if path.startswith("/docs") or path.startswith("/openapi.json") or path.startswith("/redoc") or path == "/health":
        return response

    try:
        # google_id 추출 (헤더나 쿼리 파라미터에서)
        google_id = request.headers.get("x-google-id") or request.query_params.get("google_id") or request.query_params.get("admin_id")

        ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")[:500]
        referer = request.headers.get("referer", "")[:500]
        status = response.status_code

        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """INSERT INTO access_logs
                       (google_id, ip, method, path, status, user_agent, referer, duration_ms)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (google_id, ip, method, path, status, user_agent, referer, duration_ms),
                )
    except Exception as e:
        logger.warning(f"Failed to log access: {e}")

    return response


@app.get("/health")
async def health():
    logger.info("Health check called")
    return {"status": "ok", "version": settings.APP_VERSION}
