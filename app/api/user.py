from __future__ import annotations
import logging
logger = logging.getLogger("myeonri-api")

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.api.schemas import UserCheckRequest, UserSaveRequest, UserResponse
from app.core.database import get_pool

router = APIRouter(prefix="/user", tags=["사용자"])


@router.post("/check", response_model=UserResponse)
async def check_user(req: UserCheckRequest):
    """Google ID로 사용자 조회"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT * FROM users WHERE google_id = %s LIMIT 1",
                (req.google_id,),
            )
            row = await cur.fetchone()

    if not row:
        return UserResponse(found=False, user=None)

    columns = [
        "id", "google_id", "email", "name",
        "birth_year", "birth_month", "birth_day",
        "birth_hour", "birth_minute",
        "gender", "calendar", "saju_data",
        "created_at", "updated_at",
        "role",
    ]
    user = dict(zip(columns, row))
    # datetime → str 변환
    for k in ("created_at", "updated_at"):
        if user.get(k):
            user[k] = str(user[k])
    if user.get("saju_data") and not isinstance(user["saju_data"], dict):
        import json
        try:
            user["saju_data"] = json.loads(user["saju_data"])
        except (json.JSONDecodeError, TypeError):
            user["saju_data"] = {}

    return UserResponse(found=True, user=user)


@router.post("/save")
async def save_user(req: UserSaveRequest):
    """사용자 저장 (INSERT or UPDATE)"""
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
                # UPDATE
                await cur.execute(
                    """UPDATE users SET
                        email = %s, name = %s,
                        birth_year = %s, birth_month = %s, birth_day = %s,
                        birth_hour = %s, birth_minute = %s,
                        gender = %s, calendar = %s,
                        updated_at = NOW()
                    WHERE google_id = %s""",
                    (
                        req.email, req.name,
                        req.birth_year, req.birth_month, req.birth_day,
                        req.birth_hour, req.birth_minute,
                        req.gender, req.calendar,
                        req.google_id,
                    ),
                )
                return {"success": True, "action": "updated"}
            else:
                # INSERT
                await cur.execute(
                    """INSERT INTO users
                        (google_id, email, name, birth_year, birth_month, birth_day,
                         birth_hour, birth_minute, gender, calendar)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        req.google_id, req.email, req.name,
                        req.birth_year, req.birth_month, req.birth_day,
                        req.birth_hour, req.birth_minute,
                        req.gender, req.calendar,
                    ),
                )
                return {"success": True, "action": "created"}


@router.post("/saju-data")
async def save_saju_data(google_id: str, saju_data: dict):
    """사용자 사주 데이터 저장"""
    import json
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE users SET saju_data = %s, updated_at = NOW() WHERE google_id = %s",
                (json.dumps(saju_data, ensure_ascii=False), google_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
            return {"success": True}


class ConsultHistorySaveRequest(BaseModel):
    google_id: str
    category: str
    question: str = ""
    answer: str
    model: str = ""


class ConsultHistoryItem(BaseModel):
    id: int
    category: str
    question: str | None
    answer: str
    model: str | None
    created_at: str | None


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
    from app.core.database import get_pool

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
                "SELECT id, google_id, email, name, birth_year, birth_month, birth_day, "
                "gender, calendar, role, created_at "
                "FROM users ORDER BY created_at DESC"
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
    from app.core.database import get_pool

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
                "UPDATE users SET role = %s, updated_at = NOW() WHERE google_id = %s",
                (req.role, req.target_google_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="User not found")

    return {"success": True, "role": req.role}
