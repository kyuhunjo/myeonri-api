from __future__ import annotations

import logging
import sys
from urllib.parse import unquote

import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api import saju, user, consult, consult_analyze, consult_landing, calendar, logs, rbac, auth_google, daily, compatibility, profile, influence, mbti, personality, diary, stats, weather, culture
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

# API Key Authentication (하위 호환 + 내부용)
app.add_middleware(APIKeyMiddleware)

# Routers
app.include_router(auth_google.router)  # Phase 3에서 폐지 예정
app.include_router(saju.router)
app.include_router(user.router)
app.include_router(consult.router)
app.include_router(consult_analyze.router)
app.include_router(consult_landing.router)
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
app.include_router(weather.router)
app.include_router(culture.router)


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

    path = request.url.path
    method = request.method

    response = await call_next(request)

    duration_ms = int((time.time() - start) * 1000)

    # 정적 파일, 헬스체크, docs 등은 기록하지 않음
    if path.startswith("/docs") or path.startswith("/openapi.json") or path.startswith("/redoc") or path == "/health":
        return response

    try:
        # 진짜 클라이언트 IP 추출 (X-Forwarded-For 우선, Traefik 거쳐서 직접 못 받음)
        xff = request.headers.get("x-forwarded-for", "")
        real_ip = request.headers.get("x-real-ip", "")
        cf_ip = request.headers.get("cf-connecting-ip", "")  # Cloudflare
        if cf_ip:
            ip = cf_ip
        elif xff:
            # XFF: "client, proxy1, proxy2" → 첫 번째가 진짜 클라이언트
            ip = xff.split(",")[0].strip()
        elif real_ip:
            ip = real_ip
        else:
            ip = request.client.host if request.client else None

        # 사용자 식별: x-user-id 헤더 (FE가 Authorization Bearer에서 추출해서 전달)
        # → portal-idp의 sub (portal UUID)
        user_id = (
            request.headers.get("x-user-id")
            or request.headers.get("x-google-id")  # 하위 호환
            or request.query_params.get("google_id")
            or request.query_params.get("admin_id")
        )
        if not user_id:
            # 쿠키에서 세션 키로 user_id 추출
            cookie_header = request.headers.get("cookie", "")
            for session_key in ("myeonri_pc_session", "myeonri_mobile_session"):
                marker = f"{session_key}="
                if marker in cookie_header:
                    try:
                        after = cookie_header.split(marker, 1)[1]
                        raw = after.split(";", 1)[0].strip()
                        decoded = unquote(raw)
                        m = re.search(r'"(google_?id|user_id|sub)"\s*:\s*"([^"]+)"', decoded, re.IGNORECASE)
                        if m:
                            user_id = m.group(2)
                            break
                        if decoded and decoded != "null":
                            user_id = decoded.strip('"')
                            break
                    except Exception:
                        pass

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
                    (user_id, ip, method, path, status, user_agent, referer, duration_ms),
                )
    except Exception as e:
        logger.warning(f"Failed to log access: {e}")

    return response


@app.get("/health")
async def health():
    logger.info("Health check called")
    return {"status": "ok", "version": settings.APP_VERSION}
