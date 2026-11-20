"""화면이 쓰는 리포트 목록. 30곳 리포트를 매번 검증하지 않도록 파일이 바뀔 때만 다시 읽는다."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from src.report_repository import DEFAULT_SCHEMA_PATH, ReportRepository, report_dir

ROOT = Path(__file__).resolve().parents[1]
CATEGORY_ORDER = {"시장형": 0, "준시장형": 1}
AUTO_BADGE = "자동 비교 · 원문 미검증"  # 11-19부터 화면에서 쓰지 않음 (30곳을 똑같이 보여줌)
# 30곳 모두에 해당하는 안내. 화면마다 한 번만 보여준다 (기관별 배지 대신)
DATA_NOTICE = "공고 내용은 정부 채용정보와 공고문에서 자동으로 정리했어요. 지원 전에 공고문 원문을 꼭 확인하세요."


@st.cache_data(show_spinner=False)
def _load(signature: tuple) -> tuple[list[dict[str, Any]], dict[str, str]]:
    repository = ReportRepository(signature[0])
    reports = repository.list_reports()
    return reports, dict(repository.errors)


def sort_key(report: dict[str, Any]) -> tuple:
    """시장형 → 준시장형, 기관 이름 순 (30곳을 똑같이 다룬다)."""
    return (
        CATEGORY_ORDER.get(str(report.get("category")), 2),
        str(report.get("institution")),
    )


def load_reports() -> tuple[list[dict[str, Any]], dict[str, str]]:
    """(리포트 목록, 읽지 못한 파일과 이유). 리포트 파일이나 스키마가 바뀌면 다시 읽는다."""
    folder = report_dir()
    files = sorted(folder.glob("report_*.json"))
    signature = (str(folder),) + tuple((path.name, path.stat().st_mtime_ns) for path in files) + (
        Path(DEFAULT_SCHEMA_PATH).stat().st_mtime_ns,
    )
    reports, errors = _load(signature)
    return sorted(reports, key=sort_key), errors


def is_auto(report: dict[str, Any]) -> bool:
    return report.get("tier") == "auto"


def collection_skipped() -> list[dict[str, Any]]:
    """수집 스크립트가 리포트를 만들지 못한 기관과 이유 (data/api/collect_log.json)."""
    path = ROOT / "data" / "api" / "collect_log.json"
    if not path.exists():
        return []
    try:
        return list(json.loads(path.read_text(encoding="utf-8")).get("skipped") or [])
    except (OSError, json.JSONDecodeError):
        return []
