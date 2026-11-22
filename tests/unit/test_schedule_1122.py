"""11-22 14시 '일정' 오류 점검 메모 반영 확인 (공고문 글자 stage2 묶음 기준)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.change_summary import _dates, schedule, summarize

ROOT = Path(__file__).resolve().parents[2]


def _report(institution: str) -> dict:
    for path in (ROOT / "data" / "reports").glob("*.json"):
        report = json.loads(path.read_text(encoding="utf-8"))
        if report["institution"] == institution:
            return report
    raise KeyError(institution)


def _cells(institution: str) -> dict[str, str]:
    return {cell["name"]: cell["text"] for cell in schedule(_report(institution))}


def _row(institution: str):
    return next(row for row in summarize(_report(institution)) if row.key == "schedule")


def test_multiples_are_not_dates() -> None:
    """C-1: '1.5~2배수'는 날짜가 아님"""
    assert _dates("ㅇ1차면접 : 1.5~2배수", 2026) == []
    assert _dates("면접 10.20(화)", 2026)


def test_dates_out_of_order_are_dropped() -> None:
    """A: 철도 면접 1.1('1월 1일부터 면접시험 최종일까지' 문장) → 10.21~10.23, 수자원 최종 발표 8.26(서류 유효기간 기준일) → 11.24"""
    korail = _cells("한국철도공사")
    assert korail["면접"] == "10.21~10.23"
    water = _cells("한국수자원공사")
    assert water["최종 발표"] == "11.24" and water["면접"] == "11.9~11.13"


@pytest.mark.parametrize("institution", ["한국전력공사", "한국가스공사"])
def test_schedule_tables_with_separated_labels(institution: str) -> None:
    """B: 단계 이름과 날짜가 떨어진 일정 표"""
    cells = _cells(institution)
    assert {"필기 합격 발표", "면접", "최종 발표"} <= set(cells)
    if institution == "한국전력공사":
        assert (cells["필기 합격 발표"], cells["면접"], cells["최종 발표"]) == ("10.27", "11.9~11.27", "12.3")


def test_unreadable_schedule_points_to_page() -> None:
    """B 임시 대책: 못 읽으면 '찾지 못했어요' 대신 공고문 쪽수"""
    assert "공고문 4쪽 일정 표에서 확인하세요" in _row("한국가스기술공사").answer


def test_mismatched_pair_is_not_compared() -> None:
    """C-2: 서부발전 작년 짝이 4월 공고 → 날짜 비교 안 함"""
    row = _row("한국서부발전")
    assert row.status == "비교 어려움" and "4월 접수" in row.answer


def test_every_schedule_is_in_order() -> None:
    """30곳 모두: 서류 발표 → 필기 발표 → 면접 → 최종 발표 순서"""
    order = ["서류 합격 발표", "필기 합격 발표", "면접", "최종 발표"]
    for path in (ROOT / "data" / "reports").glob("*.json"):
        cells = [cell for cell in schedule(json.loads(path.read_text(encoding="utf-8"))) if cell["name"] in order]
        firsts = [cell["first"] for cell in cells]
        assert firsts == sorted(firsts), path.name
