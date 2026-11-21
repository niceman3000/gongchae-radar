"""사용자 조건(직렬·지역·자격증)과 공고 조건을 비교해 지원 상태를 정한다 (코드만, AI 호출 없음).

판정 규칙 (specs/001-recruitment-radar-mvp/data-model.md 7절)
  1. 명시된 필수조건 불충족이 하나라도 있으면 '지원 불가'
  2. 필수조건을 모두 충족하고 수동 확인 조건이 없으면 '지원 가능'
  3. 데이터가 없거나 전공 인정·대체 자격처럼 확정할 수 없으면 '애매'
  4. 데이터 부족을 '지원 가능'으로 처리하지 않는다

판정 대상은 사용자가 입력한 직렬·지역·자격증과 관련된 조건이다.
외국어 성적·병역처럼 사용자가 입력하지 않은 공통 조건은 상태에 넣지 않고
'공통 확인 사항'으로 따로 보여준다. 합격 가능성·순위·추천 점수는 만들지 않는다.
"""

from __future__ import annotations

import re

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

try:
    from src.certificates import keep_highest_grade, matches
except ModuleNotFoundError:
    from certificates import keep_highest_grade, matches

LABELS = {"eligible": "지원 가능", "ineligible": "지원 불가", "ambiguous": "애매"}
STATUS_ORDER = {"eligible": 0, "ambiguous": 1, "ineligible": 2}
REGIONS = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원",
           "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
REGION_ALIASES = {"전남광주": ["광주", "전남"], "광주전남": ["광주", "전남"], "광주·전남": ["광주", "전남"]}
FORBIDDEN_FIELDS = {"name", "phone", "email", "birth", "resident_number", "이름", "연락처", "생년월일"}


@dataclass(frozen=True)
class UserCondition:
    """한 브라우저 세션에서만 쓰는 조건. 개인 식별 정보는 받지 않는다."""

    track: str
    region: str  # '부산·울산'처럼 여러 시도를 '·'로 이어 쓸 수 있다
    certificates: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.track or not self.region:
            raise ValueError("직렬과 지역은 꼭 골라야 합니다.")

    @property
    def regions(self) -> list[str]:
        return expand_regions(self.region.split("·"))

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "UserCondition":
        extra = set(data) & FORBIDDEN_FIELDS
        if extra:
            raise ValueError(f"개인 식별 정보는 받지 않습니다: {sorted(extra)}")
        return cls(str(data["track"]), str(data["region"]), tuple(data.get("certificates") or ()))


@dataclass
class EligibilityResult:
    pair_id: str
    institution: str
    title: str
    deadline: str
    relevance: str  # match | region_mismatch | track_missing
    status: str | None
    label: str | None
    reasons: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    review_items: list[str] = field(default_factory=list)
    units: list[dict[str, Any]] = field(default_factory=list)
    bonus: list[dict[str, Any]] = field(default_factory=list)
    bonus_rule: str | None = None
    common_checks: list[str] = field(default_factory=list)


def expand_regions(values: Iterable[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        value = value.strip()
        for region in REGION_ALIASES.get(value, [value]):
            if region and region not in output:
                output.append(region)
    return output


def _applies(item: Mapping[str, Any], track: str, unit: str) -> bool:
    if item.get("track") and item["track"] != track:
        return False
    units = item.get("applicable_units") or []
    return not units or unit in units


def _check_unit(
    unit: Mapping[str, Any], track: str, certificates: tuple[str, ...], requirements: Mapping[str, Any]
) -> dict[str, Any]:
    """일반 모집단위 하나의 전공·자격증 요건 판정."""
    name = str(unit["name"])
    accepted = [
        item for item in requirements.get("certificates") or []
        if item.get("kind") in {"accepted", "required"} and _applies(item, track, name)
    ]
    majors = [item for item in requirements.get("majors") or [] if _applies(item, track, name)]

    # 필수 자격증(required)은 전공 조건보다 먼저 본다.
    # 11-20 마사회: 공고 전체 '전공·학력 제한 없음' 항목이 먼저 걸려, 전기 모집단위 필수 자격(전기기사)이 없어도 '지원 가능'이 됨
    # - 이 모집단위 이름이 적힌 필수 항목만 본다. 모집단위가 없는 필수 항목(석유공사 토익, 가스기술공사 운전면허 같은
    #   공고 전체 조건)은 화면에서 입력받지 않는 조건이라 여기서 지원 불가로 만들지 않는다 (아래 흐름 그대로)
    # - 한 모집단위의 필수 항목이 여러 개면 '그중 하나'로 본다 (한전KPS·LH: 기술사 또는 기사 또는 기능장)
    required = [item for item in accepted if item.get("kind") == "required" and name in (item.get("applicable_units") or [])]
    if required:
        held = [cert for cert in certificates if any(matches(cert, item.get("match") or {}) for item in required)]
        if not held:
            return {
                "status": "ineligible",
                "reason": required_text(required),
                "evidence": [evidence for item in required[:3] for evidence in item["evidence"]],
                "review": None,
            }
        item = next(item for item in required if any(matches(cert, item.get("match") or {}) for cert in held))
        return {
            "status": "eligible",
            "reason": f"{_with_ro(', '.join(held))} 필수 자격을 갖췄어요",  # 11-21 팀원 2차 점검 5번: 기계 문장 → 해요체 한 줄
            "evidence": item["evidence"],
            "review": None,
        }

    unrestricted = next((item for item in majors if item.get("unrestricted")), None)
    if unrestricted:
        return {"status": "eligible", "reason": unrestricted["name"], "evidence": unrestricted["evidence"], "review": None}

    for item in accepted:
        held = [cert for cert in certificates if matches(cert, item.get("match") or {})]
        if held:
            return {
                "status": "eligible",
                "reason": f"{_with_ro(', '.join(held))} 지원 자격을 갖췄어요",
                "evidence": item["evidence"],
                "review": None,
            }

    if majors:
        review = f"관련 전공자인지 확인: {majors[0]['name']}"
        if accepted and not certificates:
            review += " (전공자가 아니면 지원 가능 자격증이 필요해요)"
        return {
            "status": "ambiguous",
            "reason": "입력한 자격증이 지원 가능 자격증 목록에 없어 전공 요건을 확인해야 해요."
            if certificates else "자격증 입력이 없어 전공 요건을 확인해야 해요.",
            "evidence": majors[0]["evidence"] + (accepted[0]["evidence"] if accepted else []),
            "review": review,
        }
    # '필수 자격증'(required)으로 명시된 경우에만 지원 불가. '전공자 또는 자격증'(accepted)인데 전공 정보가 없으면
    # 전공자일 수도 있으므로 애매로 둔다 (11-19 한수원 AI 추출: ICT 통신 관련학과 전공 항목이 빠져 통신 전공자도 '지원 불가'가 될 뻔함)
    required = [item for item in accepted if item.get("kind") == "required"]
    if required:
        return {
            "status": "ineligible",
            "reason": required_text(required[:1]),
            "evidence": required[0]["evidence"],
            "review": None,
        }
    if accepted:
        return {
            "status": "ambiguous",
            "reason": "입력한 자격증이 지원 가능 자격증 목록에 없고, 공고문에서 지원 가능 전공을 찾지 못했어요.",
            "evidence": accepted[0]["evidence"],
            "review": f"관련 전공자인지 공고문에서 확인: {accepted[0]['name']}",
        }
    return {
        "status": "ambiguous",
        "reason": "이 직렬의 전공·자격증 요건이 아직 정리되지 않았어요.",
        "evidence": [],
        "review": "공고문 지원자격에서 이 직렬의 전공·자격증 요건을 직접 확인하세요.",
    }


def _bonus(track: str, certificates: tuple[str, ...], requirements: Mapping[str, Any]) -> list[dict[str, Any]]:
    held = keep_highest_grade(certificates)
    rows = []
    for item in requirements.get("certificates") or []:
        if item.get("kind") != "bonus" or (item.get("track") and item["track"] != track):
            continue
        for cert in held:
            if matches(cert, item.get("match") or {}):
                rows.append(
                    {
                        "certificate": cert,
                        "points": item.get("points"),
                        "unit": item.get("unit") or "점",
                        "units": list(item.get("applicable_units") or []),
                        "item": item["name"],
                        "evidence": item["evidence"],
                    }
                )
    # 같은 자격증·같은 모집단위에 가점이 두 번 잡히면(예: '전체 직렬' 항목 + '기계 직렬' 항목) 높은 점수 하나만 남긴다.
    # 11-19 중부발전 AI 추출: 정답 10점인데 두 항목을 더해 20점이 됨
    best: dict[tuple, dict[str, Any]] = {}
    for row in rows:
        key = (row["certificate"], tuple(row["units"]), row.get("unit") or "점")
        if key not in best or float(row["points"] or 0) > float(best[key]["points"] or 0):
            best[key] = row
    return [row for row in rows if best.get((row["certificate"], tuple(row["units"]), row.get("unit") or "점")) is row]


REGION_WORDS = {"전국", "수도권", "비수도권", "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원",
                "충북", "충남", "전북", "전남", "경북", "경남", "제주"}


def readable_unit_name(name: str) -> str:
    """화면용 모집단위 이름: '일반직_신입_6급2_전기_전국' → '6급 전기(전국)' (11-21 팀원 2차 점검 5번)"""
    if "_" not in name:
        return name
    tokens = [token.strip() for token in name.split("_") if token.strip() and token.strip() not in {"일반직", "신입", "채용"}]
    tokens = [re.sub(r"^(\d급)\d$", r"\1", token) for token in tokens]
    if len(tokens) > 1 and tokens[-1] in REGION_WORDS:
        tokens[-2] = f"{tokens[-2]} {tokens[-1]}" if tokens[-2].endswith(")") else f"{tokens[-2]}({tokens[-1]})"
        tokens.pop()
    return " ".join(tokens) or name


def required_text(required: list[Mapping[str, Any]]) -> str:
    """'필수 자격증이 없어요: 전기 직렬 필수 자격: 발송배전·… 또는 전기 직렬 필수 자격: 전기·… 기사'
    → '전기·전기공사·전자 기사 이상 자격증이 필요해요' (새벽 점검 8·22번: 같은 말이 반복됨)"""
    names = [re.sub(r"^.*?필수\s*자격\s*[:：]\s*", "", str(item.get("name") or "")).strip() for item in required[:3]]
    names = [re.sub(r"\s*(자격증)?\s*소지자$", "", name).strip() for name in names if name]
    grades = ("기술사", "기능장", "기사", "산업기사", "기능사")
    lowest = None
    for name in names:  # '… 기술사' 또는 '… 기사' → 가장 낮은 등급 하나로 ('기사 이상')
        grade = next((value for value in sorted(grades, key=len, reverse=True) if name.endswith(value)), None)
        if grade and (lowest is None or grades.index(grade) > grades.index(lowest[1])):
            lowest = (name, grade)
    if lowest and ("·" in lowest[0] or "," in lowest[0] or " 등" in lowest[0]):
        return f"필수 자격증이 없어요: {lowest[0]} 이상이 필요해요"
    if names:
        joined = " 또는 ".join(dict.fromkeys(names))
        last = joined[-1:]
        particle = "이" if "가" <= last <= "힣" and (ord(last) - 0xAC00) % 28 else "가"
        return f"필수 자격증이 없어요: {joined}{particle} 필요해요"
    return "필수 자격증이 없어요"


def _with_ro(word: str) -> str:
    """'전기기사로', '정보처리산업기사로', '건축기능장으로' (받침 있으면 '으로', ㄹ 받침은 '로')"""
    last = word.rstrip()[-1:] if word.strip() else ""
    if "가" <= last <= "힣":
        final = (ord(last) - 0xAC00) % 28
        return word + ("로" if final in (0, 8) else "으로")
    return word + "로"


def evaluate(condition: UserCondition, report: Mapping[str, Any]) -> EligibilityResult:
    requirements = report.get("requirements") or {}
    curr = report["curr"]
    result = EligibilityResult(
        pair_id=str(report["pair_id"]),
        institution=str(report["institution"]),
        title=str(curr["title"]),
        deadline=str(curr["period"]["end"]),
        relevance="match",
        status=None,
        label=None,
        common_checks=[str(item["text"]) for item in requirements.get("common_checks") or []],
        bonus_rule=(requirements.get("bonus_rule") or {}).get("text"),
    )

    # 한 모집단위가 여러 직렬에 걸칠 수 있음(전기통신 → 전기·ICT), '전체'는 직렬 구분 없는 모집단위 (11-21)
    all_units = [unit for unit in requirements.get("units") or []
                 if condition.track in (unit.get("tracks") or [unit.get("track")]) or unit.get("track") == "전체"]
    excluded = [unit for unit in all_units if unit.get("kind") == "excluded"]
    units = [unit for unit in all_units if unit.get("kind") != "excluded"]
    if not units:
        result.relevance = "track_missing"
        result.reasons.append(f"이 공고에는 {condition.track} 직렬 모집단위가 없어요.")
        return result

    # 지역: 공고 근무지역과 희망 지역이 겹치는지
    notice_regions = expand_regions(requirements.get("regions") or [])
    wanted = condition.regions
    overlap = [region for region in wanted if region in notice_regions]
    if not notice_regions:
        result.review_items.append("공고에 근무지역 정보가 없어 직접 확인해야 해요.")
    elif overlap:
        result.reasons.append(f"희망 지역 근무지 있음: {', '.join(overlap)}")
    else:
        result.relevance = "region_mismatch"
        result.reasons.append(
            f"희망 지역({', '.join(wanted)})에 근무지가 없어요. 근무지: {', '.join(notice_regions)}"
        )
    region_note = requirements.get("region_note")

    # 모집단위별 판정
    special = [unit for unit in units if unit.get("kind") == "special"]
    for unit in units:
        if unit.get("kind") == "special":
            continue
        if unit.get("track") == "전체":
            row = {"status": "ambiguous",
                   "reason": "모집단위 이름에 직렬 구분이 없어요. 공고문에서 뽑는 분야를 확인하세요.",
                   "evidence": unit.get("evidence") or [],
                   "review": "모집단위 이름에 직렬 구분이 없어 공고문에서 뽑는 분야를 확인해야 해요."}
        elif unit.get("kind") == "condition":
            row = {"status": "ambiguous", "reason": unit.get("note") or "별도 지원 조건 확인 필요",
                   "evidence": unit.get("evidence") or [], "review": unit.get("note")}
        else:
            row = _check_unit(unit, condition.track, condition.certificates, requirements)
        result.units.append({"name": unit["name"], "status": row["status"], "label": LABELS[row["status"]],
                             "reason": row["reason"]})
        result.evidence.extend(row["evidence"])
        if row["review"] and row["review"] not in result.review_items:
            result.review_items.append(row["review"])

    statuses = [unit["status"] for unit in result.units]
    if not statuses and special:
        # 대상자 전형만 있는 공고 (수자원공사 26 하반기: 원문 1쪽 "취업지원 대상자 또는 장애인에 한하여 지원 가능")
        # → 일반 지원자는 '안 맞음' (11-21 팀원 2차 점검 1번: 전에는 '애매')
        result.status = "ineligible"
        result.label = LABELS["ineligible"]
        result.reasons.insert(0, f"{condition.track} 모집단위가 모두 대상자 전형이에요")
        result.reasons.append("보훈·장애인 등 해당 대상자만 지원할 수 있는 공고라 일반 지원자는 지원할 수 없어요.")
        result.review_items.append(
            f"취업지원 대상자(보훈)·장애인 등 해당 대상자라면 지원할 수 있어요: {', '.join(unit['name'] for unit in special)}"
        )
        if region_note:
            result.review_items.append(str(region_note["text"]))
        result.bonus = _bonus(condition.track, condition.certificates, requirements)
        return result
    if "eligible" in statuses:
        result.status = "eligible"
    elif "ambiguous" in statuses or not statuses:
        result.status = "ambiguous"
    else:
        result.status = "ineligible"
    result.label = LABELS[result.status]

    general = [unit["name"] for unit in result.units]
    result.reasons.insert(0, f"{condition.track} 모집단위: {', '.join(general) or '일반 모집 없음'}")
    if special:
        result.review_items.append(
            f"특별전형 모집단위 {len(special)}개({', '.join(unit['name'] for unit in special)})는 "
            "보훈·장애·지역인재 등 해당 대상자만 지원할 수 있어 판정에서 뺐어요."
        )
    if excluded:
        result.review_items.append(
            f"체험형 인턴·경력 채용 {len(excluded)}개({', '.join(unit['name'] for unit in excluded)})는 "
            "신입 정규직 채용이 아니라 판정에서 뺐어요."
        )
    # 근무지 배치 안내는 판정 이유 뒤에 (11-21 팀원 점검 4번: '애매' 한 줄 요약에 배치 안내가 먼저 나옴)
    if region_note:
        result.review_items.append(str(region_note["text"]))
        result.evidence.extend(region_note.get("evidence") or [])
    if result.status == "eligible":
        best = next(unit for unit in result.units if unit["status"] == "eligible")
        result.reasons.append(f"{best['name']}: {best['reason']}")
    elif result.status == "ineligible":
        result.reasons.extend(f"{unit['name']}: {unit['reason']}" for unit in result.units)

    result.bonus = _bonus(condition.track, condition.certificates, requirements)
    return result


def evaluate_all(condition: UserCondition, reports: Iterable[Mapping[str, Any]]) -> list[EligibilityResult]:
    """관련 공고 먼저, 그 안에서 지원 가능 → 애매 → 지원 불가 순서."""
    relevance_order = {"match": 0, "region_mismatch": 1, "track_missing": 2}
    results = [evaluate(condition, report) for report in reports]
    return sorted(
        results,
        key=lambda item: (relevance_order[item.relevance], STATUS_ORDER.get(item.status or "", 3), item.deadline),
    )
