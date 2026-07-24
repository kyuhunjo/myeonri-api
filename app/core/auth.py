"""JWT 검증 + JWKS 캐시 (imjoe24-auth-middleware 기반, 2026-07-24)

**마이그레이션:**
- Before: PyJWT 직접 구현 (150+ 줄)
- After: imjoe24-auth-middleware (30 줄)
- 설치: `pip install git+https://github.com/kyuhunjo/imjoe24-auth-middleware.git@main`
"""
from __future__ import annotations

import logging

from fastapi import Depends

from imjoe24_auth import JWKSManager, create_get_current_user

log = logging.getLogger("myeonri-api.auth")

# ── JWKS 관리자 (전역 단 하나) ──

jwks_manager = JWKSManager(
    jwks_url="https://idp.imjoe24.com/.well-known/jwks.json",
    ttl_sec=600,  # 10 분 캐시
    audience="imjoe24-services",
    issuer="https://idp.imjoe24.com",
)

# ── FastAPI 의존성 주입용 get_current_user ──

get_current_user = create_get_current_user(jwks_manager)

# ── 하위 호환용 export (기존 import 경로 유지) ──

__all__ = ["get_current_user", "jwks_manager"]
