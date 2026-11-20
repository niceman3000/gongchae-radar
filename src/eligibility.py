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

    unrestricted = next((item for item in majors if item.get("unrestricted")), None)
    if unrestricted:
        return {"status": "eligible", "reason": unrestricted["name"], "evidence": unrestricted["evidence"], "review": None}

    for item in accepted:
        held = [cert for cert in certificates if matches(cert, item.get("match") or {})]
        if held:
            return {
                "status": "eligible",
                "reason": f"보유 자격증 {', '.join(held)} → {item['name']}",
                "evidence": item["evidence"],
                "review": None,
            }

    if majors:
        review = f"관련 전공자인지 확인: {majors[0]['name']}"
        if accepted and not certificates:
            review += " (전공자가 아니면 지원 가능 자격증이 필요합니다)"
        return {
            "status": "ambiguous",
            "reason": "입력한 자격증이 지원 가능 자격증 목록에 없어 전공 요건 확인이 필요합니다."
            if certificates else "자격증 입력이 없어 전공 요건 확인이 필요합니다.",
            "evidence": majors[0]["evidence"] + (accepted[0]["evidence"] if accepted else []),
            "review": review,
        }
    # '필수 자격증'(required)으로 명시된 경우에만 지원 불가. '전공자 또는 자격증'(accepted)인데 전공 정보가 없으면
    # 전공자일 수도 있으므로 애매로 둔다 (11-19 한수원 AI 추출: ICT 통신 관련학과 전공 항목이 빠져 통신 전공자도 '지원 불가'가 될 뻔함)
    required = [item for item in accepted if item.get("kind") == "required"]
    if required:
        return {
            "status": "ineligible",
            "reason": f"필수 자격증이 없습니다: {required[0]['name']}",
            "evidence": required[0]["evidence"],
            "review": None,
        }
    if accepted:
        return {
            "status": "ambiguous",
            "reason": "입력한 자격증이 지원 가능 자격증 목록에 없고, 공고문에서 지원 가능 전공을 찾지 못했습니다.",
            "evidence": accepted[0]["evidence"],
            "review": f"관련 전공자인지 공고문에서 확인: {accepted[0]['name']}",
        }
    return {
        "status": "ambiguous",
        "reason": "이 직렬의 전공·자격증 요건이 아직 정리되지 않았습니다.",
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

    units = [unit for unit in requirements.get("units") or [] if unit.get("track") == condition.track]
    if not units:
        result.relevance = "track_missing"
        result.reasons.append(f"이 공고에는 {condition.track} 직렬 모집단위가 없습니다.")
        return result

    # 지역: 공고 근무지역과 희망 지역이 겹치는지
    notice_regions = expand_regions(requirements.get("regions") or [])
    wanted = condition.regions
    overlap = [region for region in wanted if region in notice_regions]
    if not notice_regions:
        result.review_items.append("공고에 근무지역 정보가 없어 직접 확인이 필요합니다.")
    elif overlap:
        result.reasons.append(f"희망 지역 근무지 있음: {', '.join(overlap)}")
    else:
        result.relevance = "region_mismatch"
        result.reasons.append(
            f"희망 지역({', '.join(wanted)})에 근무지가 없습니다. 근무지: {', '.join(notice_regions)}"
        )
    region_note = requirements.get("region_note")
    if region_note:
        result.review_items.append(str(region_note["text"]))
        result.evidence.extend(region_note.get("evidence") or [])

    # 모집단위별 판정
    special = [unit for unit in units if unit.get("kind") == "special"]
    for unit in units:
        if unit.get("kind") == "special":
            continue
        if unit.get("kind") == "condition":
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
            "보훈·장애 등 해당 대상자만 지원할 수 있어 판정에서 뺐습니다."
        )
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
