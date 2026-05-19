"""
접속 통계 API
- access_logs 테이블 기반 통계 조회
- 관리자 전용
"""

from __future__ import annotations
import logging

from fastapi import APIRouter, Query, HTTPException
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


@router.get("/summary")
async def get_stats_summary(
    admin_id: str = Query(description="관리자 google_id"),
):
    """접속 통계 요약 — 전체 방문자, 오늘 방문, 활성 사용자 등"""
    await _check_admin(admin_id)
    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # 전체 접속 수
            await cur.execute("SELECT COUNT(*) FROM access_logs")
            total_visits = (await cur.fetchone())[0]

            # 오늘 접속 수
            await cur.execute(
                "SELECT COUNT(*) FROM access_logs WHERE DATE(created_at) = CURDATE()"
            )
            today_visits = (await cur.fetchone())[0]

            # 어제 접속 수
            await cur.execute(
                "SELECT COUNT(*) FROM access_logs WHERE DATE(created_at) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)"
            )
            yesterday_visits = (await cur.fetchone())[0]

            # 전체 방문 사용자 (고유 google_id)
            await cur.execute(
                "SELECT COUNT(DISTINCT google_id) FROM access_logs WHERE google_id IS NOT NULL"
            )
            total_users = (await cur.fetchone())[0]

            # 오늘 방문 사용자 (고유)
            await cur.execute(
                "SELECT COUNT(DISTINCT google_id) FROM access_logs WHERE DATE(created_at) = CURDATE() AND google_id IS NOT NULL"
            )
            today_users = (await cur.fetchone())[0]

            # 전체 회원 수
            await cur.execute("SELECT COUNT(*) FROM users")
            total_registered = (await cur.fetchone())[0]

            # 오늘 가입자
            await cur.execute(
                "SELECT COUNT(*) FROM users WHERE DATE(created_at) = CURDATE()"
            )
            today_registered = (await cur.fetchone())[0]

            return {
                "total_visits": total_visits,
                "today_visits": today_visits,
                "yesterday_visits": yesterday_visits,
                "total_users": total_users,
                "today_users": today_users,
                "total_registered": total_registered,
                "today_registered": today_registered,
            }


@router.get("/daily")
async def get_daily_stats(
    admin_id: str = Query(description="관리자 google_id"),
    days: int = Query(default=30, ge=1, le=365, description="조회할 일 수"),
):
    """일별 접속 통계"""
    await _check_admin(admin_id)
    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT
                    DATE(created_at) as date,
                    COUNT(*) as visits,
                    COUNT(DISTINCT google_id) as unique_users
                FROM access_logs
                WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                GROUP BY DATE(created_at)
                ORDER BY date DESC
            """, (days,))
            rows = await cur.fetchall()

    return {
        "daily": [
            {"date": str(r[0]), "visits": r[1], "unique_users": r[2]}
            for r in rows
        ]
    }


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
                    COUNT(*) as visits,
                    COUNT(DISTINCT google_id) as unique_users
                FROM access_logs
                WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                GROUP BY path
                ORDER BY visits DESC
                LIMIT %s
            """, (days, limit))
            rows = await cur.fetchall()

    return {
        "popular": [
            {"path": r[0], "visits": r[1], "unique_users": r[2]}
            for r in rows
        ]
    }
