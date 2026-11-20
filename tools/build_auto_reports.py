# -*- coding: utf-8 -*-
"""
수집한 공기업 공고 쌍으로 자동 리포트 만들기 (tasks.md T043, AI 호출 없음)

입력: config/auto_pairs.json (tools/collect_institutions.py가 만듦), data/api, data/pdf
출력: data/reports/report_<기관코드>.json   (tier=auto, category=시장형/준시장형)
      stage2/bundle_<공고번호>.json        (PDF가 있을 때 쪽별 텍스트, 없거나 PDF가 더 새로우면 새로 만듦)
      results/stage1_auto.json             (1단계 비교 결과 모음)

실행 (프로젝트 최상위 폴더)
  .\\.venv\\Scripts\\python.exe tools\\build_auto_reports.py

11-19부터 핵심 3곳(config/demo_pairs.json)도 같은 방법으로 여기서 만든다 (30곳 모두 같은 과정).
핵심 3곳 원문 대조 결과(evaluation/ground_truth)는 tools/score_against_ground_truth.py의 정답지로만 쓴다.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import build_bundle  # noqa: E402
from src.diff_stage1 import compare  # noqa: E402
from src.report_builder import build_report, load_api_item, validate_report  # noqa: E402


def _bundle_text(root: Path, sn: str, pdf: Path, log=print) -> dict | None:
    """PDF가 있으면 쪽별 텍스트 묶음을 만들어 돌려준다.
    묶음이 없거나 PDF가 묶음보다 새 파일이면(다시 받은 PDF) 새로 읽는다. PDF가 없으면 옛 묶음도 쓰지 않는다."""
    bundle = root / "stage2" / f"bundle_{sn}.json"
    if not pdf.exists():
        return None
    if not bundle.exists() or pdf.stat().st_mtime > bundle.stat().st_mtime:
        try:
            data = build_bundle.build(str(pdf))
        except Exception as exc:  # noqa: BLE001 - 깨진 PDF는 건너뛰고 기록
            log(f"    PDF 읽기 실패 {pdf.name}: {exc}")
            return None
        bundle.parent.mkdir(parents=True, exist_ok=True)
        bundle.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return json.loads(bundle.read_text(encoding="utf-8")).get("all_text")


def all_pairs(root: Path = ROOT) -> list[dict]:
    """30곳 전부: 핵심 3곳(config/demo_pairs.json) + 자동 수집 27곳(config/auto_pairs.json).
    11-19부터 30곳 모두 같은 방법(코드 비교 + AI 추출 조건)으로 리포트를 만든다.
    핵심 3곳의 원문 대조 결과(evaluation/ground_truth)는 화면에 쓰지 않고 채점용 정답지로만 쓴다."""
    pairs = []
    for name in ("demo_pairs.json", "auto_pairs.json"):
        path = root / "config" / name
        if path.exists():
            pairs.extend(json.loads(path.read_text(encoding="utf-8")).get("pairs", []))
    return [{**pair, "tier": "auto"} for pair in pairs]


def build_all(root: Path = ROOT, only: list[str] | None = None, log=print) -> list[Path]:
    output_dir = root / "data" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    stage1_all, written = {}, []
    for pair in all_pairs(root):
        if only and pair["institution"] not in only:
            continue
        prefix = str(pair["pair_id"]).split("-", 1)[0]
        try:
            prev = load_api_item(root / pair["prev_api"])
            curr = load_api_item(root / pair["curr_api"])
        except (OSError, ValueError) as exc:
            log(f"  {pair['institution']}: 상세 JSON 없음 → 건너뜀 ({exc})")
            continue
        stage1 = compare(prev, curr)
        stage1_all[pair["institution"]] = stage1
        # 지원 자격·가점: AI 추출본만 쓴다 (tools/extract_requirements.py, 인용 원문 대조 통과분)
        requirements_file = root / "evaluation" / "ai_extracted" / f"{prefix}_requirements.json"
        # 예전 공고에서 뽑은 것이면 쓰지 않는다 (새 공고 수집 후 extract_requirements.py로 다시 뽑기)
        if requirements_file.exists() and json.loads(requirements_file.read_text(encoding="utf-8")).get("pair_id") != pair["pair_id"]:
            log(f"  {pair['institution']}: AI 추출본이 예전 공고 것이라 쓰지 않음 → extract_requirements.py 다시 실행")
            requirements_file = root / "evaluation" / "ai_extracted" / "_none.json"
        report = build_report(
            pair,
            stage1,
            prev,
            curr,
            prev_all_text=_bundle_text(root, pair["prev_sn"], root / pair["prev_pdf"], log),
            curr_all_text=_bundle_text(root, pair["curr_sn"], root / pair["curr_pdf"], log),
            reviewed_requirements=json.loads(requirements_file.read_text(encoding="utf-8"))
            if requirements_file.exists() else None,
            checked_at=pair.get("collected_at") or date.today().isoformat(),
        )
        validate_report(report)
        path = output_dir / f"report_{prefix}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(path)
        log(f"  {pair['institution']}: 변경 후보 {len(report['changes'])}건 → {path.name}")
    results = root / "results"
    results.mkdir(exist_ok=True)
    (results / "stage1_auto.json").write_text(json.dumps(stage1_all, ensure_ascii=False, indent=2), encoding="utf-8")
    return written


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="자동 리포트 생성 (T043)")
    parser.add_argument("--only", nargs="*", help="이 기관만 (이름)")
    args = parser.parse_args(argv)
    written = build_all(only=args.only)
    print(f"\n자동 리포트 {len(written)}개 생성 → data/reports/")


if __name__ == "__main__":
    main()
