"""
사주 계산 엔진 (Saju Calculation Engine)
— 천간/지지 데이터는 DB에서 로드 (앱 startup 시 캐시)
— 오행 순환 함수는 내장

원국 분석 기능 (v2, 2026-06-24):
  - calc_ohaeng: 5오행 분포 (천간+지지+지장간 가중치)
  - _day_stem_strength: 일간 강약 점수 (월령득지 + 십신)
  - calc_yongsin: 용신 (신강/신약별 추천 오행)
  - calc_gyeokguk: 격국 (월간 십신 기준)
  - calc_daewoon: 대운 (순역 + 10년 단위 8개)
"""

import logging
logger = logging.getLogger("myeonri-saju")

from app.utils.constants import (
    get_heavenly_sync,
    get_heavenly_by_hanja_sync,
    get_heavenly_by_index_sync,
    get_earthly_sync,
    get_earthly_by_hanja_sync,
    get_earthly_by_index_sync,
    ELEMENT_CYCLE,
    ELEMENT_INDEX,
    get_generated,
    get_generator,
    get_controlled,
    get_controller,
)

# ── 오행 매핑 ──
# 기존 get_generated/get_controlled 등 상수 함수는 한글 오행("목"/"화"/"토"/"금"/"수")을 받음
# → 내부 계산용은 한글로 통일
ELEMENT_HANJA_TO_HANGUL = {
    "木": "목", "火": "화", "土": "토", "金": "금", "水": "수",
}
ELEMENT_HANGUL_TO_HANJA = {v: k for k, v in ELEMENT_HANJA_TO_HANGUL.items()}

# 천간/지지 한자 → 오행 (한글)
STEM_ELEMENT = {
    "甲": "목", "乙": "목", "丙": "화", "丁": "화", "戊": "토",
    "己": "토", "庚": "금", "辛": "금", "壬": "수", "癸": "수",
}
BRANCH_ELEMENT = {
    "子": "수", "丑": "토", "寅": "목", "卯": "목", "辰": "토", "巳": "화",
    "午": "화", "未": "토", "申": "금", "酉": "금", "戌": "토", "亥": "수",
}
# 지지 장간(고유 오행) — 일부 지지는 지장간 본기가 오행 표기와 다름
# 여기선 지장간 본기 기준: 子(수/癸), 丑(토/己), 寅(목/甲), 卯(목/乙),
# 辰(토/戊), 巳(화/丙), 午(화/丁), 未(토/己), 申(금/庚), 酉(금/辛),
# 戌(토/戊), 亥(수/壬) — BRANCH_ELEMENT와 일치
BRANCH_MAIN_STEM = {
    "子": "癸", "丑": "己", "寅": "甲", "卯": "乙", "辰": "戊", "巳": "丙",
    "午": "丁", "未": "己", "申": "庚", "酉": "辛", "戌": "戊", "亥": "壬",
}
# 장간 지장간 (중기/여기) — 일간 강약 판정에 사용
BRANCH_HIDDEN_STEMS = {
    "子": ["癸"],
    "丑": ["己", "癸", "辛"],
    "寅": ["甲", "丙", "戊"],
    "卯": ["乙"],
    "辰": ["戊", "乙", "癸"],
    "巳": ["丙", "戊", "庚"],
    "午": ["丁", "己"],
    "未": ["己", "丁", "乙"],
    "申": ["庚", "壬", "戊"],
    "酉": ["辛"],
    "戌": ["戊", "辛", "丁"],
    "亥": ["壬", "甲"],
}
# 월지 절기 시작 일수 (간이 버전 — 다음 절기까지 일수 계산용)
# 실제 만세력 DB의 cd_hterms/cd_kterms 값을 사용하면 더 정확하지만,
# 여기선 평균 절기일(소서/경칩 등) 기반의 근사치 사용
MONTH_BRANCH_BY_MONTH = {
    1: "丑", 2: "寅", 3: "卯", 4: "辰", 5: "巳", 6: "午",
    7: "未", 8: "申", 9: "酉", 10: "戌", 11: "亥", 12: "子",
}
# 양력 기준 절기 평균 시작일 (근사) — 다음 절기 계산용
SOLAR_TERM_APPROX = {
    1: 6, 2: 4, 3: 6, 4: 5, 5: 6, 6: 6,
    7: 7, 8: 8, 9: 8, 10: 8, 11: 7, 12: 7,
}
# 12운성 (十二運星) — 일간 기준 각 지지의 에너지 강약
# 일간 甲 기준의 12운성 (다른 일간은 순환)
LIFE_STAGES_BY_DAY_STEM = {
    "甲": ["長生","沐浴","冠帶","臨官","帝旺","衰","病","死","墓","絶","胎","養"],
    "乙": ["絶","胎","養","長生","沐浴","冠帶","臨官","帝旺","衰","病","死","墓"],
    "丙": ["胎","養","長生","沐浴","冠帶","臨官","帝旺","衰","病","死","墓","絶"],
    "丁": ["墓","絶","胎","養","長生","沐浴","冠帶","臨官","帝旺","衰","病","死"],
    "戊": ["胎","養","長生","沐浴","冠帶","臨官","帝旺","衰","病","死","墓","絶"],
    "己": ["墓","絶","胎","養","長生","沐浴","冠帶","臨官","帝旺","衰","病","死"],
    "庚": ["死","墓","絶","胎","養","長生","沐浴","冠帶","臨官","帝旺","衰","病"],
    "辛": ["病","死","墓","絶","胎","養","長生","沐浴","冠帶","臨官","帝旺","衰"],
    "壬": ["帝旺","衰","病","死","墓","絶","胎","養","長生","沐浴","冠帶","臨官"],
    "癸": ["衰","病","死","墓","絶","胎","養","長生","沐浴","冠帶","臨官","帝旺"],
}
BRANCH_ORDER = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]
STEM_ORDER = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]


def _branch_index(branch_hanja: str) -> int:
    try:
        return BRANCH_ORDER.index(branch_hanja)
    except ValueError:
        return -1


def _stem_index(stem_hanja: str) -> int:
    try:
        return STEM_ORDER.index(stem_hanja)
    except ValueError:
        return -1

# ── sync alias (기존 import 호환) ──
HEAVENLY_STEMS = get_heavenly_sync
HEAVENLY_BY_HANJA = get_heavenly_by_hanja_sync
HEAVENLY_BY_INDEX = get_heavenly_by_index_sync
EARTHLY_BRANCHES = get_earthly_sync
EARTHLY_BY_HANJA = get_earthly_by_hanja_sync
EARTHLY_BY_INDEX = get_earthly_by_index_sync


# ── 십신 ──


def get_sibsin(day_stem_hanja: str, target_stem_hanja: str) -> str:
    """십신(十神) 계산 — 천간 vs 천간"""
    heavenly = HEAVENLY_BY_HANJA()
    day = heavenly[day_stem_hanja]
    target = heavenly[target_stem_hanja]

    same_element = day["element"] == target["element"]
    same_yinyang = day["yinyang"] == target["yinyang"]

    if same_element:
        return "비견" if same_yinyang else "겁재"
    if get_generated(day["element"]) == target["element"]:
        return "식신" if same_yinyang else "상관"
    if get_generator(day["element"]) == target["element"]:
        return "편인" if same_yinyang else "정인"
    if get_controlled(day["element"]) == target["element"]:
        return "편재" if same_yinyang else "정재"
    if get_controller(day["element"]) == target["element"]:
        return "편관" if same_yinyang else "정관"
    return ""


def get_sibsin_for_branch(day_stem_hanja: str, branch_hanja: str) -> str:
    """십신 계산 — 일간 vs 지지 (지지의 오행 기준)"""
    heavenly = HEAVENLY_BY_HANJA()
    earthly = EARTHLY_BY_HANJA()
    day = heavenly[day_stem_hanja]
    branch = earthly[branch_hanja]

    same_element = day["element"] == branch["element"]
    same_yinyang = day["yinyang"] == branch["yinyang"]

    if same_element:
        return "비견" if same_yinyang else "겁재"
    if get_generated(day["element"]) == branch["element"]:
        return "식신" if same_yinyang else "상관"
    if get_generator(day["element"]) == branch["element"]:
        return "편인" if same_yinyang else "정인"
    if get_controlled(day["element"]) == branch["element"]:
        return "편재" if same_yinyang else "정재"
    if get_controller(day["element"]) == branch["element"]:
        return "편관" if same_yinyang else "정관"
    return ""


# ── 시간/사주 계산 ──


def get_branch_by_hour(hour: int, minute: int = 0) -> int:
    """시간 → 지지 인덱스"""
    total_minutes = hour * 60 + minute
    if total_minutes >= 23 * 60 or total_minutes < 1 * 60:
        return 0
    return ((total_minutes - 60) // 120) + 1


def apply_korea_local_mean_time(hour: int, minute: int = 0) -> tuple[int, int]:
    """한국 태양시 보정 (동경 135도 기준, 표준시 -30분)

    대한민국 표준시는 동경 127.5도를 기준으로 하지만, 동경 135도(일본/한국 전통 태양시)와
    차이가 있어 사주 시주 계산에서는 약 30분을 빼는 게 정확.

    예: 14:30 입력 → 보정 후 14:00 → 辛未시 (13:30~15:30)
        12:30 입력 → 보정 후 12:00 → 午시 (11:30~13:30)
    """
    total = hour * 60 + minute
    adjusted = max(0, total - 30)
    return adjusted // 60, adjusted % 60


def get_siju_stem(day_stem_index: int, branch_index: int) -> int:
    """시천간 계산"""
    start_map = [0, 2, 4, 6, 8]
    start = start_map[day_stem_index % 5]
    return (start + branch_index) % 10


def calculate_saju_from_calenda(
    calenda_row: dict,
    hour: int,
    minute: int,
    gender: str | None = None,
    solar_year: int | None = None,
    solar_month: int | None = None,
    solar_day: int | None = None,
    apply_local_mean_time: bool = True,
    nickname: str | None = None,
):
    """만세력 DB 로우 + 시간(+성별) → 사주 계산 (원국 분석 + ssaju 통합)

    apply_local_mean_time=True 이면 한국 태양시 보정(-30분) 자동 적용.
    외부 응답에는 original_hour/original_minute 보존, hour/minute는 보정 후 실제 계산에 사용한 값.
    """
    # ── 한국 태양시 보정 (드인트 135도 기준, -30분) ──
    original_hour, original_minute = hour, minute
    if apply_local_mean_time:
        hour, minute = apply_korea_local_mean_time(hour, minute)

    heavenly_by_hanja = HEAVENLY_BY_HANJA()
    heavenly_by_index = HEAVENLY_BY_INDEX()
    earthly_by_index = EARTHLY_BY_INDEX()

    yeonju_hanja = calenda_row.get("cd_hyganjee", "")
    wolju_hanja = calenda_row.get("cd_hmganjee", "")
    ilju_hanja = calenda_row.get("cd_hdganjee", "")
    yeonju_hangul = calenda_row.get("cd_kyganjee", "")
    wolju_hangul = calenda_row.get("cd_kmganjee", "")
    ilju_hangul = calenda_row.get("cd_kdganjee", "")

    day_stem_hanja = ilju_hanja[0]

    branch_idx = get_branch_by_hour(hour, minute)
    day_stem_info = heavenly_by_hanja[day_stem_hanja]
    siju_stem_idx = get_siju_stem(day_stem_info["index"], branch_idx)

    siju_hanja = heavenly_by_index[siju_stem_idx]["hanja"] + earthly_by_index[branch_idx]["hanja"]
    siju_hangul = heavenly_by_index[siju_stem_idx]["hangul"] + earthly_by_index[branch_idx]["hangul"]

    pillars = {
        "yeonju": {"hanja": yeonju_hanja, "hangul": yeonju_hangul},
        "wolju": {"hanja": wolju_hanja, "hangul": wolju_hangul},
        "ilju": {"hanja": ilju_hanja, "hangul": ilju_hangul},
        "siju": {"hanja": siju_hanja, "hangul": siju_hangul},
    }

    sibsin = {}
    for key, pillar in pillars.items():
        gan = pillar["hanja"][0]
        ji = pillar["hanja"][1]
        if key == "ilju":
            sibsin[key] = {"gan": "나", "ji": get_sibsin_for_branch(day_stem_hanja, ji)}
        else:
            sibsin[key] = {
                "gan": get_sibsin(day_stem_hanja, gan),
                "ji": get_sibsin_for_branch(day_stem_hanja, ji),
            }

    result = {
        "hanja": {
            "yeonju": yeonju_hanja, "wolju": wolju_hanja,
            "ilju": ilju_hanja, "siju": siju_hanja,
        },
        "hangeul": {
            "yeonju": yeonju_hangul, "wolju": wolju_hangul,
            "ilju": ilju_hangul, "siju": siju_hangul,
        },
        "sibsin": sibsin,
        "yang": {
            "year": calenda_row.get("cd_sy"), "month": calenda_row.get("cd_sm"),
            "day": calenda_row.get("cd_sd"),
        },
        "eum": {
            "year": calenda_row.get("cd_ly"), "month": calenda_row.get("cd_lm"),
            "day": calenda_row.get("cd_ld"),
        },
        "hour": f"{hour:02d}:{minute:02d}",
    }

    # ── 원국 분석 (용신/격국/오행 분포) ──
    try:
        result["ohaeng"] = calc_ohaeng(result)
        result["yongsin"] = calc_yongsin(result)
        result["gyeokguk"] = calc_gyeokguk(result)
    except Exception as exc:
        logger.warning(f"원국 분석 일부 실패 (일간={day_stem_hanja}): {exc}")
        result.setdefault("ohaeng", {"木": 0, "火": 0, "土": 0, "金": 0, "水": 0})
        result.setdefault("yongsin", {"ohaeng": "", "reason": "분석 불가"})
        result.setdefault("gyeokguk", "")

    # ── 대운 (gender + 생년월일 모두 있을 때) ──
    daewoon_list = []
    daewoon_info = {"list": [], "current": None, "startAge": None}
    if gender and solar_year is not None and solar_month is not None and solar_day is not None:
        try:
            daewoon_list = calc_daewoon(result, gender, solar_year, solar_month, solar_day)
            result["daewoon"] = daewoon_list
            if daewoon_list:
                daewoon_info["list"] = daewoon_list
                daewoon_info["startAge"] = daewoon_list[0].get("age_start")
                # 현재 나이 기준 현재 대운
                from datetime import date
                today = date.today()
                current_age = today.year - solar_year - (
                    1 if (today.month, today.day) < (solar_month, solar_day) else 0
                )
                cur = next((x for x in daewoon_list if x["age_start"] <= current_age <= x["age_end"]), None)
                if cur:
                    daewoon_info["current"] = cur
        except Exception as exc:
            logger.warning(f"대운 계산 실패: {exc}")
            result["daewoon"] = []
    else:
        # gender 없어도 키는 유지 (백워드 호환: 빈 리스트)
        result.setdefault("daewoon", [])

    # ── ssaju 통합 객체 (FE 사주결과 컴포넌트가 참조) ──
    try:
        ssaju_obj = _build_ssaju_object(
            result, day_stem_hanja, daewoon_info,
            solar_year, solar_month, solar_day, hour, minute, gender, nickname,
        )
        result["ssaju"] = ssaju_obj
    except Exception as exc:
        logger.warning(f"ssaju 통합 객체 생성 실패: {exc}")
        result["ssaju"] = {"pillars": {}, "pillarDetails": {}, "tenGods": {}, "stages12": {}, "sals": {}, "gongmang": None, "branchRelations": {}, "stemRelations": {}, "daeun": daewoon_info, "fiveElements": {}}

    # ── input 메타 (FE 형식) ──
    result["input"] = {
        "year": solar_year or calenda_row.get("cd_sy"),
        "month": solar_month or calenda_row.get("cd_sm"),
        "day": solar_day or calenda_row.get("cd_sd"),
        "hour": original_hour,
        "minute": original_minute,
        "hour_adjusted": hour,
        "minute_adjusted": minute,
        "gender": gender,
        "calendar": "solar",
        "nickname": nickname or "",
        "apply_local_mean_time": apply_local_mean_time,
    }

    return result


# ── 원국 분석 (일간 강약 / 용신 / 격국 / 대운 / 오행 분포) ──


def calc_ohaeng(saju_result: dict) -> dict:
    """5개 오행 분포 (응답은 한자 키) — 천간 + 지지 + 지장간 가중치 적용

    가중치: 천간 1.0, 지지 0.6, 지장간 본기 0.4 / 중기 0.2 / 여기 0.1
    """
    weights = {"stem": 1.0, "branch": 0.6, "hidden_main": 0.4, "hidden_mid": 0.2, "hidden_res": 0.1}
    counts_hangul = {"목": 0.0, "화": 0.0, "토": 0.0, "금": 0.0, "수": 0.0}

    hanja = saju_result.get("hanja", {})
    for key in ("yeonju", "wolju", "ilju", "siju"):
        pillar = hanja.get(key, "")
        if len(pillar) < 2:
            continue
        gan = pillar[0]
        ji = pillar[1]
        if gan in STEM_ELEMENT:
            counts_hangul[STEM_ELEMENT[gan]] += weights["stem"]
        if ji in BRANCH_ELEMENT:
            counts_hangul[BRANCH_ELEMENT[ji]] += weights["branch"]
        for i, hidden in enumerate(BRANCH_HIDDEN_STEMS.get(ji, [])):
            if hidden in STEM_ELEMENT:
                w = [weights["hidden_main"], weights["hidden_mid"], weights["hidden_res"]][min(i, 2)]
                counts_hangul[STEM_ELEMENT[hidden]] += w

    # 응답은 한자 오행 키로 (rag-console / 외부 합의 포맷)
    return {ELEMENT_HANGUL_TO_HANJA[k]: round(v, 2) for k, v in counts_hangul.items()}


def _day_stem_strength(saju_result: dict) -> dict:
    """일간 강약 점수 계산 (월령득지 + 비겁 + 인성 가산, 식상/재성/관성 감산)"""
    sibsin = saju_result.get("sibsin", {})

    # 월령득지: 일지 장간 본기가 일간을 도와주는 오행이면 가산
    ilju_hanja = saju_result.get("hanja", {}).get("ilju", "")
    day_stem = ilju_hanja[0] if ilju_hanja else ""
    day_elem = STEM_ELEMENT.get(day_stem, "")

    wolju_hanja = saju_result.get("hanja", {}).get("wolju", "")
    wolju_branch = wolju_hanja[1] if len(wolju_hanja) >= 2 else ""
    wolju_elem = BRANCH_ELEMENT.get(wolju_branch, "")

    # 일지가 일간의 뿌리(같은 오행/생조)인지
    ilju_branch = ilju_hanja[1] if len(ilju_hanja) >= 2 else ""
    ilju_elem = BRANCH_ELEMENT.get(ilju_branch, "")

    # 월지 본기 오행(계절)
    month_strength = 0
    season_strength = {
        "목": "春", "화": "夏", "토": "長夏", "금": "秋", "수": "冬",
    }
    cur_season = season_strength.get(wolju_elem, "")
    elem_season = season_strength.get(day_elem, "")
    if cur_season == elem_season:
        month_strength = 2  # 월령득지
    elif wolju_elem and get_generated(wolju_elem) == day_elem:
        month_strength = 1  # 생조
    elif wolju_elem and get_controller(wolju_elem) == day_elem:
        month_strength = -1  # 월령탈지

    # 십신 기반 가/감
    gan_counts = {"비겁": 0, "인성": 0, "식상": 0, "재성": 0, "관성": 0}
    for key in ("yeonju", "wolju", "siju"):  # ilju 제외
        gan = sibsin.get(key, {}).get("gan", "")
        if gan in ("비견", "겁재"):
            gan_counts["비겁"] += 1
        elif gan in ("정인", "편인"):
            gan_counts["인성"] += 1
        elif gan in ("식신", "상관"):
            gan_counts["식상"] += 1
        elif gan in ("정재", "편재"):
            gan_counts["재성"] += 1
        elif gan in ("정관", "편관"):
            gan_counts["관성"] += 1

    score = month_strength
    score += gan_counts["비겁"] * 1.5
    score += gan_counts["인성"] * 1.2
    score -= gan_counts["식상"] * 0.6
    score -= gan_counts["재성"] * 0.6
    score -= gan_counts["관성"] * 0.8

    # 일지 뿌리 보너스
    if ilju_elem == day_elem:
        score += 1.0
    elif get_generated(ilju_elem) == day_elem:
        score += 0.6

    strong = score >= 4.0
    return {
        "score": round(score, 2),
        "strong": strong,
        "weak": not strong,
        "ilgan_elem": day_elem,
        "wolji_elem": wolju_elem,
    }


def calc_yongsin(saju_result: dict) -> dict:
    """용신(用神) 계산 — 일간 강약에 따라 균형에 필요한 오행 산출

    - 신강: 식상 > 재성 > 관성 중 약한 것 우선 (기신은 인성/비겁)
    - 신약: 인성 > 비겁 중 약한 것 우선 (기신은 식상/재성/관성)
    """
    strength = _day_stem_strength(saju_result)
    day_elem = strength["ilgan_elem"]

    ohaeng = saju_result.get("ohaeng", {})
    # 가장 약한 오행 (보조 제외 일간 오행)
    filtered = {k: v for k, v in ohaeng.items() if k != day_elem}

    if strength["strong"]:
        # 신강 → 식상/재성/관성 순으로 필요한 오행
        primary = get_generated(day_elem)      # 식상 (한글)
        secondary = get_controlled(day_elem)    # 재성
        tertiary = get_controller(day_elem)     # 관성
        day_h = ELEMENT_HANGUL_TO_HANJA[day_elem]
        pri_h = ELEMENT_HANGUL_TO_HANJA[primary]
        reason = (
            f"일간({day_h})이 강하므로(점수 {strength['score']}) 일간이 에너지를 빼주는 "
            f"{pri_h}(식상)가 필요합니다."
        )
        return {
            "ohaeng": pri_h,
            "reason": reason,
            "candidates": [pri_h, ELEMENT_HANGUL_TO_HANJA[secondary], ELEMENT_HANGUL_TO_HANJA[tertiary]],
            "day_strength": "신강",
            "day_strength_score": strength["score"],
        }
    else:
        # 신약 → 인성(나를 생) > 비겁(나와 같음) 순
        primary = get_generator(day_elem)
        secondary = day_elem  # 비겁
        day_h = ELEMENT_HANGUL_TO_HANJA[day_elem]
        pri_h = ELEMENT_HANGUL_TO_HANJA[primary]
        sec_h = ELEMENT_HANGUL_TO_HANJA[secondary]
        reason = (
            f"일간({day_h})이 약하므로(점수 {strength['score']}) 일간을 도와주는 "
            f"{pri_h}(인성)가 필요합니다."
        )
        return {
            "ohaeng": pri_h,
            "reason": reason,
            "candidates": [pri_h, sec_h],
            "day_strength": "신약",
            "day_strength_score": strength["score"],
        }


def calc_gyeokguk(saju_result: dict) -> dict:
    """격국(格局) 계산 — 월지 + 월간 기반"""
    hanja = saju_result.get("hanja", {})
    wolju_hanja = hanja.get("wolju", "")
    if len(wolju_hanja) < 2:
        return {"name": "불명", "description": "월주 정보 부족"}

    wolgan = wolju_hanja[0]
    wolji = wolju_hanja[1]
    wolgan_elem = STEM_ELEMENT.get(wolgan, "")
    wolji_elem = BRANCH_ELEMENT.get(wolji, "")

    ilju_hanja = hanja.get("ilju", "")
    ilgan = ilju_hanja[0] if ilju_hanja else ""
    day_elem = STEM_ELEMENT.get(ilgan, "")

    # 격국 명 결정 (월간 기준)
    gan_to_gyeokguk = {
        # 정관/편관: 일간을 극함
        "정관": "정관격",
        "편관": "편관격(칠살격)",
        # 정인/편인: 일간을 생함
        "정인": "정인격",
        "편인": "편인격",
        # 식신/상관: 일간이 생함
        "식신": "식신격",
        "상관": "상관격",
        # 정재/편재: 일간이 극함
        "정재": "정재격",
        "편재": "편재격",
    }

    sibsin = saju_result.get("sibsin", {})
    wolgan_sibsin = sibsin.get("wolju", {}).get("gan", "")
    gyeokguk_name = gan_to_gyeokguk.get(wolgan_sibsin, "잡격")

    descriptions = {
        "정관격": "안정과 질서를 중시하며, 책임감이 강하고 사회적으로 인정받는 구조입니다.",
        "편관격(칠살격)": "강한 추진력과 개성이 있으며, 경쟁과 도전 속에서 성장하는 구조입니다.",
        "정인격": "학문과 지혜를 중시하며, 어머니·문서의 도움을 받아 성장하는 구조입니다.",
        "편인격": "독창적이고 직관력이 뛰어나며, 학문·기술·종교와 인연이 깊습니다.",
        "식신격": "먹거리·표현·재능으로 복을 누리며, 순수한 자기표현이 특징입니다.",
        "상관격": "뛰어난 표현력과 개성, 예술·언변 분야에서 빛을 발합니다.",
        "정재격": "안정적인 재물운, 성실한 노력으로 부를 쌓는 구조입니다.",
        "편재격": "활동적인 재물운, 투자·사업으로 큰 부를 추구하는 구조입니다.",
        "잡격": "정해진 격에 얽매이지 않는 자유로운 구조로, 다양한 재능이 있습니다.",
    }

    return {
        "name": gyeokguk_name,
        "month_stem_sibsin": wolgan_sibsin,
        "month_stem": wolgan,
        "month_branch": wolji,
        "description": descriptions.get(gyeokguk_name, ""),
    }


def calc_daewoon(
    saju_result: dict,
    gender: str,
    solar_year: int,
    solar_month: int,
    solar_day: int,
    count: int = 8,
) -> list[dict]:
    """대운(大運) 계산 — 10년 단위 운의 흐름

    순역 결정:
      남성 + 양년생 (양력 간지 연주 천간이 양) → 순행
      남성 + 음년생 → 역행
      여성 + 양년생 → 역행
      여성 + 음년생 → 순행

    시작 나이: 생일 → 다음/이전 절기까지 일수 ÷ 3
      순행 시 → 다음 절기까지
      역행 시 → 이전 절기까지
    """
    hanja = saju_result.get("hanja", {})
    yeonju = hanja.get("yeonju", "")
    if len(yeonju) < 1:
        return []

    yeon_gan = yeonju[0]
    yeon_yinyang = "양" if yeon_gan in ("甲", "丙", "戊", "庚", "壬") else "음"
    is_male = gender.lower() in ("m", "male", "남", "남자")

    # 순역 결정
    if is_male:
        forward = yeon_yinyang == "양"
    else:
        forward = yeon_yinyang == "음"

    # 시작 나이 계산 (절기까지 일수 ÷ 3, 올림)
    next_term_day = SOLAR_TERM_APPROX.get(solar_month, 6)
    if forward:
        # 다음 절기까지
        days_to_term = (next_term_day - solar_day) if solar_day < next_term_day else (30 + next_term_day - solar_day)
    else:
        # 이전 절기까지
        days_to_term = (solar_day - next_term_day) if solar_day >= next_term_day else (solar_day + 30 - next_term_day)

    start_age = max(1, (days_to_term + 2) // 3)

    # 대운 천간/지지: 월주에서 출발
    wolju = hanja.get("wolju", "")
    wolgan = wolju[0] if wolju else ""
    wolji = wolju[1] if len(wolju) >= 2 else ""

    wolgan_idx = _stem_index(wolgan)
    wolji_idx = _branch_index(wolji)

    daewoons = []
    for i in range(count):
        if forward:
            gan_idx = (wolgan_idx + 1 + i) % 10
            ji_idx = (wolji_idx + 1 + i) % 12
        else:
            gan_idx = (wolgan_idx - 1 - i) % 10
            ji_idx = (wolji_idx - 1 - i) % 12

        age_start = start_age + i * 10
        age_end = age_start + 9
        gan_hanja = STEM_ORDER[gan_idx]
        ji_hanja = BRANCH_ORDER[ji_idx]

        # 대운의 십신 (일간 기준)
        gan_sibsin = get_sibsin(saju_result["hanja"]["ilju"][0], gan_hanja)
        ji_sibsin = get_sibsin_for_branch(saju_result["hanja"]["ilju"][0], ji_hanja)

        daewoons.append({
            "order": i + 1,
            "age_start": age_start,
            "age_end": age_end,
            "gan": gan_hanja,
            "ji": ji_hanja,
            "gan_hangul": HEAVENLY_BY_HANJA()[gan_hanja]["hangul"],
            "ji_hangul": EARTHLY_BY_HANJA()[ji_hanja]["hangul"],
            "gan_sibsin": gan_sibsin,
            "ji_sibsin": ji_sibsin,
            "element": ELEMENT_HANGUL_TO_HANJA.get(STEM_ELEMENT[gan_hanja], STEM_ELEMENT[gan_hanja]),
        })

    return daewoons


# ── 궁합 ──


def calc_compatibility(saju_a: dict, saju_b: dict) -> dict:
    """두 사람의 사주 데이터로 궁합 점수와 해설 계산"""
    heavenly_by_hanja = HEAVENLY_BY_HANJA()
    earthly_by_hanja = EARTHLY_BY_HANJA()

    def _get_pillar(saju, key):
        hanja = saju.get("hanja", {}) if isinstance(saju.get("hanja"), dict) else {}
        return hanja.get(key, "")

    def _get_day_stem(saju):
        ilju = _get_pillar(saju, "ilju")
        return ilju[0] if ilju and len(ilju) >= 1 else ""

    def _get_day_branch(saju):
        ilju = _get_pillar(saju, "ilju")
        return ilju[1] if ilju and len(ilju) >= 2 else ""

    def _element_score(e1, e2):
        if e1 == e2:
            return 1
        if get_generated(e1) == e2 or get_generator(e1) == e2:
            return 3
        return -1

    day_stem_a = _get_day_stem(saju_a)
    day_stem_b = _get_day_stem(saju_b)
    day_branch_a = _get_day_branch(saju_a)
    day_branch_b = _get_day_branch(saju_b)

    stem_info_a = heavenly_by_hanja.get(day_stem_a, {})
    stem_info_b = heavenly_by_hanja.get(day_stem_b, {})
    branch_info_a = earthly_by_hanja.get(day_branch_a, {})
    branch_info_b = earthly_by_hanja.get(day_branch_b, {})

    stem_elem_a = stem_info_a.get("element", "")
    stem_elem_b = stem_info_b.get("element", "")
    branch_elem_a = branch_info_a.get("element", "")
    branch_elem_b = branch_info_b.get("element", "")

    score = 50
    score += _element_score(stem_elem_a, stem_elem_b) * 5
    score += _element_score(branch_elem_a, branch_elem_b) * 5
    score += _element_score(stem_elem_a, branch_elem_b) * 3
    score += _element_score(stem_elem_b, branch_elem_a) * 3

    LHA = {"子":"丑","丑":"子","寅":"亥","亥":"寅","卯":"戌","戌":"卯",
           "辰":"酉","酉":"辰","巳":"申","申":"巳","午":"未","未":"午"}
    CHUNG = {"子":"午","午":"子","丑":"未","未":"丑","寅":"申","申":"寅",
             "卯":"酉","酉":"卯","辰":"戌","戌":"辰","巳":"亥","亥":"巳"}
    if LHA.get(day_branch_a) == day_branch_b:
        score += 10
    elif CHUNG.get(day_branch_a) == day_branch_b:
        score -= 10

    SAMHAP = [{"申","子","辰"}, {"寅","午","戌"}, {"巳","酉","丑"}, {"亥","卯","未"}]
    for group in SAMHAP:
        if day_branch_a in group and day_branch_b in group:
            score += 5
            break

    score = max(0, min(100, score))

    if score >= 80:
        grade = "최상"
        desc = "두 사람의 기운이 매우 잘 맞습니다. 서로를 성장시키는 인연입니다."
    elif score >= 65:
        grade = "상"
        desc = "서로 보완해주는 좋은 궁합입니다. 대화와 이해가 중요합니다."
    elif score >= 50:
        grade = "중"
        desc = "무난한 궁합입니다. 서로 다른 점을 인정하고 존중하는 것이 필요합니다."
    elif score >= 35:
        grade = "하"
        desc = "에너지 방향이 달라 갈등이 생기기 쉽습니다. 서로에 대한 이해와 배려가 특히 중요합니다."
    else:
        grade = "최하"
        desc = "두 사람의 기운이 상충합니다. 극복하기 위해 많은 노력과 대화가 필요합니다."

    return {
        "score": score, "grade": grade, "summary": desc,
        "day_stem_a": day_stem_a, "day_stem_b": day_stem_b,
        "day_branch_a": day_branch_a, "day_branch_b": day_branch_b,
        "stem_element_a": stem_elem_a, "stem_element_b": stem_elem_b,
        "branch_element_a": branch_elem_a, "branch_element_b": branch_elem_b,
    }


# ────────────────────────────────────────────────────────────────────
# ssaju 통합 객체 (FE SajuResult.jsx가 기대하는 형식, 2026-06-26 추가)
# ────────────────────────────────────────────────────────────────────

# 12운성 표기 (한글)
LIFE_STAGE_NAMES = ["장생", "목욕", "관대", "건록", "제왕", "쇠", "병", "사", "묘", "절", "태", "양"]
# 12지지 × 일간 → 12운성 매핑 (위 LIFE_STAGES_BY_DAY_STEM dict와 동일 키 사용)
# 위 dict는 일간 기준으로 12지지 순서(子丑寅卯辰巳午未申酉戌亥)의 운성을 나열

# 지장간 정기/중기/여기 (3개 장간)
HIDDEN_STEMS_FM = {
    "子": {"정기": "癸"},
    "丑": {"정기": "己", "중기": "癸", "여기": "辛"},
    "寅": {"정기": "甲", "중기": "丙", "여기": "戊"},
    "卯": {"정기": "乙"},
    "辰": {"정기": "戊", "중기": "乙", "여기": "癸"},
    "巳": {"정기": "丙", "중기": "戊", "여기": "庚"},
    "午": {"정기": "丁", "중기": "己"},
    "未": {"정기": "己", "중기": "丁", "여기": "乙"},
    "申": {"정기": "庚", "중기": "壬", "여기": "戊"},
    "酉": {"정기": "辛"},
    "戌": {"정기": "戊", "중기": "辛", "여기": "丁"},
    "亥": {"정기": "壬", "중기": "甲"},
}

# 12살 (년지 기준 12지지 사이클)
# 년지가申일 때 → 申=정인(제1살), 酉=편인(제2살), 戌=식신(제3살), ...
# 순서: 년지=제1살, 년지+1=제2살, ...
# 즉 year_branch에서부터 0거리일 때 year_branch의 살이 나옴
# 12살 테이블 (12지지 고유 — 일간 무관 단순화 버전)
TWELVE_SALS_BY_BRANCH = {
    "申": "정인", "酉": "편인", "戌": "식신", "亥": "상관",
    "子": "제왕", "丑": "패덕", "寅": "역마", "卯": "도화",
    "辰": "겁재", "巳": "재성", "午": "정관", "未": "편관",
}
TWELVE_SALS_BY_YEAR_BRANCH = TWELVE_SALS_BY_BRANCH

# 특수 신살
SPECIAL_SALS_BY_DAY_STEM = {
    "甲": {"역마": "申", "도화": "卯", "양인": "卯"},
    "乙": {"역마": "巳", "도화": "寅", "양인": "辰"},
    "丙": {"역마": "寅", "도화": "酉", "양인": "午"},
    "丁": {"역마": "亥", "도화": "申", "양인": "未"},
    "戊": {"역마": "申", "도화": "卯", "양인": "午"},
    "己": {"역마": "巳", "도화": "寅", "양인": "未"},
    "庚": {"역마": "寅", "도화": "酉", "양인": "酉"},
    "辛": {"역마": "亥", "도화": "申", "양인": "戌"},
    "壬": {"역마": "申", "도화": "卯", "양인": "子"},
    "癸": {"역마": "巳", "도화": "寅", "양인": "丑"},
}

# 공망 (년일주의 납음/일진 기준 — 간단히 년간+일주로 계산)
# 실제로는 율리브/여명 등 다양한 규칙. 여기선 일주 기준 간단 매핑
GONGMANG_BY_DAY_PILLAR_INDEX = {
    # (year_branch_idx, day_branch_idx) → 공망 2지지
    # 너무 복잡하므로 년지/일지 기반 휴리스틱:
}

# 지지 관계 (12지지 충/형/파/해/육합/삼합/방합/원진)
SIX_HARMONY = {"子":"丑","丑":"子","寅":"亥","亥":"寅","卯":"戌","戌":"卯",
               "辰":"酉","酉":"辰","巳":"申","申":"巳","午":"未","未":"午"}
SIX_CLASH = {"子":"午","午":"子","丑":"未","未":"丑","寅":"申","申":"寅",
             "卯":"酉","酉":"卯","辰":"戌","戌":"辰","巳":"亥","亥":"巳"}
THREE_HARM = {"子":"申","申":"子","丑":"未","未":"丑","寅":"午","午":"寅",
              "卯":"酉","酉":"卯","辰":"戌","戌":"辰","巳":"亥","亥":"巳"}
SIX_BREAK = {"子":"酉","丑":"辰","寅":"亥","卯":"午","辰":"丑","巳":"申",
             "午":"卯","未":"戌","申":"巳","酉":"子","戌":"未","亥":"寅"}
SIX_PUNISH = {"子":"卯","丑":"戌","寅":"巳","卯":"子","辰":"辰","巳":"寅",
              "午":"午","未":"未","申":"亥","酉":"酉","戌":"丑","亥":"申"}
# 육해 (Six Harms / Six Harm) — 지지 간 해(害) 관계
SIX_HURT = {"子":"未","丑":"午","寅":"巳","卯":"辰","申":"亥","酉":"戌",
            "辰":"卯","巳":"寅","午":"丑","未":"子","戌":"酉","亥":"申"}
# 원진 (寅巳申 / 亥卯未 / 子午卯酉 / 辰戌丑未)
HURT = {"寅":"巳","巳":"申","申":"寅","亥":"未","未":"亥","亥":"卯","卯":"未",
        "子":"卯","卯":"子","子":"午","午":"子","午":"卯","卯":"午","子":"酉","酉":"子","午":"酉","酉":"午",
        "辰":"戌","戌":"辰","辰":"丑","丑":"辰","戌":"未","未":"戌","丑":"未","未":"丑","辰":"未","未":"辰","丑":"戌","戌":"丑"}
# 귀문 (간소화 — 년지+일지 쌍으로 일부만 정의)
GHOST_GATE = {
    ("子","丑"): ["寅","卯"],  # 예시 패턴 (실제로는 더 복잡)
}


def _hangul_of(stem_or_branch_hanja: str, kind: str) -> str:
    """천간/지지 한자 → 한글"""
    if kind == "stem":
        m = HEAVENLY_BY_HANJA()
    else:
        m = EARTHLY_BY_HANJA()
    return m.get(stem_or_branch_hanja, {}).get("hangul", "")


def _element_hangul(stem_or_branch_hanja: str, kind: str) -> str:
    """천간/지지 → 오행 한글"""
    if kind == "stem":
        return STEM_ELEMENT.get(stem_or_branch_hanja, "")
    return BRANCH_ELEMENT.get(stem_or_branch_hanja, "")


def calc_pillar_details(saju_result: dict) -> dict:
    """pillarDetails: 각 주(年/月/日/時)별 상세 정보

    FE 형식: { year: { stem, stemKo, branch, branchKo, element: {stem, branch}, hiddenStems: {정기, 중기, 여기} }, ... }
    내부 키(yeonju/wolju/ilju/siju) → FE 키(year/month/day/hour) 매핑
    """
    KEY_MAP = {"yeonju": "year", "wolju": "month", "ilju": "day", "siju": "hour"}
    hanja = saju_result.get("hanja", {})
    out = {}
    for internal_key, pillar_hanja in hanja.items():
        if len(pillar_hanja) < 2:
            continue
        fe_key = KEY_MAP.get(internal_key, internal_key)
        gan, ji = pillar_hanja[0], pillar_hanja[1]
        out[fe_key] = {
            "stem": gan,
            "stemKo": _hangul_of(gan, "stem"),
            "branch": ji,
            "branchKo": _hangul_of(ji, "branch"),
            "element": {
                "stem": _element_hangul(gan, "stem"),
                "branch": _element_hangul(ji, "branch"),
            },
            "hiddenStems": HIDDEN_STEMS_FM.get(ji, {"정기": ji and STEM_ORDER[(_branch_index(ji)+0)%10] or ""}),
        }
    return out


def calc_ten_gods(saju_result: dict) -> dict:
    """tenGods (FE 형식): 각 주별 천간/지지 십신

    FE 형식: { year: { stem: '겁재', branch: '정관' }, ... }
    일간은 { stem: '(일간)', branch: '편인' } 처럼 표시
    """
    KEY_MAP = {"yeonju": "year", "wolju": "month", "ilju": "day", "siju": "hour"}
    day_stem_hanja = saju_result["hanja"]["ilju"][0]
    hanja = saju_result.get("hanja", {})
    out = {}
    for internal_key, pillar_hanja in hanja.items():
        gan, ji = pillar_hanja[0], pillar_hanja[1]
        fe_key = KEY_MAP.get(internal_key, internal_key)
        if internal_key == "ilju":
            out[fe_key] = {"stem": "(일간)", "branch": get_sibsin_for_branch(day_stem_hanja, ji)}
        else:
            out[fe_key] = {
                "stem": get_sibsin(day_stem_hanja, gan),
                "branch": get_sibsin_for_branch(day_stem_hanja, ji),
            }
    return out


def calc_12_stages(saju_result: dict) -> dict:
    """12운성 (장생/목욕/관대/건록/제왕/쇠/병/사/묘/절/태/양)

    일간 기준 각 지지가 어떤 운성을 가지는지.
    """
    KEY_MAP = {"yeonju": "year", "wolju": "month", "ilju": "day", "siju": "hour"}
    day_stem = saju_result["hanja"]["ilju"][0]
    stages = LIFE_STAGES_BY_DAY_STEM.get(day_stem, [])
    if not stages:
        return {"bong": {}, "geo": {}}

    hanja = saju_result.get("hanja", {})
    bong = {}
    geo = {}

    for internal_key, pillar_hanja in hanja.items():
        if len(pillar_hanja) < 2:
            continue
        ji = pillar_hanja[1]
        idx = _branch_index(ji)
        if idx < 0:
            continue
        fe_key = KEY_MAP.get(internal_key, internal_key)
        bong[fe_key] = stages[idx]
        geo[fe_key] = stages[idx]

    return {"bong": bong, "geo": geo}


def calc_sals(saju_result: dict) -> dict:
    """신살: 12살(년지 기준 각 柱 지지의 거리 기반 살) + 특수 신살(역마/도화/양인)

    FE 형식: { year: { twelveSal: '겁재', specialSals: ['역마', '도화'] }, ... }

    12살 산출:
      - 12살 테이블 (TWELVE_SALS_BY_BRANCH)에서 각 柱 지지으 살을 직접 조회
      - 년지가 申이면: 申=정인, 酉=편인, 戌=식신, 亥=상관, 子=제왕, ...
      - 즉 TWELVE_SALS_BY_BRANCH은 고정 테이블 (실제 명리학에서는 일간 따라 결정되지만 단순화)
      - 이 테이블이 12살 그대로을고, 각 柱 지지의 살은 그 테이블에서 직접 lookup
    """
    KEY_MAP = {"yeonju": "year", "wolju": "month", "ilju": "day", "siju": "hour"}
    day_stem = saju_result["hanja"]["ilju"][0]
    sals_special_map = SPECIAL_SALS_BY_DAY_STEM.get(day_stem, {})

    hanja = saju_result.get("hanja", {})
    out = {}
    for internal_key, pillar_hanja in hanja.items():
        if len(pillar_hanja) < 2:
            continue
        ji = pillar_hanja[1]
        # 각 柱 지지가 12살 테이블에서 어느 살을 가지는지
        twelve = TWELVE_SALS_BY_BRANCH.get(ji, "")
        specials = [name for name, target in sals_special_map.items() if target == ji]
        fe_key = KEY_MAP.get(internal_key, internal_key)
        out[fe_key] = {
            "twelveSal": twelve,
            "specialSals": specials,
        }
    return out


def calc_gongmang(saju_result: dict) -> dict:
    """공망 (일주 기준 간단 매핑)

    실전에서는 60갑자 순환으로 결정. 여기선 일지 인덱스 기반 휴리스틱.
    일진 index = (year_stem_index * 6 + ...) 복잡하므로,
    일지 인덱스 mod 12로 2개 공망 지지 결정 (대략적):
      - 일지가 子(0) → 공망 辰戌
      - 일지가 丑(1) → 공망 巳亥
      - 일지가 寅(2) → 공망 午子
      - ...
    """
    day_branch = saju_result["hanja"]["ilju"][1]
    idx = _branch_index(day_branch)
    # (idx+4, idx+10) mod 12 = 공망 2개
    gong1 = BRANCH_ORDER[(idx + 4) % 12]
    gong2 = BRANCH_ORDER[(idx + 10) % 12]
    branches_hanja = [gong1, gong2]
    branches_ko = [_hangul_of(b, "branch") for b in branches_hanja]
    return {"branches": branches_hanja, "branchesKo": branches_ko}


def _find_partner(target_branch: str, pair_map: dict) -> str | None:
    """쌍방향 매핑에서 상대편 지지 찾기"""
    for k, v in pair_map.items():
        if k == target_branch:
            return v
        if v == target_branch:
            return k
    return None


def calc_branch_relations(saju_result: dict) -> dict:
    """지지 관계 11종: 충/형/파/해/육합/삼합/방합/반합/원진/귀문/지장간

    FE 형식: { 충: { year: '午', month: '子', ... }, 형: {...}, ... }
    """
    KEY_MAP = {"yeonju": "year", "wolju": "month", "ilju": "day", "siju": "hour"}
    hanja = saju_result.get("hanja", {})
    branches = {k: v[1] for k, v in hanja.items() if len(v) >= 2}
    branches_fe = {KEY_MAP.get(k, k): v for k, v in branches.items()}

    # 각 주(년/월/일/시)별로, 다른 주와의 관계 매핑
    def _build_relations_for_key(key, relation_map, label):
        result = {}
        my_branch = branches.get(key, "")
        if not my_branch:
            return {}
        partner = _find_partner(my_branch, relation_map)
        if partner:
            result[KEY_MAP.get(key, key)] = partner  # 충/형 등: 단순히 상대편 지지
        return result

    # 육합은 양방향, 나머지도 쌍방향
    relations = {
        "충": _build_relations_for_each(branches_fe, SIX_CLASH),
        "형": _build_relations_for_each(branches_fe, SIX_BREAK),
        "파": _build_relations_for_each(branches_fe, SIX_PUNISH),
        "해": _build_relations_for_each(branches_fe, SIX_HURT),
        "육합": _build_relations_for_each(branches_fe, SIX_HARMONY),
        "삼합": {},  # 삼합은 3개 조합이라 단순화
        "방합": {},
        "반합": {},
        "원진": _build_relations_for_each(branches_fe, HURT),
        "귀문": {},
        "지장간": {},
    }
    return relations


def _build_relations_for_each(branches: dict, pair_map: dict) -> dict:
    """각 주에 대해 상대편 지지 매핑 (양방향)"""
    out = {}
    for key, branch in branches.items():
        partner = _find_partner(branch, pair_map)
        if partner:
            out[key] = partner
    return out


def calc_stem_relations(saju_result: dict) -> dict:
    """천간 관계 (합/충)

    천간 5합: 甲己合土, 乙庚合金, 丙辛合水, 丁壬合木, 戊癸合火
    천간 4충: 甲庚冲, 乙辛冲, 丙壬冲, 丁癸冲
    """
    KEY_MAP = {"yeonju": "year", "wolju": "month", "ilju": "day", "siju": "hour"}
    STEM_SIX_HARM = {
        "甲":"己","己":"甲","乙":"庚","庚":"乙","丙":"辛","辛":"丙",
        "丁":"壬","壬":"丁","戊":"癸","癸":"戊",
    }
    STEM_FOUR_CLASH = {
        "甲":"庚","庚":"甲","乙":"辛","辛":"乙",
        "丙":"壬","壬":"丙","丁":"癸","癸":"丁",
    }
    hanja = saju_result.get("hanja", {})
    stems = {KEY_MAP.get(k, k): v[0] for k, v in hanja.items() if len(v) >= 1}

    out = {
        "합": _build_relations_for_each(stems, STEM_SIX_HARM),
        "충": _build_relations_for_each(stems, STEM_FOUR_CLASH),
    }
    return out


def calc_ohaeng_hangul(saju_result: dict) -> dict:
    """오행 분포 (한글 키 — FE SajuResult.jsx 형식)"""
    ohaeng = saju_result.get("ohaeng", {})
    # 한자 키 → 한글 키 매핑
    result = {}
    for k, v in ohaeng.items():
        ko = ELEMENT_HANJA_TO_HANGUL.get(k, k)
        result[ko] = v
    return result


def _build_ssaju_object(
    saju_result: dict,
    day_stem_hanja: str,
    daewoon_info: dict,
    solar_year: int | None,
    solar_month: int | None,
    solar_day: int | None,
    hour: int,
    minute: int,
    gender: str | None,
    nickname: str | None,
) -> dict:
    """FE SajuResult.jsx가 기대하는 ssaju 통합 객체"""
    day_branch = saju_result["hanja"]["ilju"][1] if len(saju_result["hanja"]["ilju"]) >= 2 else ""

    pillars_obj = {
        "year": saju_result["hangeul"]["yeonju"],
        "month": saju_result["hangeul"]["wolju"],
        "day": saju_result["hangeul"]["ilju"],
        "hour": saju_result["hangeul"]["siju"],
    }

    return {
        "pillars": pillars_obj,
        "pillarDetails": calc_pillar_details(saju_result),
        "tenGods": calc_ten_gods(saju_result),
        "stages12": calc_12_stages(saju_result),
        "dayStem": day_stem_hanja,
        "dayBranch": day_branch,
        "fiveElements": calc_ohaeng_hangul(saju_result),
        "sals": calc_sals(saju_result),
        "gongmang": calc_gongmang(saju_result),
        "branchRelations": calc_branch_relations(saju_result),
        "stemRelations": calc_stem_relations(saju_result),
        "daeun": daewoon_info,
    }
