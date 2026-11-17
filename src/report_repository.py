"""검증된 통합 리포트 JSON 조회 계층."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from src.evidence import validate_report_semantics


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORT_DIR = ROOT / "data" / "reports"
DEFAULT_SCHEMA_PATH = ROOT / "src" / "schemas" / "report.schema.json"


class ReportContractError(ValueError):
    """리포트가 구조 또는 의미 계약을 위반할 때 발생한다."""


class ReportRepository:
    def __init__(
        self,
        report_dir: Path | str = DEFAULT_REPORT_DIR,
        schema_path: Path | str = DEFAULT_SCHEMA_PATH,
    ) -> None:
        self.report_dir = Path(report_dir)
        self.schema_path = Path(schema_path)
        schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        self.validator = Draft202012Validator(schema, format_checker=FormatChecker())
        self.errors: dict[str, str] = {}

    def load_path(self, path: Path | str) -> dict[str, Any]:
        path = Path(path)
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReportContractError(f"{path.name}: JSON을 읽을 수 없습니다: {exc}") from exc

        structural = sorted(self.validator.iter_errors(report), key=lambda item: list(item.path))
        if structural:
            messages = "; ".join(error.message for error in structural[:5])
            raise ReportContractError(f"{path.name}: 스키마 오류: {messages}")

        semantic = validate_report_semantics(report)
        if semantic:
            raise ReportContractError(f"{path.name}: 의미 오류: {'; '.join(semantic)}")
        return report

    def list_reports(self) -> list[dict[str, Any]]:
        self.errors = {}
        reports = []
        for path in sorted(self.report_dir.glob("report_*.json")):
            try:
                reports.append(self.load_path(path))
            except ReportContractError as exc:
                self.errors[path.name] = str(exc)
        return reports

    def load(self, pair_id: str) -> dict[str, Any]:
        for report in self.list_reports():
            if report["pair_id"] == pair_id:
                return report
        raise KeyError(f"리포트를 찾을 수 없습니다: {pair_id}")
