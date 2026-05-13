"""
천간(Heavenly Stems) 및 지지(Earthly Branches) 데이터
DB 테이블 조회 + 메모리 캐시
앱 startup 시 load*() 호출 → 이후 sync 접근 가능
"""

from __future__ import annotations

import logging

logger = logging.getLogger("myeonri-api")

# ── 메모리 캐시 ──
_heavenly_stems: list[dict] | None = None
_heavenly_by_hanja: dict | None = None
_heavenly_by_index: dict | None = None

_earthly_branches: list[dict] | None = None
_earthly_by_hanja: dict | None = None
_earthly_by_index: dict | None = None


async def load_heavenly_stems() -> list[dict]:
    """DB에서 천간 데이터 로드 (메모리 캐시, 중복 로드 방지)"""
    global _heavenly_stems, _heavenly_by_hanja, _heavenly_by_index
    if _heavenly_stems is not None:
        return _heavenly_stems

    from app.core.database import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT idx, hanja, hangul, element, yinyang FROM heavenly_stems ORDER BY idx"
            )
            rows = await cur.fetchall()

    _heavenly_stems = [
        {"index": r[0], "hanja": r[1], "hangul": r[2], "element": r[3], "yinyang": r[4]}
        for r in rows
    ]
    _heavenly_by_hanja = {s["hanja"]: s for s in _heavenly_stems}
    _heavenly_by_index = {s["index"]: s for s in _heavenly_stems}
    logger.info(f"Loaded {len(_heavenly_stems)} heavenly stems from DB")
    return _heavenly_stems


async def load_earthly_branches() -> list[dict]:
    """DB에서 지지 데이터 로드 (메모리 캐시, 중복 로드 방지)"""
    global _earthly_branches, _earthly_by_hanja, _earthly_by_index
    if _earthly_branches is not None:
        return _earthly_branches

    from app.core.database import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT idx, hanja, hangul, element, yinyang, zodiac FROM earthly_branches ORDER BY idx"
            )
            rows = await cur.fetchall()

    _earthly_branches = [
        {"index": r[0], "hanja": r[1], "hangul": r[2], "element": r[3], "yinyang": r[4], "zodiac": r[5]}
        for r in rows
    ]
    _earthly_by_hanja = {b["hanja"]: b for b in _earthly_branches}
    _earthly_by_index = {b["index"]: b for b in _earthly_branches}
    logger.info(f"Loaded {len(_earthly_branches)} earthly branches from DB")
    return _earthly_branches


# ── Sync getter (캐시 로드 후 호출 가능) ──


def get_heavenly_sync() -> list[dict]:
    """캐시된 천간 데이터 반환 (sync, startup 후 사용)"""
    if _heavenly_stems is None:
        raise RuntimeError("heavenly_stems not loaded. Call load_heavenly_stems() on startup")
    return _heavenly_stems


def get_heavenly_by_hanja_sync() -> dict:
    if _heavenly_by_hanja is None:
        raise RuntimeError("heavenly data not loaded. Call load_heavenly_stems() on startup")
    return _heavenly_by_hanja


def get_heavenly_by_index_sync() -> dict:
    if _heavenly_by_index is None:
        raise RuntimeError("heavenly data not loaded. Call load_heavenly_stems() on startup")
    return _heavenly_by_index


def get_earthly_sync() -> list[dict]:
    if _earthly_branches is None:
        raise RuntimeError("earthly data not loaded. Call load_earthly_branches() on startup")
    return _earthly_branches


def get_earthly_by_hanja_sync() -> dict:
    if _earthly_by_hanja is None:
        raise RuntimeError("earthly data not loaded. Call load_earthly_branches() on startup")
    return _earthly_by_hanja


def get_earthly_by_index_sync() -> dict:
    if _earthly_by_index is None:
        raise RuntimeError("earthly data not loaded. Call load_earthly_branches() on startup")
    return _earthly_by_index


# ── Async getter (최초 로드 시 DB 조회) ──


async def get_heavenly_by_hanja() -> dict:
    if _heavenly_by_hanja is None:
        await load_heavenly_stems()
    return _heavenly_by_hanja


async def get_heavenly_by_index() -> dict:
    if _heavenly_by_index is None:
        await load_heavenly_stems()
    return _heavenly_by_index


async def get_earthly_by_hanja() -> dict:
    if _earthly_by_hanja is None:
        await load_earthly_branches()
    return _earthly_by_hanja


async def get_earthly_by_index() -> dict:
    if _earthly_by_index is None:
        await load_earthly_branches()
    return _earthly_by_index


async def get_all_heavenly() -> list[dict]:
    if _heavenly_stems is None:
        await load_heavenly_stems()
    return _heavenly_stems


async def get_all_earthly() -> list[dict]:
    if _earthly_branches is None:
        await load_earthly_branches()
    return _earthly_branches


# ── 오행 순환 (상생/상극) — sync 함수, DB 불필요 ──

ELEMENT_CYCLE = ["목", "화", "토", "금", "수"]
ELEMENT_INDEX = {e: i for i, e in enumerate(ELEMENT_CYCLE)}


def get_generated(element: str) -> str:
    """상생: 내가 낳는 것 (목→화→토→금→수→목)"""
    return ELEMENT_CYCLE[(ELEMENT_INDEX[element] + 1) % 5]


def get_generator(element: str) -> str:
    """피생: 나를 낳아주는 것 (수→금→토→화→목→수)"""
    return ELEMENT_CYCLE[(ELEMENT_INDEX[element] - 1) % 5]


def get_controlled(element: str) -> str:
    """상극: 내가 제어하는 것 (목→토→수→화→금→목)"""
    return ELEMENT_CYCLE[(ELEMENT_INDEX[element] + 2) % 5]


def get_controller(element: str) -> str:
    """피극: 나를 제어하는 것 (금→화→수→토→목→금)"""
    return ELEMENT_CYCLE[(ELEMENT_INDEX[element] - 2) % 5]
