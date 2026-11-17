"""1·2단계 결과를 화면용 report v1 JSON으로 합친다."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator, FormatChecker

try:
    from src.evidence import can_confirm_change, validate_report_semantics
except ModuleNotFoundError:  # `python src/report_builder.py` 직접 실행 지원
    from evidence import can_confirm_change, validate_report_semantics


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config" / "demo_pairs.json"
DEFAULT_STAGE1 = ROOT / "results" / "stage1_result.json"
DEFAULT_SCHEMA = ROOT / "src" / "schemas" / "report.schema.json"
DEFAULT_OUTPUT = ROOT / "data" / "reports"

IMPORTANCE = {
    "number": 1,
    "added": 2,
    "removed": 2,
    "list": 2,
    "text": 2,
    "rename": 3,
    "date": 3,
}
CATEGORY = {
    "채용인원": "인원",
    "근무지역": "지역",
    "응시자격": "자격",
    "우대사항": "가점",
    "전형방법": "전형",
    "모집단위": "모집단위",
    "모집단위 세분화": "모집단위",
}


def normalize_unit_name(name: str) -> str:
    """연도 비교에만 쓰는 모집단위 이름. 화면에는 원문 이름을 유지한다."""
    normalized = re.sub(r"_(일반|보훈|장애|장애인)$", "", name or "")
    normalized = re.sub(r"\((일반|보훈|장애|장애인|가|나)\)$", "", normalized)
    return normalized.strip()


def load_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_api_item(path: Path | str) -> dict[str, Any]:
    payload = load_json(path)
    result = payload.get("result", payload)
    if isinstance(result, list):
        if not result:
            raise ValueError(f"API 결과가 비었습니다: {path}")
        return result[0]
    if not isinstance(result, dict):
        raise ValueError(f"API 상세 형식이 아닙니다: {path}")
    return result


def _source_url(item: Mapping[str, Any]) -> str | None:
    notices = [
        file
        for file in item.get("files") or []
        if file.get("atchFileType") == "A" and file.get("url")
    ]
    return str(notices[0]["url"]) if notices else None


def _notice_ref(
    item: Mapping[str, Any], sn: str, pdf_path: str
) -> dict[str, Any]:
    return {
        "sn": str(sn),
        "title": str(item.get("recrutPbancTtl") or "제목 확인 필요"),
        "period": {
            "start": str(item.get("pbancBgngYmd") or "확인 필요"),
            "end": str(item.get("pbancEndYmd") or "확인 필요"),
        },
        "pdf_path": pdf_path,
        "source_url": _source_url(item),
    }


def _change_values(change: Mapping[str, Any]) -> tuple[Any, Any]:
    if change.get("type") == "list":
        return change.get("removed") or [], change.get("added") or []
    return change.get("prev"), change.get("curr")


def _classification_index(items: Iterable[Mapping[str, Any]] | None) -> dict[tuple, Mapping[str, Any]]:
    def key(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    return {
        (item.get("field"), key(item.get("prev")), key(item.get("curr"))): item
        for item in items or []
    }


def _default_title(field: str, kind: str, prev: Any, curr: Any) -> str:
    if kind == "added":
        return f"{field} 추가: {curr}"
    if kind == "removed":
        return f"{field} 삭제: {prev}"
    if kind == "list":
        return f"{field} 목록 변경"
    return f"{field}: {prev} → {curr}"


def _stage1_changes(
    stage1: Mapping[str, Any],
    classifications: Iterable[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    class_by_key = _classification_index(classifications)
    changes = []
    for index, source in enumerate(stage1.get("changes") or [], 1):
        field = str(source.get("field") or "기타")
        kind = str(source.get("type") or "text")
        prev, curr = _change_values(source)
        classification = class_by_key.get(
            (
                field,
                json.dumps(source.get("prev"), ensure_ascii=False, sort_keys=True),
                json.dumps(source.get("curr"), ensure_ascii=False, sort_keys=True),
            )
        )
        label = classification.get("label") if classification else None
        confidence = classification.get("confidence") if classification else None
        title = (
            str(classification.get("one_line"))
            if classification and classification.get("one_line")
            else _default_title(field, kind, prev, curr)
        )
        changes.append(
            {
                "id": f"stage1-{index:03d}",
                "importance": IMPORTANCE.get(kind, 3),
                "category": CATEGORY.get(field, field),
                "title": title,
                "change_type": kind if kind in IMPORTANCE else "text",
                "prev_value": prev,
                "curr_value": curr,
                "source": "stage1",
                "ai_label": label if label in {"실질 변경", "표현 변경"} else None,
                "confidence": (
                    "high" if confidence == "높음" else "low" if confidence == "낮음" else "not_applicable"
                ),
                "status": "review_required",
                "affected_units": [],
                "evidence": [],
            }
        )
    return changes


def _convert_evidence(
    raw: Mapping[str, Any] | None, side: str, notice_sn: str
) -> dict[str, Any] | None:
    if not raw or not raw.get("quote"):
        return None
    try:
        page = int(raw.get("page"))
    except (TypeError, ValueError):
        return None
    if page < 1:
        return None
    verified = raw.get("verified") is True or raw.get("verified") == "쪽 일치"
    return {
        "side": side,
        "notice_sn": str(notice_sn),
        "page": page,
        "quote": str(raw["quote"])[:300],
        "verified": verified,
    }


def _unit_index(extract: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    result = {}
    for unit in (extract or {}).get("units") or []:
        name = str(unit.get("unit_name") or "").strip()
        if name:
            result.setdefault(normalize_unit_name(name), unit)
    return result


def _number(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _headcount(unit: Mapping[str, Any] | None) -> int | None:
    return _number(((unit or {}).get("headcount_total") or {}).get("value"))


def _unit_evidence(
    unit: Mapping[str, Any] | None, side: str, notice_sn: str
) -> list[dict[str, Any]]:
    output = []
    total = ((unit or {}).get("headcount_total") or {}).get("evidence")
    converted = _convert_evidence(total, side, notice_sn)
    if converted:
        output.append(converted)
    return output


def _regions(unit: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    return {
        str(item.get("region")): item
        for item in (unit or {}).get("headcount_by_region") or []
        if item.get("region")
    }


def _build_units(
    prev_extract: Mapping[str, Any] | None,
    curr_extract: Mapping[str, Any] | None,
    prev_sn: str,
    curr_sn: str,
    default_track: str,
) -> list[dict[str, Any]]:
    prev_units = _unit_index(prev_extract)
    curr_units = _unit_index(curr_extract)
    output = []
    for normalized in sorted(set(prev_units) | set(curr_units)):
        prev_unit = prev_units.get(normalized)
        curr_unit = curr_units.get(normalized)
        raw_name = str((curr_unit or prev_unit or {}).get("unit_name") or normalized)
        prev_regions = _regions(prev_unit)
        curr_regions = _regions(curr_unit)
        by_region = []
        for region in sorted(set(prev_regions) | set(curr_regions)):
            p = prev_regions.get(region)
            c = curr_regions.get(region)
            evidence = []
            for raw, side, sn in ((p, "prev", prev_sn), (c, "curr", curr_sn)):
                item = _convert_evidence((raw or {}).get("evidence"), side, sn)
                if item:
                    evidence.append(item)
            by_region.append(
                {
                    "region": region,
                    "prev": _number((p or {}).get("value")),
                    "curr": _number((c or {}).get("value")),
                    "evidence": evidence,
                }
            )
        output.append(
            {
                "unit_name": raw_name,
                "normalized_name": normalized,
                "track": str((curr_unit or prev_unit or {}).get("track") or default_track),
                "headcount_prev": _headcount(prev_unit),
                "headcount_curr": _headcount(curr_unit),
                "by_region": by_region,
                "evidence": _unit_evidence(prev_unit, "prev", prev_sn)
                + _unit_evidence(curr_unit, "curr", curr_sn),
            }
        )
    return output


def _stage2_unit_changes(units: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    changes = []
    for index, unit in enumerate(units, 1):
        prev = unit.get("headcount_prev")
        curr = unit.get("headcount_curr")
        if prev is None or curr is None or prev == curr:
            continue
        change = {
            "id": f"stage2-unit-{index:03d}",
            "importance": 1,
            "category": "인원",
            "title": f"{unit['unit_name']} 인원 {prev}명 → {curr}명",
            "change_type": "number",
            "prev_value": prev,
            "curr_value": curr,
            "source": "stage2",
            "ai_label": "실질 변경",
            "confidence": "high",
            "status": "review_required",
            "affected_units": [str(unit["unit_name"])],
            "evidence": list(unit.get("evidence") or []),
        }
        if can_confirm_change(change):
            change["status"] = "confirmed"
        changes.append(change)
    return changes


def _requirements(
    curr_extract: Mapping[str, Any] | None,
    curr_sn: str,
    tracks: list[str],
) -> dict[str, Any]:
    certificates = []
    manual = []
    regions = set()
    for unit in (curr_extract or {}).get("units") or []:
        unit_name = str(unit.get("unit_name") or "")
        for region in unit.get("headcount_by_region") or []:
            if region.get("region"):
                regions.add(str(region["region"]))
        for item in unit.get("certificate_bonus") or []:
            ev = _convert_evidence(item.get("evidence"), "curr", curr_sn)
            certificates.append(
                {
                    "name": str(item.get("certificate") or "자격증 확인 필요"),
                    "kind": "bonus",
                    "applicable_units": [unit_name] if unit_name else [],
                    "evidence": [ev] if ev else [],
                }
            )
        for item in unit.get("required_qualifications") or []:
            if item.get("item"):
                manual.append(str(item["item"]))
    return {
        "tracks": list(dict.fromkeys(tracks)),
        "regions": sorted(regions),
        "certificates": certificates,
        "majors": [],
        "manual_review_conditions": list(dict.fromkeys(manual)),
    }


def build_report(
    config: Mapping[str, Any],
    stage1: Mapping[str, Any],
    prev_api: Mapping[str, Any],
    curr_api: Mapping[str, Any],
    *,
    prev_extract: Mapping[str, Any] | None = None,
    curr_extract: Mapping[str, Any] | None = None,
    text_classifications: Iterable[Mapping[str, Any]] | None = None,
    checked_at: str | None = None,
) -> dict[str, Any]:
    prev_sn, curr_sn = str(config["prev_sn"]), str(config["curr_sn"])
    tracks = [str(value) for value in config.get("track_focus") or ["기타"]]
    units = _build_units(prev_extract, curr_extract, prev_sn, curr_sn, tracks[0])
    changes = _stage1_changes(stage1, text_classifications) + _stage2_unit_changes(units)
    changes.sort(key=lambda item: (item["importance"], item["id"]))
    competition = stage1.get("competition_in_api") or {}
    published = bool(competition.get("prev") or competition.get("curr"))

    return {
        "schema_version": "1.0.0",
        "pair_id": str(config["pair_id"]),
        "pair_name": str(config["pair_name"]),
        "institution": str(config["institution"]),
        "checked_at": checked_at or date.today().isoformat(),
        "prev": _notice_ref(prev_api, prev_sn, str(config["prev_pdf"])),
        "curr": _notice_ref(curr_api, curr_sn, str(config["curr_pdf"])),
        "tracks": tracks,
        "changes": changes,
        "units": units,
        "competition": {
            "published": published,
            "prev": None,
            "curr": None,
            "note": "API에 인원 정보가 있으나 경쟁률 수기 확인 필요" if published else "기관 미공시",
            "checked_at": None,
        },
        "requirements": _requirements(curr_extract, curr_sn, tracks),
    }


def _find_stage1(all_results: Mapping[str, Any], prev_sn: str, curr_sn: str) -> Mapping[str, Any]:
    for result in all_results.values():
        if str((result.get("prev") or {}).get("sn")) == str(prev_sn) and str(
            (result.get("curr") or {}).get("sn")
        ) == str(curr_sn):
            return result
    raise KeyError(f"stage1 결과에서 공고쌍을 찾지 못했습니다: {prev_sn}-{curr_sn}")


def _optional_json(path: Path) -> Any | None:
    return load_json(path) if path.exists() else None


def validate_report(report: Mapping[str, Any], schema_path: Path = DEFAULT_SCHEMA) -> None:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(report), key=lambda item: list(item.path))
    if errors:
        raise ValueError("리포트 스키마 오류: " + "; ".join(item.message for item in errors[:5]))
    semantic = validate_report_semantics(report)
    if semantic:
        raise ValueError("리포트 의미 오류: " + "; ".join(semantic))


def build_from_files(
    config_path: Path = DEFAULT_CONFIG,
    stage1_path: Path = DEFAULT_STAGE1,
    output_dir: Path = DEFAULT_OUTPUT,
    pair_id: str | None = None,
    checked_at: str | None = None,
) -> list[Path]:
    config = load_json(config_path)
    stage1_all = load_json(stage1_path)
    selected = [pair for pair in config["pairs"] if pair_id in (None, pair["pair_id"])]
    if not selected:
        raise KeyError(f"설정에서 공고쌍을 찾지 못했습니다: {pair_id}")

    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for pair in selected:
        prev_sn, curr_sn = str(pair["prev_sn"]), str(pair["curr_sn"])
        prefix = str(pair["pair_id"]).split("-", 1)[0]
        prev_extract = _optional_json(ROOT / "stage2" / f"extract_{prev_sn}.json")
        curr_extract = _optional_json(ROOT / "stage2" / f"extract_{curr_sn}.json")
        classification_path = ROOT / "stage2" / f"text_class_{prefix}.json"
        classifications = _optional_json(classification_path)
        if classifications is None and prefix == "kepco":
            classifications = _optional_json(ROOT / "stage2" / "text_class.json")

        report = build_report(
            pair,
            _find_stage1(stage1_all, prev_sn, curr_sn),
            load_api_item(ROOT / pair["prev_api"]),
            load_api_item(ROOT / pair["curr_api"]),
            prev_extract=prev_extract,
            curr_extract=curr_extract,
            text_classifications=classifications,
            checked_at=checked_at,
        )
        validate_report(report)
        path = output_dir / f"report_{prefix}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(path)
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all-demo-pairs", action="store_true")
    group.add_argument("--pair", help="config/demo_pairs.json의 pair_id")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--stage1", type=Path, default=DEFAULT_STAGE1)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--checked-at", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = build_from_files(
        args.config,
        args.stage1,
        args.output_dir,
        pair_id=None if args.all_demo_pairs else args.pair,
        checked_at=args.checked_at,
    )
    for path in paths:
        print(f"생성: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
