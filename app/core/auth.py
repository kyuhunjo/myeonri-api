"""JWT 검증 + API 키 미들웨어 (imjoe24-auth-middleware 기반, 2026-07-24)

**기능:**
1. APIKeyMiddleware: 레거시 API 키 인증 (하위 호환)
2. get_current_user: portal-idp JWT 검증 (새 방식)

**사용법:**
```python
# API 키 인증 (레거시)
app.add_middleware(APIKeyMiddleware)

# JWT 인증 (새 방식)
@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user
```
"""
from __future__ import annotations

import logging

from fastapi import Depends, Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from imjoe24_auth import JWKSManager, create_get_current_user

from app.core.config import settings

log = logging.getLogger("myeonri-api.auth")

# ── API 키 미들웨어 (레거시, 하위 호환) ──

# 인증이 필요 없는 경로
PUBLIC_PATHS = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/auth/google",
    "/auth/google/callback",
    "/weather/current",
    "/weather/forecast",
    "/weather/sunrise",
    "/weather/air-quality",
    "/stats/pageview",
    "/stats/session-end",
    "/consult/landing-intro/stream",
    "/consult/landing-culture/stream",
    "/culture/station-spaces",
    "/calendar/month",
}


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # CORS preflight 는 항상 통과
        if request.method == "OPTIONS":
            return await call_next(request)

        # Swagger UI 관련 정적 파일은 통과
        if path.startswith("/docs") or path.startswith("/openapi.json") or path.startswith("/redoc"):
            return await call_next(request)

        # 공개 경로는 통과
        if path in PUBLIC_PATHS:
            return await call_next(request)

        # API 키 검증
        api_key = request.headers.get("x-api-key", "")
        if not api_key or api_key != settings.API_KEY:
            origin = request.headers.get("origin", "")
            resp = JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized: invalid or missing API key"},
                headers={
                    "Access-Control-Allow-Origin": origin or "*",
                    "Access-Control-Allow-Credentials": "true",
                } if origin else {},
            )
            return resp

        return await call_next(request)


# ── JWT 검증 (portal-idp 기반) ──

jwks_manager = JWKSManager(
    jwks_url=settings.JWKS_URL,
    ttl_sec=600,  # 10 분 캐시
    audience=settings.AUTH_AUDIENCE,  # env JWT_AUDIENCE 에서 읽음 (콤마 구분 여러 값 가능)
    issuer=settings.AUTH_ISSUER,
)

get_current_user = create_get_current_user(jwks_manager)

# ── export ──

__all__ = ["APIKeyMiddleware", "get_current_user", "jwks_manager"]
