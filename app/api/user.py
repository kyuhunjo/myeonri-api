"""
사용자 CRUD API
— /check, /save, /saju/save
— /list, /role (관리자)

portal-idp 전환 (2026-07-20):
- google_id → portal_id (sub from portal-idp JWT)
- users 테이블에 portal_id 컬럼 필요 (ALTER TABLE 필요)
- 하위 호환: portal_id 없으면 google_id 로 fallback
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
    """portal_id 또는 google_id 로 사용자 조회 + 내 사주 데이터 함께 반환"""
    pool = await get_pool()

    # portal_id 우선, google_id fallback
    user_row = None
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # portal_id 로 먼저查找
            if req.portal_id:
                await cur.execute(
                    "SELECT id, portal_id, google_id, email, name, role, created_at, "
                    "birth_year, birth_month, birth_day, birth_hour, birth_minute, "
                    "gender, calendar, saju_data "
                    "FROM users WHERE portal_id = %s LIMIT 1",
                    (req.portal_id,),
                )
                user_row = await cur.fetchone()

            # portal_id 없으면 google_id 로
            if not user_row and req.google_id:
                await cur.execute(
                    "SELECT id, portal_id, google_id, email, name, role, created_at, "
                    "birth_year, birth_month, birth_day, birth_hour, birth_minute, "
                    "gender, calendar, saju_data "
                    "FROM users WHERE google_id = %s LIMIT 1",
                    (req.google_id,),
                )
                user_row = await cur.fetchone()

    if not user_row:
        return UserResponse(found=False, user=None)

    columns = [
        "id", "portal_id", "google_id", "email", "name", "role", "created_at",
        "birth_year", "birth_month", "birth_day", "birth_hour", "birth_minute",
        "gender", "calendar", "saju_data",
    ]
    user = dict(zip(columns, user_row))
    if user.get("created_at"):
        user["created_at"] = str(user["created_at"])
    if user.get("saju_data") and not isinstance(user["saju_data"], dict):
        try:
            user["saju_data"] = json.loads(user["saju_data"])
        except (json.JSONDecodeError, TypeError):
            user["saju_data"] = None

    # user_id 는 portal_id 우선 (새 인증 방식)
    user["user_id"] = user.get("portal_id") or user.get("google_id")

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


# ── 사용자 저장 ──

@router.post("/save")
async def save_user(req: UserSaveRequest):
    """사용자 저장 (INSERT or UPDATE — portal-idp JWT sub 기준)"""
    pool = await get_pool()

    # portal_id 또는 google_id 중 하나는 있어야 함
    lookup_id = req.portal_id or req.google_id
    if not lookup_id:
        raise HTTPException(status_code=400, detail="portal_id or google_id required")

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            existing = None  # 먼저 초기화
            
            # portal_id 로 먼저查找
            if req.portal_id:
                await cur.execute(
                    "SELECT id FROM users WHERE portal_id = %s LIMIT 1",
                    (req.portal_id,),
                )
                existing = await cur.fetchone()

            # portal_id 없으면 google_id 로
            if not existing and req.google_id:
                await cur.execute(
                    "SELECT id FROM users WHERE google_id = %s LIMIT 1",
                    (req.google_id,),
                )
                existing = await cur.fetchone()

            if existing:
                # UPDATE — portal_id 도 함께 갱신
                await cur.execute(
                    "UPDATE users SET email = %s, name = %s, portal_id = COALESCE(%s, portal_id) "
                    "WHERE google_id = %s OR portal_id = %s",
                    (req.email, req.name, req.portal_id, req.google_id, req.portal_id),
                )
                return {"success": True, "action": "updated", "user_id": existing[0]}

            # ── 중복 방지: 이메일로 기존 사용자查找 (Google → portal-idp 마이그레이션) ──
            # 기존 사용자가 portal-idp 로 처음 로그인할 때 google_id=None, portal_id=new-sub
            # email 로查找해서 portal_id 를UPDATE (계정 중복 방지)
            if req.portal_id and req.email:
                await cur.execute(
                    "SELECT id, google_id FROM users WHERE email = %s AND portal_id IS NULL LIMIT 1",
                    (req.email,),
                )
                existing_by_email = await cur.fetchone()
                if existing_by_email:
                    old_id, old_google_id = existing_by_email
                    await cur.execute(
                        "UPDATE users SET portal_id = %s, google_id = COALESCE(%s, google_id) "
                        "WHERE id = %s",
                        (req.portal_id, req.google_id, old_id),
                    )
                    logger.info(f"Migrated user {old_id} (google_id={old_google_id}) → portal_id={req.portal_id}")
                    return {"success": True, "action": "migrated", "user_id": old_id}

            # INSERT — portal_id 사용 (google_id 는 NULL 허용)
            await cur.execute(
                "INSERT INTO users (portal_id, google_id, email, name) VALUES (%s, %s, %s, %s)",
                (req.portal_id, req.google_id, req.email, req.name),
            )
            return {"success": True, "action": "created", "user_id": cur.lastrowid}


# ── 내 사주 저장 ──

class MySajuSaveRequest(BaseModel):
    portal_id: str | None = None
    google_id: str | None = None
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
    lookup_id = req.portal_id or req.google_id
    if not lookup_id:
        raise HTTPException(status_code=400, detail="portal_id or google_id required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # portal_id 또는 google_id 로查找
            if req.portal_id:
                await cur.execute(
                    "SELECT id FROM users WHERE portal_id = %s LIMIT 1",
                    (req.portal_id,),
                )
            else:
                await cur.execute(
                    "SELECT id FROM users WHERE google_id = %s LIMIT 1",
                    (req.google_id,),
                )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

            where_col = "portal_id" if req.portal_id else "google_id"
            where_val = req.portal_id if req.portal_id else req.google_id
            await cur.execute(
                f"""UPDATE users SET
                    birth_year=%s, birth_month=%s, birth_day=%s,
                    birth_hour=%s, birth_minute=%s,
                    gender=%s, calendar=%s,
                    saju_data=%s,
                    updated_at=NOW()
                WHERE {where_col}=%s""",
                (
                    req.birth_year, req.birth_month, req.birth_day,
                    req.birth_hour, req.birth_minute,
                    req.gender, req.calendar,
                    json.dumps(req.saju_data, ensure_ascii=False) if req.saju_data else None,
                    where_val,
                ),
            )
    return {"success": True}


# ── 관리자: 사용자 목록 ──

@router.get("/list")
async def get_users(admin_id: str):
    """사용자 목록 조회 (관리자 전용)"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # portal_id 또는 google_id 로 관리자 확인
            await cur.execute(
                "SELECT role FROM users WHERE portal_id = %s OR google_id = %s LIMIT 1",
                (admin_id, admin_id),
            )
            row = await cur.fetchone()
    if not row or row[0] != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: admin only")

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, portal_id, google_id, email, name, "
                "birth_year, birth_month, birth_day, "
                "gender, calendar, role, created_at "
                "FROM users ORDER BY created_at DESC"
            )
            rows = await cur.fetchall()

    result = []
    for row in rows:
        result.append({
            "id": row[0],
            "portal_id": req[1],
            "google_id": row[2],
            "email": row[3],
            "name": row[4],
            "birth_year": row[5],
            "birth_month": row[6],
            "birth_day": row[7],
            "gender": row[8],
            "calendar": row[9],
            "role": row[10],
            "created_at": str(row[11]) if row[11] else None,
        })
    return {"users": result}


class UpdateRoleRequest(BaseModel):
    admin_id: str
    target_portal_id: str | None = None
    target_google_id: str | None = None
    role: str


@router.patch("/role")
async def update_user_role(req: UpdateRoleRequest):
    """사용자 역할 변경 (관리자 전용)"""
    if req.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'user' or 'admin'")

    target_id = req.target_portal_id or req.target_google_id
    if not target_id:
        raise HTTPException(status_code=400, detail="target_portal_id or target_google_id required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT role FROM users WHERE portal_id = %s OR google_id = %s LIMIT 1",
                (req.admin_id, req.admin_id),
            )
            row = await cur.fetchone()
    if not row or row[0] != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: admin only")

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE users SET role = %s WHERE portal_id = %s OR google_id = %s",
                (req.role, target_id, target_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="User not found")

    return {"success": True, "role": req.role}
