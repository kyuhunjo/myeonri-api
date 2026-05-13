"""
상담 내역 API
— consult_history 테이블 저장/조회
"""

from __future__ import annotations
import logging

from fastapi import APIRouter
from pydantic import BaseModel
from app.core.database import get_pool

logger = logging.getLogger("myeonri-api")
router = APIRouter(prefix="/user", tags=["상담내역"])


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
            "id": row[0], "category": row[1], "question": row[2],
            "answer": row[3], "model": row[4],
            "created_at": str(row[5]) if row[5] else None,
        })
    return {"history": result}
