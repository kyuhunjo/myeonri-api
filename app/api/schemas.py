from __future__ import annotations

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
    birth_year: int | None = None
    birth_month: int | None = None
    birth_day: int | None = None
    birth_hour: int | None = None
    birth_minute: int | None = None
    gender: str = "남"
    calendar: str = "solar"


class UserResponse(BaseModel):
    found: bool
    user: dict | None = None
