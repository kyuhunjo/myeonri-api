"""
사용자 CRUD API
— /check, /save, /saju/save
— /list, /role (관리자)
"""

from __future__ import annotations
import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.api.schemas import UserCheckRequest, UserSaveRequest, UserResponse
from app.core.database import get_pool

logger = logging.getLogger("myeonri-api")
router = APIRouter(prefix="/user", tags=["사용자"])


# ── 사용자 조회 ──

@router.post("/check", response_model=UserResponse)
async def check_user(req: UserCheckRequest):
    """Google ID로 사용자 조회 + 내 사주 데이터 함께 반환"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, google_id, email, name, role, created_at, "
                "birth_year, birth_month, birth_day, birth_hour, birth_minute, "
                "gender, calendar, saju_data "
                "FROM users WHERE google_id = %s LIMIT 1",
                (req.google_id,),
            )
            row = await cur.fetchone()

    if not row:
        return UserResponse(found=False, user=None)

    columns = [
        "id", "google_id", "email", "name", "role", "created_at",
        "birth_year", "birth_month", "birth_day", "birth_hour", "birth_minute",
        "gender", "calendar", "saju_data",
    ]
    user = dict(zip(columns, row))
    if user.get("created_at"):
        user["created_at"] = str(user["created_at"])
    if user.get("saju_data") and not isinstance(user["saju_data"], dict):
        try:
            user["saju_data"] = json.loads(user["saju_data"])
        except (json.JSONDecodeError, TypeError):
            user["saju_data"] = None

    # 역할 및 권한 정보
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT r.id, r.name FROM user_roles ur "
                "JOIN roles r ON r.id = ur.role_id WHERE ur.user_id = %s",
                (user["id"],),
            )
            user["roles"] = [{"id": r[0], "name": r[1]} for r in await cur.fetchall()]

            all_perms = set()
            for role in user["roles"]:
                await cur.execute(
                    "SELECT p.code FROM role_permissions rp "
                    "JOIN permissions p ON p.id = rp.permission_id WHERE rp.role_id = %s",
                    (role["id"],),
                )
                for p in await cur.fetchall():
                    all_perms.add(p[0])
            user["permissions"] = sorted(all_perms)

    return UserResponse(found=True, user=user)


# ── 사용자 저장 (구글 로그인) ──

@router.post("/save")
async def save_user(req: UserSaveRequest):
    """사용자 저장 (INSERT or UPDATE — 구글 로그인 정보)"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM users WHERE google_id = %s LIMIT 1",
                (req.google_id,),
            )
            existing = await cur.fetchone()

            if existing:
                await cur.execute(
                    "UPDATE users SET email = %s, name = %s WHERE google_id = %s",
                    (req.email, req.name, req.google_id),
                )
                return {"success": True, "action": "updated", "user_id": existing[0]}
            else:
                await cur.execute(
                    "INSERT INTO users (google_id, email, name) VALUES (%s, %s, %s)",
                    (req.google_id, req.email, req.name),
                )
                return {"success": True, "action": "created", "user_id": cur.lastrowid}


# ── 내 사주 저장 ──

class MySajuSaveRequest(BaseModel):
    google_id: str
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int = 12
    birth_minute: int = 0
    gender: str = "남"
    calendar: str = "solar"
    saju_data: dict | None = None


@router.post("/saju/save")
async def save_my_saju(req: MySajuSaveRequest):
    """내 사주 저장 — users 테이블의 birth_* / saju_data 업데이트"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """UPDATE users SET
                    birth_year=%s, birth_month=%s, birth_day=%s,
                    birth_hour=%s, birth_minute=%s,
                    gender=%s, calendar=%s,
                    saju_data=%s,
                    updated_at=NOW()
                WHERE google_id=%s""",
                (
                    req.birth_year, req.birth_month, req.birth_day,
                    req.birth_hour, req.birth_minute,
                    req.gender, req.calendar,
                    json.dumps(req.saju_data, ensure_ascii=False) if req.saju_data else None,
                    req.google_id,
                ),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    return {"success": True}


# ── 관리자: 사용자 목록 ──

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
                "SELECT id, google_id, email, name, "
                "birth_year, birth_month, birth_day, "
                "gender, calendar, role, created_at "
                "FROM users ORDER BY created_at DESC"
            )
            rows = await cur.fetchall()

    result = []
    for row in rows:
        result.append({
            "id": row[0], "google_id": row[1], "email": row[2], "name": row[3],
            "birth_year": row[4], "birth_month": row[5], "birth_day": row[6],
            "gender": row[7], "calendar": row[8], "role": row[9],
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
    if req.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'user' or 'admin'")

    pool = await get_pool()
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
