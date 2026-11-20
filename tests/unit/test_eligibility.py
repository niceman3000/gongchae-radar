import pytest

from src.certificates import keep_highest_grade, matches, parse
from src.eligibility import UserCondition, evaluate, evaluate_all
from src.report_builder import _reviewed_requirements, unit_track

EVIDENCE = [{"side": "curr", "notice_sn": "2", "page": 3, "quote": "근거", "verified": True}]


def _report(requirements, pair_id="sample", end="20260806"):
    base = {
        "tracks": ["전기"],
        "regions": ["부산", "울산"],
        "certificates": [],
        "majors": [],
        "manual_review_conditions": [],
        "units": [{"name": "전기(일반)", "track": "전기", "kind": "general", "note": None, "evidence": []}],
        "common_checks": [{"text": "외국어: TOEIC 700점 이상", "evidence": []}],
        "region_note": None,
        "bonus_rule": None,
    }
    base.update(requirements)
    return {
        "pair_id": pair_id,
        "institution": "샘플기관",
        "curr": {"title": "샘플 공고", "period": {"start": "20260722", "end": end}},
        "prev": {"title": "작년 공고"},
        "requirements": base,
    }


ACCEPTED = {
    "name": "전기 기사·산업기사",
    "kind": "accepted",
    "track": "전기",
    "applicable_units": [],
    "match": {"items": ["전기", "전기공사"], "grades": ["산업기사", "기사"]},
    "evidence": EVIDENCE,
}
MAJOR = {"name": "전기 관련학과", "kind": "accepted", "track": "전기", "applicable_units": [], "evidence": EVIDENCE}
CONDITION = UserCondition("전기", "부산·울산", ("전기기사",))


def test_certificate_names_split_into_item_and_grade():
    assert parse("전기기사") == ("전기", "기사")
    assert parse("전기공사산업기사") == ("전기공사", "산업기사")
    assert parse("소방설비기사(전기)") == ("소방설비전기", "기사")
    assert matches("전기기사", {"items": ["전기"], "grades": ["산업기사", "기사"]})
    assert not matches("전기기능사", {"items": ["전기"], "grades": ["산업기사", "기사"]})
    assert matches("소방설비기사(전기)", {"names": ["소방설비기사(전기)"]})


def test_same_item_keeps_only_highest_grade():
    assert keep_highest_grade(["전기산업기사", "전기기사", "전자기사"]) == ["전기기사", "전자기사"]


def test_required_condition_met_is_eligible_with_evidence():
    result = evaluate(CONDITION, _report({"certificates": [ACCEPTED], "majors": [MAJOR]}))

    assert result.status == "eligible"
    assert result.label == "지원 가능"
    assert any("전기기사" in reason for reason in result.reasons)
    assert result.evidence == EVIDENCE
    # 외국어처럼 입력받지 않은 조건은 상태가 아니라 공통 확인 사항으로 보여준다
    assert result.common_checks == ["외국어: TOEIC 700점 이상"]


def test_explicit_missing_required_certificate_is_ineligible():
    required = {**ACCEPTED, "kind": "required"}

    result = evaluate(UserCondition("전기", "부산", ("정보처리기사",)), _report({"certificates": [required]}))

    assert result.status == "ineligible"
    assert result.label == "지원 불가"
    assert any("필수 자격증이 없습니다" in reason for reason in result.reasons)
    assert result.evidence == EVIDENCE


def test_missing_requirement_data_is_ambiguous_not_eligible():
    result = evaluate(CONDITION, _report({}))

    assert result.status == "ambiguous"
    assert any("직접 확인" in item for item in result.review_items)


def test_major_alternative_without_certificate_needs_manual_check():
    result = evaluate(UserCondition("전기", "부산", ()), _report({"certificates": [ACCEPTED], "majors": [MAJOR]}))

    assert result.status == "ambiguous"
    assert any(item.startswith("관련 전공자인지 확인: 전기 관련학과") for item in result.review_items)


def test_unrestricted_major_is_eligible_without_certificate():
    unrestricted = {**MAJOR, "name": "전공 제한 없음", "unrestricted": True}

    result = evaluate(UserCondition("전기", "부산", ()), _report({"majors": [unrestricted]}))

    assert result.status == "eligible"


def test_special_units_are_excluded_and_condition_units_are_ambiguous():
    units = [
        {"name": "전기(보훈)", "track": "전기", "kind": "special", "note": "보훈 대상자만", "evidence": []},
        {"name": "지역모집(전기)", "track": "전기", "kind": "condition", "note": "지역주민 확인 필요", "evidence": []},
    ]

    result = evaluate(CONDITION, _report({"units": units, "certificates": [ACCEPTED]}))

    assert result.status == "ambiguous"
    assert [unit["name"] for unit in result.units] == ["지역모집(전기)"]
    assert "지역주민 확인 필요" in result.review_items
    assert any("특별전형 모집단위 1개" in item for item in result.review_items)


def test_region_and_track_relevance():
    report = _report({"regions": ["서울", "전남광주"], "certificates": [ACCEPTED]})

    assert evaluate(UserCondition("전기", "광주", ("전기기사",)), report).relevance == "match"
    assert evaluate(CONDITION, report).relevance == "region_mismatch"
    missing = evaluate(UserCondition("기계", "서울", ()), report)
    assert missing.relevance == "track_missing"
    assert missing.status is None


def test_results_are_sorted_by_relevance_then_status_without_scores():
    eligible = _report({"certificates": [ACCEPTED]}, "a")
    ambiguous = _report({}, "b")
    other_region = _report({"regions": ["서울"], "certificates": [ACCEPTED]}, "c")

    results = evaluate_all(CONDITION, [other_region, ambiguous, eligible])

    assert [item.pair_id for item in results] == ["a", "b", "c"]
    assert not any(hasattr(item, "score") for item in results)


def test_bonus_lists_points_for_held_certificates():
    bonus = {**ACCEPTED, "kind": "bonus", "points": 10, "name": "가점 10점", "applicable_units": ["전기(일반)"]}

    result = evaluate(UserCondition("전기", "부산", ("전기기사", "전기산업기사")), _report({"certificates": [bonus]}))

    assert [(row["certificate"], row["points"]) for row in result.bonus] == [("전기기사", 10)]


def test_personal_identification_fields_are_refused():
    with pytest.raises(ValueError):
        UserCondition.from_mapping({"track": "전기", "region": "부산", "name": "홍길동"})
    with pytest.raises(ValueError):
        UserCondition("", "부산")


def test_unit_track_mapping_and_reviewed_requirements_are_verified_against_pdf_text():
    assert unit_track("배전(일반)") == "전기"
    assert unit_track("일반모집(원전발전-전기전자)") == "전기"
    assert unit_track("일반모집(원전ENG-기계)") == "기계"

    api = {
        "workRgnNmLst": "부산,울산",
        "steps": [{"recrutPbancTtl": "배전(일반)"}, {"recrutPbancTtl": "배전(일반)"}, {"recrutPbancTtl": "배전(보훈)"}],
    }
    reviewed = {
        "items": [{"kind": "major", "track": "전기", "name": "전기 관련학과", "evidence": [{"side": "curr", "page": 1, "quote": "전기공학 관련학과"}]}],
        "unit_notes": [{"pattern": "보훈", "kind": "special", "text": "보훈 대상자만", "evidence": []}],
        "common_checks": [],
    }

    requirements = _reviewed_requirements(api, reviewed, {"1": "지원 가능 학과: 전기공학 관련학과"}, "2")

    assert [(unit["name"], unit["kind"]) for unit in requirements["units"]] == [("배전(일반)", "general"), ("배전(보훈)", "special")]
    assert requirements["majors"][0]["evidence"][0]["verified"] is True
    assert requirements["regions"] == ["부산", "울산"]


def test_core_reports_have_requirements_for_every_general_track():
    """정답지가 있는 핵심 3곳은 AI 추출만으로도 일반 모집 직렬마다 지원 자격(전공 또는 자격증)이 있어야 한다.
    (11-19부터 30곳 모두 AI 추출본을 쓴다. 22곳은 공고문 형태에 따라 비어 있을 수 있어 검사하지 않는다)"""
    from src.report_repository import ReportRepository

    for report in ReportRepository().list_reports():
        if report["pair_id"].split("-", 1)[0] not in {"kepco", "khnp", "komipo"}:
            continue
        requirements = report["requirements"]
        general_tracks = {unit["track"] for unit in requirements["units"] if unit["kind"] == "general"} - {"기타"}
        items = requirements["certificates"] + requirements["majors"]
        if any(not item.get("track") for item in items):  # 직렬 구분 없는 항목은 모든 직렬에 적용
            continue
        reviewed_tracks = {item["track"] for item in items}
        assert general_tracks <= reviewed_tracks, (report["pair_id"], general_tracks - reviewed_tracks)

def test_water_resources_track_uses_khnp_attachment_lists():
    from src.report_repository import ReportRepository

    reports = ReportRepository().list_reports()
    with_cert = evaluate_all(UserCondition("수자원", "부산", ("수자원개발기사",)), reports)
    without = evaluate_all(UserCondition("수자원", "부산", ()), reports)

    khnp = next(item for item in with_cert if item.pair_id == "khnp-2025-2026-round3")
    assert khnp.status == "eligible"
    assert next(item for item in without if item.pair_id == "khnp-2025-2026-round3").status == "ambiguous"
