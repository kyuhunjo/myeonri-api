from __future__ import annotations

import logging
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

from app.core.config import settings

logger = logging.getLogger("myeonri-api")

router = APIRouter(prefix="/auth", tags=["auth"])

# 간단한 state 저장소 (in-memory, 프로덕션에서는 Redis 권장)
_state_store: dict[str, datetime] = {}


def _clean_expired_states():
    """5분 지난 state 정리"""
    now = datetime.now(timezone.utc)
    expired = [k for k, v in _state_store.items() if now - v > timedelta(minutes=5)]
    for k in expired:
        _state_store.pop(k, None)


@router.get("/google")
async def google_login():
    """구글 OAuth 로그인 페이지로 리디렉트"""
    state = secrets.token_urlsafe(32)
    _state_store[state] = datetime.now(timezone.utc)

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
        "prompt": "consent",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{query}"
    logger.info(f"Google OAuth redirect: state={state[:8]}...")
    return RedirectResponse(url=url, status_code=302)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
):
    """구글 OAuth 콜백 처리"""
    # 에러 처리
    if error:
        logger.warning(f"Google OAuth error: {error}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/?error={error}",
            status_code=302,
        )

    if not code or not state:
        logger.warning("Missing code or state in OAuth callback")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/?error=missing_params",
            status_code=302,
        )

    # state 검증
    if state not in _state_store:
        logger.warning(f"Invalid state: {state[:8]}...")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/?error=invalid_state",
            status_code=302,
        )
    _state_store.pop(state, None)

    try:
        # code → token 교환
        async with httpx.AsyncClient() as client:
            token_res = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            token_data = token_res.json()

            if "error" in token_data:
                logger.error(f"Token exchange failed: {token_data.get('error')}")
                return RedirectResponse(
                    url=f"{settings.FRONTEND_URL}/?error=token_exchange_failed",
                    status_code=302,
                )

            access_token = token_data["access_token"]
            # refresh_token = token_data.get("refresh_token")  # 나중에 필요하면 사용

            # 사용자 정보 조회
            user_res = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_info = user_res.json()

        # 구글 access_token과 user_info를 프론트로 전달
        # (JWT 없이 직접 전달 — 프론트에서 localStorage에 저장)
        redirect_params = urlencode({
            "access_token": access_token,
            "sub": user_info["sub"],
            "name": user_info.get("name", ""),
            "email": user_info.get("email", ""),
            "picture": user_info.get("picture", ""),
        })

        logger.info(f"Google login success: {user_info.get('email')} ({user_info['sub'][:8]}...)")

        # 프론트엔드로 리디렉트
        redirect_url = f"{settings.FRONTEND_URL}/auth/callback?{redirect_params}"
        return RedirectResponse(url=redirect_url, status_code=302)

    except httpx.HTTPError as e:
        logger.error(f"HTTP error during OAuth: {e}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/?error=http_error",
            status_code=302,
        )
    except Exception as e:
        logger.error(f"Unexpected error during OAuth: {e}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/?error=internal_error",
            status_code=302,
        )
