from __future__ import annotations
import logging
logger = logging.getLogger("myeonri-api")

from pydantic import BaseModel, Field


# ── 사주 계산 요청/응답 ──
class SajuRequest(BaseModel):
    year: int
    month: int
    day: int
    hour: int = Field(default=12, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    calendar: str = Field(default="solar", pattern="^(solar|lunar)$")
    gender: str | None = Field(default=None, description="M/F — 대운 계산용 (선택)")
    nickname: str | None = Field(default=None, description="프로필 닉네임 (선택)")


class YongsinInfo(BaseModel):
    ohaeng: str = ""
    reason: str = ""
    candidates: list[str] = []
    day_strength: str = ""  # 신강/신약
    day_strength_score: float = 0.0


class GyeokgukInfo(BaseModel):
    name: str = ""
    month_stem_sibsin: str = ""
    month_stem: str = ""
    month_branch: str = ""
    description: str = ""


class DaewoonEntry(BaseModel):
    order: int
    age_start: int
    age_end: int
    gan: str
    ji: str
    gan_hangul: str = ""
    ji_hangul: str = ""
    gan_sibsin: str = ""
    ji_sibsin: str = ""
    element: str = ""


class SajuResponse(BaseModel):
    hanja: dict
    hangeul: dict
    sibsin: dict
    yang: dict
    eum: dict
    hour: str
    # ── 원국 분석 (옵셔널 — 백워드 호환) ──
    ohaeng: dict | None = None       # 5개 오행 분포 {木: 1.6, 火: 0.4, ...}
    yongsin: YongsinInfo | None = None  # 용신
    gyeokguk: GyeokgukInfo | None = None  # 격국
    daewoon: list[DaewoonEntry] | None = None  # 대운 (gender 있을 때만)
    # ── ssaju 통합 객체 (FE가 기대하는 구조, 2026-06-26 추가) ──
    ssaju: dict | None = None
    input: dict | None = None


# ── 사용자 (portal-idp 전환 2026-07-20) ──
# portal_id: portal-idp JWT의 sub (UUID)
# google_id: 기존 Google OAuth ID (하위 호환, portal_id 우선)
class UserCheckRequest(BaseModel):
    portal_id: str | None = None
    google_id: str | None = None


class UserSaveRequest(BaseModel):
    portal_id: str | None = None
    google_id: str | None = None
    email: str = ""
    name: str = ""


class UserResponse(BaseModel):
    found: bool
    user: dict | None = None


class SajuProfileResponse(BaseModel):
    id: int
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int | None = None
    birth_minute: int | None = None
    gender: str | None = None
    calendar: str | None = None
    saju_data: dict | None = None
    is_primary: bool
