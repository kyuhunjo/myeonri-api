from __future__ import annotations

from fastapi import APIRouter, HTTPException
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
