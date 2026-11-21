"""11-21 팀원 2차 점검 (배포본 43c7d94) 반영 확인."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.pages.matches import _date_short, _short_title
from app.ui_components import _fragment_meaning, _tidy_list_text, diff_side_html
from src.eligibility import EligibilityResult, UserCondition, _with_ro, evaluate, readable_unit_name

ROOT = Path(__file__).resolve().parents[2]


def test_special_only_notice_is_ineligible_for_general_applicant() -> None:
    """1번: 수자원공사 26 하반기는 보훈·장애인 전용 → 일반 지원자 '안 맞음', 대상자 안내는 남김"""
    path = next(p for p in (ROOT / "data" / "reports").glob("*.json")
                if json.loads(p.read_text(encoding="utf-8"))["institution"] == "한국수자원공사")
    report = json.loads(path.read_text(encoding="utf-8"))
    result = evaluate(UserCondition("전기", "부산·울산", ("전기기사",)), report)
    assert result.status == "ineligible"
    assert "대상자" in result.reasons[0]
    assert result.review_items[0].startswith("취업지원 대상자")


def _result(institution: str, title: str) -> EligibilityResult:
    return EligibilityResult(pair_id="x", institution=institution, title=title, deadline="20261201", relevance="match",
                             status="eligible", label="지원 가능")


def test_title_keeps_nested_brackets() -> None:
    """2번: 괄호를 지우다 앞부분까지 잘리던 것"""
    assert _short_title(_result("한국동서발전", "한국동서발전(주) 2027년 상반기 신입직원(대졸수준(일반/보훈) 및 고졸) 선발")) \
        == "2027년 상반기 신입직원(대졸수준(일반/보훈) 및 고졸) 선발"
    assert _short_title(_result("한국가스공사", "2026년 하반기 일반직 , 연구직 및 별정직 채용공고")) \
        == "2026년 하반기 일반직, 연구직 및 별정직 채용공고"


def test_other_year_deadline_has_year() -> None:
    """4번"""
    today = date(2026, 11, 21)
    assert _date_short("20261201", today) == "12.01"
    assert _date_short("20251208", today) == "2025.12.08"


def test_machine_sentences_become_readable() -> None:
    """5번"""
    assert _with_ro("전기기사") == "전기기사로" and _with_ro("건축기능장") == "건축기능장으로"
    assert readable_unit_name("일반직_신입_6급2_전기_전국") == "6급 전기(전국)"
    assert readable_unit_name("대졸일반-발전전기") == "대졸일반-발전전기"


def test_change_titles_and_meaning() -> None:
    """6번: 목록 표기, 10배수 설명"""
    assert _tidy_list_text("모집단위 세분화 추가: ['배전(보훈)', '배전(일반)']") == "모집단위 세분화 추가: 배전(보훈), 배전(일반)"
    prev = "자격증가점(사무20, 기술40); / 사무 : 50배수, 기술 : 15배수"
    curr = "자격증가점(사무20점, 기술40점) / 사무 : 50배수, 전기(배전, 송변전) : 10배수, 기술(전기 외) : 15배수"
    assert _fragment_meaning(prev, curr, "전기(배전, 송변전) 10배수", ["10배수"], True) \
        == "작년엔 기술 분야 전체가 15배수였는데, 올해 전기(배전, 송변전)는 10배수로 줄었어요."


def test_diff_ignores_spacing_punctuation_and_point_unit() -> None:
    """9번(예시 3): '사무20 → 사무20점', 쉼표·괄호 차이는 색칠 안 함"""
    prev = "자격증가점(사무20, 기술40); / 사무 : 50배수"
    curr = "자격증가점(사무20점, 기술40점) / 사무 : 50배수, 전기 : 10배수"
    assert "diff-removed" not in diff_side_html(prev, curr, "prev")
    added = diff_side_html(prev, curr, "curr")
    assert added.count("diff-added") == 1 and "10배수" in added
