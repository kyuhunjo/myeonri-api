"""
궁합(Compatibility) 계산 — DB 캐시된 데이터 사용 (sync)
"""

from __future__ import annotations

from app.utils.constants import (
    get_heavenly_by_hanja_sync,
    get_earthly_by_hanja_sync,
    get_generated,
    get_generator,
)


def calc_compatibility(saju_a: dict, saju_b: dict) -> dict:
    """두 사람의 사주 데이터로 궁합 점수와 해설 계산"""
    heavenly = get_heavenly_by_hanja_sync()
    earthly = get_earthly_by_hanja_sync()

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

    stem_info_a = heavenly.get(day_stem_a, {})
    stem_info_b = heavenly.get(day_stem_b, {})
    branch_info_a = earthly.get(day_branch_a, {})
    branch_info_b = earthly.get(day_branch_b, {})

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
