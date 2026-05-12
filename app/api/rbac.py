from __future__ import annotations
import logging
logger = logging.getLogger("myeonri-api")

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.database import get_pool

router = APIRouter(prefix="/rbac", tags=["RBAC"])


# ── 역할 목록 ──

@router.get("/roles")
async def get_roles():
    """전체 역할 목록 + 각 역할별 권한"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id, name, description FROM roles ORDER BY id")
            roles = [{"id": r[0], "name": r[1], "description": r[2]} for r in await cur.fetchall()]

            await cur.execute("SELECT id, code, description FROM permissions ORDER BY id")
            all_perms = [{"id": p[0], "code": p[1], "description": p[2]} for p in await cur.fetchall()]

            for role in roles:
                await cur.execute(
                    "SELECT p.id, p.code, p.description FROM role_permissions rp "
                    "JOIN permissions p ON p.id = rp.permission_id WHERE rp.role_id = %s",
                    (role["id"],),
                )
                role["permissions"] = [{"id": p[0], "code": p[1], "description": p[2]} for p in await cur.fetchall()]

    return {"roles": roles, "all_permissions": all_perms}


# ── 사용자 역할 조회 ──

class UserRolesRequest(BaseModel):
    admin_id: str
    target_google_id: str


@router.post("/user-roles")
async def get_user_roles(req: UserRolesRequest):
    """특정 사용자의 역할 목록 조회 (관리자 전용)"""
    await _check_admin(req.admin_id)

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM users WHERE google_id = %s LIMIT 1",
                (req.target_google_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
            user_id = row[0]

            await cur.execute(
                "SELECT r.id, r.name, r.description FROM user_roles ur "
                "JOIN roles r ON r.id = ur.role_id WHERE ur.user_id = %s",
                (user_id,),
            )
            roles = [{"id": r[0], "name": r[1], "description": r[2]} for r in await cur.fetchall()]

    return {"google_id": req.target_google_id, "roles": roles}


# ── 사용자 역할 할당/해제 ──

class UserRoleUpdateRequest(BaseModel):
    admin_id: str
    target_google_id: str
    role_id: int
    action: str  # 'add' | 'remove'


@router.post("/user-role/update")
async def update_user_role(req: UserRoleUpdateRequest):
    """사용자 역할 추가/제거 (관리자 전용)"""
    await _check_admin(req.admin_id)

    if req.action not in ("add", "remove"):
        raise HTTPException(status_code=400, detail="actionは 'add' または 'remove' にしてください")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM users WHERE google_id = %s LIMIT 1",
                (req.target_google_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
            user_id = row[0]

            if req.action == "add":
                await cur.execute(
                    "INSERT IGNORE INTO user_roles (user_id, role_id) VALUES (%s, %s)",
                    (user_id, req.role_id),
                )
            else:
                await cur.execute(
                    "DELETE FROM user_roles WHERE user_id = %s AND role_id = %s",
                    (user_id, req.role_id),
                )

    return {"success": True, "action": req.action, "role_id": req.role_id}


# ── 권한 확인 헬퍼 ──


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
