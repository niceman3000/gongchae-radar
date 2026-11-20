"""T046: 30곳 수집·자동 리포트 규칙 테스트 (실제 수집 결과 기준, API 호출 없음)."""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from src.report_repository import ReportRepository, report_dir
from tools.collect_institutions import is_target, normalize_title, pick_pair

ROOT = Path(__file__).resolve().parents[2]


def notice(sn: str, start: str, title: str, people: int = 100, **extra) -> dict:
    return {"recrutPblntSn": sn, "pbancBgngYmd": start, "recrutPbancTtl": title, "recrutNope": people,
            "recrutSeNm": "신입", "hireTypeNmLst": "정규직", **extra}


def test_title_compare_ignores_year_and_round_numbers():
    assert normalize_title("2026년도 하반기 신입사원 채용") == normalize_title("2025년 하반기 신입사원 채용")
    assert normalize_title("2026년 제2차 신입 공채") == normalize_title("2025년 제3차 신입 공채")
    assert normalize_title("하반기 대졸") != normalize_title("상반기 고졸")


def test_previous_notice_is_about_one_year_before_with_similar_title():
    curr = notice("3", "20260901", "2026년 하반기 신입사원 채용")
    same_half_year = notice("2", "20260301", "2026년 상반기 신입사원 채용")    # 184일 전 → 짝 아님
    last_year = notice("1", "20250905", "2025년 하반기 신입사원 채용")          # 361일 전
    two_years = notice("0", "20240901", "2024년 하반기 신입사원 채용")          # 730일 전
    picked_curr, prev, reason = pick_pair([curr, same_half_year, last_year, two_years])
    assert picked_curr["recrutPblntSn"] == "3" and prev["recrutPblntSn"] == "1" and reason is None


def test_no_previous_notice_gives_reason():
    _, prev, reason = pick_pair([notice("3", "20260901", "2026년 신입")])
    assert prev is None and reason == "약 1년 전 비교 공고 없음"


@pytest.mark.parametrize("item, expected", [
    (notice("1", "20260901", "2026년 신입사원 공개채용"), True),
    (notice("1", "20260901", "단기노무원 채용", hireTypeNmLst="비정규직"), False),  # '비정규직'에 '정규직' 글자가 들어 있음
    (notice("1", "20260901", "2026년 서비스지원직(보훈) 채용"), False),
    (notice("1", "20260901", "2026년 일반직(신입, 경력), 연구직 및 별정직 채용"), True),
    (notice("1", "20260901", "2026년 신입 채용", hireTypeNmLst="청년인턴(채용형)"), True),
])
def test_target_filter(item, expected):
    assert is_target(item) is expected


def test_all_30_reports_pass_schema_and_have_requirements():
    repository = ReportRepository(report_dir())
    reports = repository.list_reports()
    assert not repository.errors, repository.errors
    assert len(reports) == 30
    empty = [report["institution"] for report in reports
             if not (report.get("requirements") or {}).get("certificates") and not (report.get("requirements") or {}).get("majors")]
    assert empty == []  # 11-20부터 그림 공고 7곳도 지원 자격 있음


KEY_SHAPES = [re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), re.compile(r"serviceKey=(?!\{|<|%s)[A-Za-z0-9%+/=]{20,}")]


@pytest.mark.parametrize("folder, pattern", [
    ("data/reports", "*.json"), ("evaluation/ai_extracted", "*.json"), ("config", "*.json"), ("stage2", "bundle_*.json"),
])
def test_saved_files_have_no_key_strings(folder, pattern):
    for path in (ROOT / folder).glob(pattern):
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(shape.search(text) for shape in KEY_SHAPES), path.name
