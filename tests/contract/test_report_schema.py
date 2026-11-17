import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "src" / "schemas" / "report.schema.json"


def load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def make_valid_report():
    return {
        "schema_version": "1.0.0",
        "pair_id": "sample-2025-2026",
        "pair_name": "샘플 공고 비교",
        "institution": "샘플기관",
        "checked_at": "2026-11-17",
        "prev": {
            "sn": "100",
            "title": "2025 공고",
            "period": {"start": "20250101", "end": "20250131"},
            "pdf_path": "data/pdf/100.pdf",
            "source_url": None,
        },
        "curr": {
            "sn": "200",
            "title": "2026 공고",
            "period": {"start": "20260101", "end": "20260131"},
            "pdf_path": "data/pdf/200.pdf",
            "source_url": None,
        },
        "tracks": ["전기"],
        "changes": [],
        "units": [],
        "competition": {
            "published": False,
            "prev": None,
            "curr": None,
            "note": "기관 미공시",
            "checked_at": None,
        },
        "requirements": {
            "tracks": ["전기"],
            "regions": [],
            "certificates": [],
            "majors": [],
            "manual_review_conditions": [],
        },
    }


def validator():
    return Draft202012Validator(load_schema(), format_checker=FormatChecker())


def test_schema_is_valid_draft_2020_12():
    Draft202012Validator.check_schema(load_schema())


def test_minimal_report_matches_contract():
    validator().validate(make_valid_report())


def test_missing_pair_id_is_rejected():
    report = make_valid_report()
    del report["pair_id"]

    with pytest.raises(ValidationError):
        validator().validate(report)


def test_unknown_top_level_field_is_rejected():
    report = make_valid_report()
    report["unexpected"] = True

    with pytest.raises(ValidationError):
        validator().validate(report)


@pytest.mark.parametrize("path", sorted((ROOT / "data" / "reports").glob("report_*.json")))
def test_generated_reports_match_contract(path):
    validator().validate(json.loads(path.read_text(encoding="utf-8")))
