import json
from pathlib import Path

import pytest

from src.report_repository import ReportContractError, ReportRepository
from tests.contract.test_report_schema import make_valid_report


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "src" / "schemas" / "report.schema.json"


def write_report(directory, name, report):
    path = directory / name
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    return path


def test_repository_lists_only_valid_reports(tmp_path):
    write_report(tmp_path, "report_valid.json", make_valid_report())
    write_report(tmp_path, "report_invalid.json", {"pair_id": "broken"})
    repository = ReportRepository(tmp_path, SCHEMA)

    reports = repository.list_reports()

    assert [item["pair_id"] for item in reports] == ["sample-2025-2026"]
    assert "report_invalid.json" in repository.errors


def test_repository_loads_report_by_pair_id(tmp_path):
    write_report(tmp_path, "report_valid.json", make_valid_report())
    repository = ReportRepository(tmp_path, SCHEMA)

    report = repository.load("sample-2025-2026")

    assert report["institution"] == "샘플기관"


def test_repository_rejects_unknown_pair_id(tmp_path):
    repository = ReportRepository(tmp_path, SCHEMA)

    with pytest.raises(KeyError):
        repository.load("missing")


def test_repository_rejects_semantically_invalid_confirmed_change(tmp_path):
    report = make_valid_report()
    report["changes"] = [
        {
            "id": "bad-evidence",
            "importance": 1,
            "category": "서류",
            "title": "배수 변경",
            "change_type": "number",
            "prev_value": "15배수",
            "curr_value": "10배수",
            "source": "stage1",
            "ai_label": None,
            "confidence": "not_applicable",
            "status": "confirmed",
            "affected_units": ["전기"],
            "evidence": [],
        }
    ]
    path = write_report(tmp_path, "report_bad.json", report)
    repository = ReportRepository(tmp_path, SCHEMA)

    with pytest.raises(ReportContractError):
        repository.load_path(path)
