from __future__ import annotations

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings

# 인증이 필요 없는 경로
PUBLIC_PATHS = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
}


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # CORS preflight는 항상 통과
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
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized: invalid or missing API key"},
            )

        return await call_next(request)
