"""
접속 통계 API (고도화)
- access_logs 테이블 기반 통계 조회
- 프론트엔드 페이지 뷰 수집
- 관리자 전용 통계 대시보드
"""

from __future__ import annotations
import logging
import uuid

from fastapi import APIRouter, Query, HTTPException, Request
from pydantic import BaseModel
from app.core.database import get_pool

logger = logging.getLogger("myeonri-api")
router = APIRouter(prefix="/stats", tags=["통계"])


async def _check_admin(google_id: str):
    """관리자 권한 확인"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT role FROM users WHERE google_id = %s LIMIT 1",
                (google_id,),
            )
            row = await cur.fetchone()
    if not row or row[0] != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: admin only")


# ── 프론트엔드 페이지 뷰 수집 ──

class PageViewRequest(BaseModel):
    google_id: str | None = None
    path: str
    page_title: str | None = None
    feature: str | None = None  # 'daily', 'compatibility', 'analysis', 'diary', 'mbti', 'personality', 'influence', 'main', 'my', etc.
    session_id: str | None = None
    referer: str | None = None
    duration_ms: int = 0


@router.post("/pageview")
async def track_pageview(req: PageViewRequest, request: Request):
    """프론트엔드에서 페이지 뷰 전송 (SPA 라우팅 추적용)"""
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")[:500]
    session_id = req.session_id or str(uuid.uuid4())[:16]

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO access_logs
                   (google_id, ip, method, path, page_title, feature, session_id,
                    status, user_agent, referer, duration_ms)
                   VALUES (%s, %s, 'PAGEVIEW', %s, %s, %s, %s,
                           200, %s, %s, %s)""",
                (
                    req.google_id, ip, req.path, req.page_title, req.feature, session_id,
                    user_agent, req.referer or "", req.duration_ms,
                ),
            )
    return {"ok": True}


# ── 페이지 이탈/세션 종료 ──

class SessionEndRequest(BaseModel):
    session_id: str


@router.post("/session-end")
async def track_session_end(req: SessionEndRequest):
    """세션 종료 시 체류 시간 업데이트"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE access_logs SET duration_ms = TIMESTAMPDIFF(MICROSECOND, created_at, NOW()) / 1000 WHERE session_id = %s AND method = 'PAGEVIEW'",
                (req.session_id,),
            )
    return {"ok": True}


# ── 요약 통계 ──

@router.get("/summary")
async def get_stats_summary(
    admin_id: str = Query(description="관리자 google_id"),
):
    """접속 통계 요약 — DAU, WAU, 기능별 사용량 등"""
    await _check_admin(admin_id)
    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # 전체 PV
            await cur.execute("SELECT COUNT(*) FROM access_logs WHERE method IN ('PAGEVIEW', 'GET', 'POST')")
            total_pv = (await cur.fetchone())[0]

            # 오늘 PV
            await cur.execute("SELECT COUNT(*) FROM access_logs WHERE DATE(created_at) = CURDATE() AND method IN ('PAGEVIEW', 'GET', 'POST')")
            today_pv = (await cur.fetchone())[0]

            # 오늘 방문자 (DAU)
            await cur.execute("SELECT COUNT(DISTINCT google_id) FROM access_logs WHERE DATE(created_at) = CURDATE() AND google_id IS NOT NULL")
            today_dau = (await cur.fetchone())[0]

            # 어제 방문자
            await cur.execute("SELECT COUNT(DISTINCT google_id) FROM access_logs WHERE DATE(created_at) = DATE_SUB(CURDATE(), INTERVAL 1 DAY) AND google_id IS NOT NULL")
            yesterday_dau = (await cur.fetchone())[0]

            # 주간 방문자 (WAU)
            await cur.execute("SELECT COUNT(DISTINCT google_id) FROM access_logs WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) AND google_id IS NOT NULL")
            weekly_wau = (await cur.fetchone())[0]

            # 월간 방문자 (MAU)
            await cur.execute("SELECT COUNT(DISTINCT google_id) FROM access_logs WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) AND google_id IS NOT NULL")
            monthly_mau = (await cur.fetchone())[0]

            # 전체 회원 수
            await cur.execute("SELECT COUNT(*) FROM users")
            total_registered = (await cur.fetchone())[0]

            # 오늘 가입자
            await cur.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) = CURDATE()")
            today_registered = (await cur.fetchone())[0]

            # 오늘 새 세션 수
            await cur.execute("SELECT COUNT(DISTINCT session_id) FROM access_logs WHERE DATE(created_at) = CURDATE() AND session_id IS NOT NULL")
            today_sessions = (await cur.fetchone())[0]

            # 기능별 사용량 (오늘) — feature 컬럼 + path에서 추론
            await cur.execute("""
                SELECT
                    CASE
                        WHEN feature IS NOT NULL AND feature != '' THEN feature
                        WHEN path LIKE '%%/daily%' OR path LIKE '%%/today%' THEN 'daily'
                        WHEN path LIKE '%%compatibility%' THEN 'compatibility'
                        WHEN path LIKE '%%/consult%' OR path LIKE '%%/analyze%' THEN 'consult'
                        WHEN path LIKE '%%/diary%' THEN 'diary'
                        WHEN path LIKE '%%/mbti%' THEN 'mbti'
                        WHEN path LIKE '%%/personality%' THEN 'personality'
                        WHEN path LIKE '%%/influence%' THEN 'influence'
                        WHEN path LIKE '%%/saju%' OR path LIKE '%%/calendar%' OR path = '/saju/calculate' THEN 'analysis'
                        WHEN path LIKE '%%/user/%' OR path LIKE '%%/profile%' THEN 'my'
                        WHEN path LIKE '%%/auth/%' THEN 'landing'
                        WHEN path = '/health' THEN 'health'
                        ELSE 'other'
                    END as category,
                    COUNT(*) as cnt
                FROM access_logs
                WHERE DATE(created_at) = CURDATE()
                GROUP BY category
                ORDER BY cnt DESC
            """)
            feature_rows = await cur.fetchall()

            return {
                "total_pv": total_pv,
                "today_pv": today_pv,
                "today_dau": today_dau,
                "yesterday_dau": yesterday_dau,
                "weekly_wau": weekly_wau,
                "monthly_mau": monthly_mau,
                "total_registered": total_registered,
                "today_registered": today_registered,
                "today_sessions": today_sessions,
                "feature_usage": {r[0]: r[1] for r in feature_rows},
            }


# ── 일별 추이 (DAU, PV, 신규가입) ──

@router.get("/daily")
async def get_daily_stats(
    admin_id: str = Query(description="관리자 google_id"),
    days: int = Query(default=30, ge=1, le=365, description="조회할 일 수"),
):
    """일별 방문자/페이지뷰 추이"""
    await _check_admin(admin_id)
    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT
                    DATE(al.created_at) as date,
                    COUNT(*) as visits,
                    COUNT(DISTINCT al.google_id) as unique_users,
                    COUNT(DISTINCT al.session_id) as sessions,
                    (SELECT COUNT(*) FROM users WHERE DATE(created_at) = DATE(al.created_at)) as new_users
                FROM access_logs al
                WHERE al.created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                GROUP BY DATE(al.created_at)
                ORDER BY date DESC
            """, (days,))
            rows = await cur.fetchall()

    return {
        "daily": [
            {
                "date": str(r[0]),
                "pv": r[1],
                "dau": r[2],
                "sessions": r[3],
                "new_users": r[4],
            }
            for r in rows
        ]
    }


# ── 기능별 사용 통계 ──

@router.get("/features")
async def get_feature_stats(
    admin_id: str = Query(description="관리자 google_id"),
    days: int = Query(default=30, ge=1, le=365),
):
    """기능별 사용 통계 (feature 컬럼 기준)"""
    await _check_admin(admin_id)
    pool = await get_pool()

    FEATURE_LABELS = {
        "daily": "오늘의 운세",
        "compatibility": "궁합",
        "analysis": "사주 원국 분석",
        "diary": "사주 일기",
        "mbti": "MBTI",
        "personality": "성향 분석",
        "influence": "영향력 분석",
        "main": "메인",
        "my": "마이페이지",
        "today": "오늘",
        "saju": "사주 입력",
        "other": "기타",
        "landing": "랜딩페이지",
        "consult": "AI 상담",
        "admin": "관리자",
        "health": "상태 확인",
    }

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # 기능별 총 사용량 (feature 컬럼 + path 추론)
            await cur.execute("""
                SELECT
                    CASE
                        WHEN feature IS NOT NULL AND feature != '' THEN feature
                        WHEN path LIKE '%%/daily%' OR path LIKE '%%/today%' THEN 'daily'
                        WHEN path LIKE '%%compatibility%' THEN 'compatibility'
                        WHEN path LIKE '%%/consult%' OR path LIKE '%%/analyze%' THEN 'consult'
                        WHEN path LIKE '%%/diary%' THEN 'diary'
                        WHEN path LIKE '%%/mbti%' THEN 'mbti'
                        WHEN path LIKE '%%/personality%' THEN 'personality'
                        WHEN path LIKE '%%/influence%' THEN 'influence'
                        WHEN path LIKE '%%/saju%' OR path LIKE '%%/calendar%' OR path = '/saju/calculate' THEN 'analysis'
                        WHEN path LIKE '%%/user/%' OR path LIKE '%%/profile%' THEN 'my'
                        WHEN path LIKE '%%/auth/%' THEN 'landing'
                        ELSE 'other'
                    END as category,
                    COUNT(*) as total_views,
                    COUNT(DISTINCT google_id) as total_users
                FROM access_logs
                WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                GROUP BY category
                ORDER BY total_views DESC
            """, (days,))
            rows = await cur.fetchall()

            # 기능별 일별 추이 (최근 7일, path 추론 포함)
            await cur.execute("""
                SELECT
                    DATE(created_at) as date,
                    CASE
                        WHEN feature IS NOT NULL AND feature != '' THEN feature
                        WHEN path LIKE '%%/daily%' OR path LIKE '%%/today%' THEN 'daily'
                        WHEN path LIKE '%%compatibility%' THEN 'compatibility'
                        WHEN path LIKE '%%/consult%' OR path LIKE '%%/analyze%' THEN 'consult'
                        WHEN path LIKE '%%/diary%' THEN 'diary'
                        WHEN path LIKE '%%/mbti%' THEN 'mbti'
                        WHEN path LIKE '%%/personality%' THEN 'personality'
                        WHEN path LIKE '%%/influence%' THEN 'influence'
                        WHEN path LIKE '%%/saju%' OR path LIKE '%%/calendar%' OR path = '/saju/calculate' THEN 'analysis'
                        WHEN path LIKE '%%/user/%' OR path LIKE '%%/profile%' THEN 'my'
                        WHEN path LIKE '%%/auth/%' THEN 'landing'
                        ELSE 'other'
                    END as category,
                    COUNT(*) as cnt
                FROM access_logs
                WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                GROUP BY DATE(created_at), category
                ORDER BY date ASC, cnt DESC
            """)
            trend_rows = await cur.fetchall()

            # 트렌드 데이터 구조화
            trend_data = {}
            for r in trend_rows:
                d = str(r[0])
                if d not in trend_data:
                    trend_data[d] = {}
                trend_data[d][r[1]] = r[2]

    return {
        "features": [
            {
                "feature": r[0],
                "label": FEATURE_LABELS.get(r[0], r[0]),
                "total_views": r[1],
                "total_users": r[2],
            }
            for r in rows
        ],
        "trend": trend_data,
    }


# ── 인기 페이지 ──

@router.get("/popular")
async def get_popular_pages(
    admin_id: str = Query(description="관리자 google_id"),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=20, ge=1, le=100),
):
    """인기 페이지 통계"""
    await _check_admin(admin_id)
    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT
                    path,
                    page_title,
                    feature,
                    COUNT(*) as visits,
                    COUNT(DISTINCT google_id) as unique_users,
                    ROUND(AVG(duration_ms)) as avg_duration_ms
                FROM access_logs
                WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                GROUP BY path, page_title, feature
                ORDER BY visits DESC
                LIMIT %s
            """, (days, limit))
            rows = await cur.fetchall()

    return {
        "popular": [
            {
                "path": r[0],
                "page_title": r[1] or "",
                "feature": r[2] or "",
                "visits": r[3],
                "unique_users": r[4],
                "avg_duration_ms": r[5] or 0,
            }
            for r in rows
        ]
    }


# ── 사용자별 방문 통계 ──

@router.get("/users")
async def get_user_stats(
    admin_id: str = Query(description="관리자 google_id"),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=20, ge=1, le=100),
):
    """사용자별 방문 통계 (가장 활동적인 사용자 순)"""
    await _check_admin(admin_id)
    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT
                    u.name,
                    u.email,
                    COUNT(al.id) as total_views,
                    COUNT(DISTINCT DATE(al.created_at)) as active_days
                FROM users u
                JOIN access_logs al ON al.google_id = u.google_id
                WHERE al.created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                GROUP BY u.google_id, u.name, u.email
                ORDER BY total_views DESC
                LIMIT %s
            """, (days, limit))
            rows = await cur.fetchall()

    return {
        "users": [
            {
                "name": r[0] or "익명",
                "email": r[1] or "",
                "total_views": r[2],
                "active_days": r[3],
            }
            for r in rows
        ]
    }
