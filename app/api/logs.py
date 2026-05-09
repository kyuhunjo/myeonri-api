from __future__ import annotations

import asyncio
from fastapi import APIRouter, Query

from app.core.config import settings

router = APIRouter(prefix="/logs", tags=["로그"])


@router.get("")
async def get_logs(
    tail: int = Query(default=100, ge=10, le=1000, description="가져올 라인 수"),
    level: str = Query(default="", description="로그 레벨 필터 (INFO, ERROR, WARNING)"),
    grep: str = Query(default="", description="키워드 필터"),
):
    """
    서비스 로그 조회 (현재 파드의 stdout 로그)
    API 키 인증 필요 (x-api-key 헤더)
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "tail", f"-n{tail}", "/proc/self/fd/1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        lines = stdout.decode("utf-8", errors="replace").splitlines()
    except Exception:
        return {"total": 0, "logs": ["로그를 읽을 수 없습니다."]}

    # 필터
    if level:
        level_upper = level.upper()
        lines = [l for l in lines if level_upper in l]
    if grep:
        lines = [l for l in lines if grep.lower() in l.lower()]

    return {
        "total": len(lines),
        "logs": lines[-settings.LOG_TAIL_MAX:],
    }
