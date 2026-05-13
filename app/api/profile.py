"""
사주 프로필 API (saju_profiles 테이블)
다른 사람 사주 저장/목록/상세/삭제
"""

from __future__ import annotations
import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.database import get_pool

logger = logging.getLogger("myeonri-api")
router = APIRouter(prefix="/user", tags=["사주프로필"])


# ── 다른 사람 사주 저장 ──

class OtherSajuSaveRequest(BaseModel):
    google_id: str
    nickname: str
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int = 12
    birth_minute: int = 0
    gender: str = "남"
    calendar: str = "solar"
    saju_data: dict | None = None


@router.post("/other/save")
async def save_other_saju(req: OtherSajuSaveRequest):
    """다른 사람 사주 저장 — saju_profiles 테이블 (nickname 필수)"""
    if not req.nickname or not req.nickname.strip():
        raise HTTPException(status_code=400, detail="별칭(nickname)은 필수입니다")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM users WHERE google_id = %s LIMIT 1",
                (req.google_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
            user_id = row[0]

            await cur.execute(
                "SELECT id FROM saju_profiles WHERE user_id = %s AND nickname = %s LIMIT 1",
                (user_id, req.nickname.strip()),
            )
            existing = await cur.fetchone()

            if existing:
                await cur.execute(
                    """UPDATE saju_profiles SET
                        birth_year=%s, birth_month=%s, birth_day=%s,
                        birth_hour=%s, birth_minute=%s,
                        gender=%s, calendar=%s,
                        saju_data=%s,
                        updated_at=NOW()
                    WHERE id=%s""",
                    (
                        req.birth_year, req.birth_month, req.birth_day,
                        req.birth_hour, req.birth_minute,
                        req.gender, req.calendar,
                        json.dumps(req.saju_data, ensure_ascii=False) if req.saju_data else None,
                        existing[0],
                    ),
                )
                return {"success": True, "action": "updated", "profile_id": existing[0]}
            else:
                await cur.execute(
                    """INSERT INTO saju_profiles
                        (user_id, nickname, birth_year, birth_month, birth_day,
                         birth_hour, birth_minute, gender, calendar, saju_data)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        user_id, req.nickname.strip(), req.birth_year, req.birth_month, req.birth_day,
                        req.birth_hour, req.birth_minute,
                        req.gender, req.calendar,
                        json.dumps(req.saju_data, ensure_ascii=False) if req.saju_data else None,
                    ),
                )
                return {"success": True, "action": "created", "profile_id": cur.lastrowid}


# ── 다른 사람 사주 목록 ──

class ProfileListRequest(BaseModel):
    google_id: str


@router.post("/other/list", tags=["다른 사람 사주"])
async def get_other_saju_profiles(req: ProfileListRequest):
    """다른 사람 사주 목록 조회 (saju_profiles)"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM users WHERE google_id = %s LIMIT 1",
                (req.google_id,),
            )
            row = await cur.fetchone()
            if not row:
                return {"profiles": []}
            user_id = row[0]

            await cur.execute(
                """SELECT id, nickname, birth_year, birth_month, birth_day,
                    birth_hour, birth_minute, gender, calendar, created_at
                FROM saju_profiles
                WHERE user_id = %s
                ORDER BY created_at DESC""",
                (user_id,),
            )
            rows = await cur.fetchall()

    profiles = []
    for row in rows:
        profiles.append({
            "id": row[0], "nickname": row[1],
            "birth_year": row[2], "birth_month": row[3], "birth_day": row[4],
            "birth_hour": row[5], "birth_minute": row[6],
            "gender": row[7], "calendar": row[8],
            "created_at": str(row[9]) if row[9] else None,
        })
    return {"profiles": profiles}


# ── 다른 사람 사주 상세 ──

class ProfileGetRequest(BaseModel):
    google_id: str
    profile_id: int


@router.post("/other/get", tags=["다른 사람 사주"])
async def get_other_saju_profile(req: ProfileGetRequest):
    """특정 다른 사람 사주 상세 조회 (saju_data 포함)"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """SELECT sp.id, sp.nickname, sp.birth_year, sp.birth_month, sp.birth_day,
                    sp.birth_hour, sp.birth_minute, sp.gender, sp.calendar,
                    sp.saju_data, sp.created_at
                FROM saju_profiles sp
                JOIN users u ON u.id = sp.user_id
                WHERE sp.id = %s AND u.google_id = %s
                LIMIT 1""",
                (req.profile_id, req.google_id),
            )
            row = await cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다")

    saju_data = row[9]
    if saju_data and not isinstance(saju_data, dict):
        try:
            saju_data = json.loads(saju_data)
        except (json.JSONDecodeError, TypeError):
            saju_data = None

    return {
        "id": row[0], "nickname": row[1],
        "birth_year": row[2], "birth_month": row[3], "birth_day": row[4],
        "birth_hour": row[5], "birth_minute": row[6],
        "gender": row[7], "calendar": row[8],
        "saju_data": saju_data,
        "created_at": str(row[10]) if row[10] else None,
    }


# ── 다른 사람 사주 삭제 ──

class ProfileDeleteRequest(BaseModel):
    google_id: str
    profile_id: int


@router.post("/other/delete", tags=["다른 사람 사주"])
async def delete_other_saju_profile(req: ProfileDeleteRequest):
    """다른 사람 사주 삭제"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """SELECT sp.id FROM saju_profiles sp
                    JOIN users u ON u.id = sp.user_id
                WHERE sp.id = %s AND u.google_id = %s
                LIMIT 1""",
                (req.profile_id, req.google_id),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="프로필을 찾을 수 없거나 권한이 없습니다")

            await cur.execute(
                "DELETE FROM saju_profiles WHERE id = %s",
                (req.profile_id,),
            )

    return {"success": True, "profile_id": req.profile_id}
