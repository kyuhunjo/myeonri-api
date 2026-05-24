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
                "SELECT id, han_char, element, yin_yang, korean FROM heavenly_stems ORDER BY id"
            )
            rows = await cur.fetchall()

    _heavenly_stems = [
        {"index": r[0] - 1, "hanja": r[1], "hangul": r[4], "element": r[2], "yinyang": r[3]}
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
                "SELECT id, han_char, element, yin_yang, korean FROM earthly_branches ORDER BY id"
            )
            rows = await cur.fetchall()

    _earthly_branches = [
        {"index": r[0] - 1, "hanja": r[1], "hangul": r[4], "element": r[2], "yinyang": r[3], "zodiac": ["쥐","소","호랑이","토끼","용","뱀","말","양","원숭이","닭","개","돼지"][r[0] - 1]}
        for r in rows
    ]
    _earthly_by_hanja = {b["hanja"]: b for b in _earthly_branches}
    _earthly_by_index = {b["index"]: b for b in _earthly_branches}
    logger.info(f"Loaded {len(_earthly_branches)} earthly branches from DB")
    return _earthly_branches


# ── 하드코딩 폴백 데이터 (startup 실패 시 사용) ──
_FALLBACK_HEAVENLY = [
    {"index": 0, "hanja": "甲", "hangul": "갑", "element": "목", "yinyang": "양"},
    {"index": 1, "hanja": "乙", "hangul": "을", "element": "목", "yinyang": "음"},
    {"index": 2, "hanja": "丙", "hangul": "병", "element": "화", "yinyang": "양"},
    {"index": 3, "hanja": "丁", "hangul": "정", "element": "화", "yinyang": "음"},
    {"index": 4, "hanja": "戊", "hangul": "무", "element": "토", "yinyang": "양"},
    {"index": 5, "hanja": "己", "hangul": "기", "element": "토", "yinyang": "음"},
    {"index": 6, "hanja": "庚", "hangul": "경", "element": "금", "yinyang": "양"},
    {"index": 7, "hanja": "辛", "hangul": "신", "element": "금", "yinyang": "음"},
    {"index": 8, "hanja": "壬", "hangul": "임", "element": "수", "yinyang": "양"},
    {"index": 9, "hanja": "癸", "hangul": "계", "element": "수", "yinyang": "음"},
]

_FALLBACK_EARTHLY = [
    {"index": 0, "hanja": "子", "hangul": "자", "element": "수", "yinyang": "양", "zodiac": "쥐"},
    {"index": 1, "hanja": "丑", "hangul": "축", "element": "토", "yinyang": "음", "zodiac": "소"},
    {"index": 2, "hanja": "寅", "hangul": "인", "element": "목", "yinyang": "양", "zodiac": "호랑이"},
    {"index": 3, "hanja": "卯", "hangul": "묘", "element": "목", "yinyang": "음", "zodiac": "토끼"},
    {"index": 4, "hanja": "辰", "hangul": "진", "element": "토", "yinyang": "양", "zodiac": "용"},
    {"index": 5, "hanja": "巳", "hangul": "사", "element": "화", "yinyang": "음", "zodiac": "뱀"},
    {"index": 6, "hanja": "午", "hangul": "오", "element": "화", "yinyang": "양", "zodiac": "말"},
    {"index": 7, "hanja": "未", "hangul": "미", "element": "토", "yinyang": "음", "zodiac": "양"},
    {"index": 8, "hanja": "申", "hangul": "신", "element": "금", "yinyang": "양", "zodiac": "원숭이"},
    {"index": 9, "hanja": "酉", "hangul": "유", "element": "금", "yinyang": "음", "zodiac": "닭"},
    {"index": 10, "hanja": "戌", "hangul": "술", "element": "토", "yinyang": "양", "zodiac": "개"},
    {"index": 11, "hanja": "亥", "hangul": "해", "element": "수", "yinyang": "양", "zodiac": "돼지"},
]


# ── Sync getter (캐시 로드 후 호출 가능, fallback 있음) ──


def get_heavenly_sync() -> list[dict]:
    """캐시된 천간 데이터 반환 (없으면 fallback)"""
    if _heavenly_stems is not None:
        return _heavenly_stems
    _init_fallback()
    return _heavenly_stems


def get_heavenly_by_hanja_sync() -> dict:
    if _heavenly_by_hanja is not None:
        return _heavenly_by_hanja
    _init_fallback()
    return _heavenly_by_hanja


def get_heavenly_by_index_sync() -> dict:
    if _heavenly_by_index is not None:
        return _heavenly_by_index
    _init_fallback()
    return _heavenly_by_index


def get_earthly_sync() -> list[dict]:
    if _earthly_branches is not None:
        return _earthly_branches
    _init_fallback()
    return _earthly_branches


def get_earthly_by_hanja_sync() -> dict:
    if _earthly_by_hanja is not None:
        return _earthly_by_hanja
    _init_fallback()
    return _earthly_by_hanja


def get_earthly_by_index_sync() -> dict:
    if _earthly_by_index is not None:
        return _earthly_by_index
    _init_fallback()
    return _earthly_by_index


def _init_fallback():
    """캐시가 없으면 하드코딩 fallback 데이터로 초기화"""
    global _heavenly_stems, _heavenly_by_hanja, _heavenly_by_index
    global _earthly_branches, _earthly_by_hanja, _earthly_by_index
    if _heavenly_stems is None:
        _heavenly_stems = _FALLBACK_HEAVENLY
        _heavenly_by_hanja = {s["hanja"]: s for s in _FALLBACK_HEAVENLY}
        _heavenly_by_index = {s["index"]: s for s in _FALLBACK_HEAVENLY}
        logger.warning("Using fallback heavenly stems (DB not loaded)")
    if _earthly_branches is None:
        _earthly_branches = _FALLBACK_EARTHLY
        _earthly_by_hanja = {b["hanja"]: b for b in _FALLBACK_EARTHLY}
        _earthly_by_index = {b["index"]: b for b in _FALLBACK_EARTHLY}
        logger.warning("Using fallback earthly branches (DB not loaded)")


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
