from __future__ import annotations
import logging
logger = logging.getLogger("myeonri-api")

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.api.schemas import UserCheckRequest, UserSaveRequest, UserResponse, SajuProfileResponse
from app.core.database import get_pool

router = APIRouter(prefix="/user", tags=["사용자"])


@router.post("/check", response_model=UserResponse)
async def check_user(req: UserCheckRequest):
    """Google ID로 사용자 조회 + 대표 사주 프로필 함께 반환"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, google_id, email, name, role, created_at FROM users WHERE google_id = %s LIMIT 1",
                (req.google_id,),
            )
            row = await cur.fetchone()

    if not row:
        return UserResponse(found=False, user=None)

    columns = ["id", "google_id", "email", "name", "role", "created_at"]
    user = dict(zip(columns, row))
    if user.get("created_at"):
        user["created_at"] = str(user["created_at"])

    # 대표 사주 프로필 조회
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, birth_year, birth_month, birth_day, birth_hour, birth_minute, "
                "gender, calendar, saju_data, is_primary "
                "FROM saju_profiles "
                "WHERE user_id = %s AND is_primary = 1 "
                "LIMIT 1",
                (user["id"],),
            )
            profile_row = await cur.fetchone()

    if profile_row:
        profile_cols = ["id", "birth_year", "birth_month", "birth_day",
                        "birth_hour", "birth_minute", "gender", "calendar",
                        "saju_data", "is_primary"]
        profile = dict(zip(profile_cols, profile_row))
        if profile.get("saju_data") and not isinstance(profile["saju_data"], dict):
            try:
                profile["saju_data"] = json.loads(profile["saju_data"])
            except (json.JSONDecodeError, TypeError):
                profile["saju_data"] = None
        user["profile"] = profile
    else:
        user["profile"] = None

    return UserResponse(found=True, user=user)


@router.post("/save")
async def save_user(req: UserSaveRequest):
    """사용자 저장 (INSERT only — 구글 로그인 정보)"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # 기존 사용자 확인
            await cur.execute(
                "SELECT id FROM users WHERE google_id = %s LIMIT 1",
                (req.google_id,),
            )
            existing = await cur.fetchone()

            if existing:
                # UPDATE: name/email만 갱신
                await cur.execute(
                    "UPDATE users SET email = %s, name = %s WHERE google_id = %s",
                    (req.email, req.name, req.google_id),
                )
                return {"success": True, "action": "updated", "user_id": existing[0]}
            else:
                # INSERT
                await cur.execute(
                    "INSERT INTO users (google_id, email, name) VALUES (%s, %s, %s)",
                    (req.google_id, req.email, req.name),
                )
                return {"success": True, "action": "created", "user_id": cur.lastrowid}


# ── 사주 프로필 ──

class SajuProfileSaveRequest(BaseModel):
    google_id: str
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int = 12
    birth_minute: int = 0
    gender: str = "남"
    calendar: str = "solar"
    saju_data: dict | None = None
    is_primary: bool = True


@router.post("/profile/save")
async def save_saju_profile(req: SajuProfileSaveRequest):
    """사주 프로필 저장 (INSERT or UPDATE)"""
    pool = await get_pool()

    # user_id 조회
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

    # 기존 primary 프로필 확인
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            if req.is_primary:
                await cur.execute(
                    "UPDATE saju_profiles SET is_primary = 0 WHERE user_id = %s",
                    (user_id,),
                )
            await cur.execute(
                "SELECT id FROM saju_profiles WHERE user_id = %s AND is_primary = 1 LIMIT 1",
                (user_id,),
            )
            profile_row = await cur.fetchone()

            if profile_row:
                # UPDATE
                await cur.execute(
                    """UPDATE saju_profiles SET
                        birth_year=%s, birth_month=%s, birth_day=%s,
                        birth_hour=%s, birth_minute=%s,
                        gender=%s, calendar=%s,
                        saju_data=%s, is_primary=%s,
                        updated_at=NOW()
                    WHERE id=%s""",
                    (
                        req.birth_year, req.birth_month, req.birth_day,
                        req.birth_hour, req.birth_minute,
                        req.gender, req.calendar,
                        json.dumps(req.saju_data, ensure_ascii=False) if req.saju_data else None,
                        1 if req.is_primary else 0,
                        profile_row[0],
                    ),
                )
                return {"success": True, "action": "updated", "profile_id": profile_row[0]}
            else:
                # INSERT
                await cur.execute(
                    """INSERT INTO saju_profiles
                        (user_id, birth_year, birth_month, birth_day,
                         birth_hour, birth_minute, gender, calendar,
                         saju_data, is_primary)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        user_id, req.birth_year, req.birth_month, req.birth_day,
                        req.birth_hour, req.birth_minute,
                        req.gender, req.calendar,
                        json.dumps(req.saju_data, ensure_ascii=False) if req.saju_data else None,
                        1 if req.is_primary else 0,
                    ),
                )
                return {"success": True, "action": "created", "profile_id": cur.lastrowid}


# ── 상담 내역 ──

class ConsultHistorySaveRequest(BaseModel):
    google_id: str
    category: str
    question: str = ""
    answer: str
    model: str = ""


@router.post("/consult/history/save")
async def save_consult_history(req: ConsultHistorySaveRequest):
    """상담 내역 저장"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO consult_history (google_id, category, question, answer, model) "
                "VALUES (%s, %s, %s, %s, %s)",
                (req.google_id, req.category, req.question, req.answer, req.model),
            )
    return {"success": True, "id": cur.lastrowid}


@router.get("/consult/history/{google_id}")
async def get_consult_history(google_id: str):
    """사용자 상담 내역 조회 (최근 20개)"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, category, question, answer, model, created_at "
                "FROM consult_history WHERE google_id = %s "
                "ORDER BY created_at DESC LIMIT 20",
                (google_id,),
            )
            rows = await cur.fetchall()

    result = []
    for row in rows:
        result.append({
            "id": row[0],
            "category": row[1],
            "question": row[2],
            "answer": row[3],
            "model": row[4],
            "created_at": str(row[5]) if row[5] else None,
        })
    return {"history": result}


@router.get("/list")
async def get_users(admin_id: str):
    """사용자 목록 조회 (관리자 전용)"""
    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT role FROM users WHERE google_id = %s LIMIT 1",
                (admin_id,),
            )
            row = await cur.fetchone()
    if not row or row[0] != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: admin only")

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT u.id, u.google_id, u.email, u.name, "
                "sp.birth_year, sp.birth_month, sp.birth_day, "
                "sp.gender, sp.calendar, u.role, u.created_at "
                "FROM users u "
                "LEFT JOIN saju_profiles sp ON sp.user_id = u.id AND sp.is_primary = 1 "
                "ORDER BY u.created_at DESC"
            )
            rows = await cur.fetchall()

    result = []
    for row in rows:
        result.append({
            "id": row[0],
            "google_id": row[1],
            "email": row[2],
            "name": row[3],
            "birth_year": row[4],
            "birth_month": row[5],
            "birth_day": row[6],
            "gender": row[7],
            "calendar": row[8],
            "role": row[9],
            "created_at": str(row[10]) if row[10] else None,
        })
    return {"users": result}


class UpdateRoleRequest(BaseModel):
    admin_id: str
    target_google_id: str
    role: str


@router.patch("/role")
async def update_user_role(req: UpdateRoleRequest):
    """사용자 역할 변경 (관리자 전용)"""
    pool = await get_pool()

    if req.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'user' or 'admin'")

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT role FROM users WHERE google_id = %s LIMIT 1",
                (req.admin_id,),
            )
            row = await cur.fetchone()
    if not row or row[0] != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: admin only")

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE users SET role = %s WHERE google_id = %s",
                (req.role, req.target_google_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="User not found")

    return {"success": True, "role": req.role}
