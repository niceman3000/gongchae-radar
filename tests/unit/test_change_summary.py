"""'작년과 달라진 점' 5줄 요약 규칙 (11-21 구조 개편 명세 4·6번)."""

from __future__ import annotations

from datetime import date

from src.change_summary import (date_only_change, meaningful_changes, normalize, schedule, similar_exists,
                                summarize)


def _report(changes, prev_title="2025년 신입사원(대졸 일반)", curr_title="2026년 신입사원(대졸 일반)", benefits=()):
    return {"institution": "테스트공사", "prev": {"sn": "x1", "title": prev_title, "period": {"start": "20250909"}},
            "curr": {"sn": "x2", "title": curr_title, "period": {"start": "20260902", "end": "20260916"}},
            "changes": list(changes), "notice_info": {"benefits": list(benefits)}}


def test_same_after_normalize_is_not_a_change() -> None:
    """번호·기호·띄어쓰기·쉼표·괄호, '20'↔'20점' 차이는 같은 문장"""
    assert normalize("1. 자격증가점(사무20, 기술40)") == normalize("○ 자격증가점 (사무20점,기술40점)")
    change = {"category": "자격", "change_type": "text", "prev_value": "- 학력 : 제한 없음", "curr_value": "○ 학력: 제한없음"}
    assert meaningful_changes(_report([change])) == []


def test_new_only_when_nothing_similar_last_year() -> None:
    """'신설'·'새로'는 작년에 비슷한 문장이 없을 때만 (동서발전 '본사이전 지역인재'는 작년에도 있음)"""
    previous = ["1. 본사이전 지역인재 : 대졸수준(일반) 사무 IT분야 채용인원의 30% 이상"]
    assert similar_exists("1. 본사이전 지역인재 : 아래 분야 채용인원의 30% 이상", previous)
    assert not similar_exists("○ 한전 청년청렴 Auditor 우수활동자 : 1차전형 10% 가점", previous)


def test_changed_number_only_when_number_differs() -> None:
    same = {"name": "본사이전 지역인재", "change": "changed", "benefit": "아래 분야 채용인원의 30% 이상",
            "prev_benefit": "사무, IT분야 채용인원의 30% 이상"}
    row = summarize(_report([], benefits=[same]))[3]
    assert row.status == "같음" and "30% 그대로" in row.answer
    changed = {"name": "채용형 인턴 수료자", "change": "changed", "benefit": "배점의 10% 가점", "prev_benefit": "배점의 5% 가점"}
    row = summarize(_report([], benefits=[changed]))[3]
    assert row.status == "바뀜" and "5% → 10%" in row.answer


def test_count_is_hard_to_compare_when_kinds_differ() -> None:
    count = {"category": "인원", "change_type": "number", "prev_value": 49, "curr_value": 101}
    hard = summarize(_report([count], "2026년 상반기 신입사원(대졸 수준(일반/보훈/장애) 및 별정직)",
                             "2027년 상반기 신입직원(대졸수준(일반/보훈) 및 고졸) 선발"), "전기")[0]
    assert hard.status == "비교 어려움" and "고졸 전형이 새로 들어가" in hard.answer
    plain = summarize(_report([{**count, "prev_value": 421, "curr_value": 490}]), "전기")[0]
    assert plain.status == "바뀜" and plain.answer == "421명 → 490명 (+69명)"
    assert "전기 직렬 인원은 공고문 표에서 확인" in plain.note


def test_no_record_is_not_same() -> None:
    """기록이 없으면 '정보 없음' ('같음'은 작년·올해 둘 다 확인됐을 때만)"""
    rows = summarize(_report([]))
    assert [row.status for row in rows] == ["정보 없음"] * 5


def test_multiple_and_interview_rounds() -> None:
    multiple = {"category": "전형", "change_type": "text",
                "prev_value": "○ 외국어성적(100점) / 사무 : 50배수, 기술 : 15배수",
                "curr_value": "○ 외국어성적(100점) / 사무 : 50배수, 전기(배전, 송변전) : 10배수, 기술(전기 외) : 15배수"}
    assert summarize(_report([multiple]), "전기")[1].answer == "전기(배전·송변전) 서류 15배수 → 10배수"
    interviews = [{"category": "전형", "change_type": "text", "prev_value": "8. 1차 면접전형 : 2025.12.22.(월)",
                   "curr_value": "8. 면접전형(직무,인성) : 2027.01.25.(월)∼02.04.(목)"},
                  {"category": "전형", "change_type": "removed", "prev_value": "10. 2차 면접전형 : 2026.01.19.(월)",
                   "curr_value": None}]
    assert "면접 2번(1차·2차) → 1번" in summarize(_report(interviews))[1].answer


def test_schedule_and_date_only_changes() -> None:
    lines = [{"category": "전형", "change_type": "text", "prev_value": "5. 필기합격자 발표 : 2025.12.05.(금)",
              "curr_value": "5. 필기합격자 발표 : 2026.12.24.(목)"}]
    report = _report(lines)
    assert date_only_change(lines[0])
    assert meaningful_changes(report) == []
    row = summarize(report)[4]
    assert row.status == "바뀜" and "12.24 (작년 12.05보다 약 3주 늦음)" in row.answer
    cells = schedule(report, date(2026, 11, 21))
    assert [cell["name"] for cell in cells] == ["지원서 접수", "필기 합격 발표"]
