from __future__ import annotations
import logging
logger = logging.getLogger("myeonri-api")

import asyncio
from fastapi import APIRouter, Query

from app.core.config import settings

router = APIRouter(prefix="/logs", tags=["로그"])

LOG_FILE = "/tmp/myeonri-api.log"


@router.get("")
async def get_logs(
    tail: int = Query(default=100, ge=10, le=1000, description="가져올 라인 수"),
    level: str = Query(default="", description="로그 레벨 필터 (INFO, ERROR, WARNING)"),
    grep: str = Query(default="", description="키워드 필터"),
):
    """서비스 로그 조회"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "tail", f"-n{tail}", LOG_FILE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        lines = stdout.decode("utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return {"total": 0, "logs": ["로그 파일이 없습니다."]}
    except Exception as e:
        return {"total": 0, "logs": [f"로그 읽기 오류: {e}"]}

    if level:
        level_upper = level.upper()
        lines = [l for l in lines if level_upper in l]
    if grep:
        lines = [l for l in lines if grep.lower() in l.lower()]

    return {"total": len(lines), "logs": lines}
