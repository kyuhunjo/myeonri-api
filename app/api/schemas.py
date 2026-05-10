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


class SajuResponse(BaseModel):
    hanja: dict
    hangeul: dict
    sibsin: dict
    yang: dict
    eum: dict
    hour: str


# ── 사용자 ──
class UserCheckRequest(BaseModel):
    google_id: str


class UserSaveRequest(BaseModel):
    google_id: str
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
