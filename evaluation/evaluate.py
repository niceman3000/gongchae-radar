# -*- coding: utf-8 -*-
"""
최종 측정 (tasks.md T033·T034) → evaluation/final-report.md

AI를 새로 부르지 않는다. 지금 저장된 결과로 다시 잰다.
  ① 지원 자격·가점·화면 판정: 3곳 정답지 대비 (tools/score_against_ground_truth.py를 다시 돌림)
  ② 작년 대비 변경점: 한전 원문 대조(evaluation/ground_truth/kepco_evidence.json) 대비 현재 리포트 후보
  ③ 핵심 숫자(인원·배수·면접 배점): 정답지 요약(*_summary.json)의 숫자가 리포트 변경 후보에 그대로 있는지
  ④ 근거 질문: 마지막 AI 채점 결과(evaluation/score_qa.md)를 옮겨 적음 (다시 재려면 tools/score_qa.py, 약 $0.15)
  ⑤ 30곳 데이터 범위: 리포트·지원 자격·원문 글자(PDF/그림 옮김) 있는 곳 수
  ⑥ 자동 테스트: --all이면 pytest 실행 결과

실행 (프로젝트 최상위 폴더)
  .\\.venv\\Scripts\\python.exe evaluation\\evaluate.py --all
측정 결과는 그대로 기록한다. 목표에 맞추려고 정답지나 결과를 고치지 않는다.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import io
import json
from pathlib import Path
import re
import subprocess
import sys
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

OUT = ROOT / "evaluation" / "final-report.md"
CORE = {"kepco": "한국전력공사", "khnp": "한국수력원자력", "komipo": "한국중부발전"}


def pct(part: int, whole: int) -> str:
    return f"{part / whole * 100:.0f}% ({part}/{whole})" if whole else "- (0/0)"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ① 지원 자격·가점·판정
def requirements_scores() -> list[str]:
    import score_against_ground_truth as scorer

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        scorer.main()
    lines = [line.strip() for line in buffer.getvalue().splitlines() if line.strip()]
    keep = [line for line in lines if "재현" in line or "판정 일치" in line]
    return [f"- {line}" for line in keep] + ["- 자세한 표: `evaluation/score_requirements.md`"]


# ② 변경점 (한전)
def change_scores() -> list[str]:
    evidence = load(ROOT / "evaluation" / "ground_truth" / "kepco_evidence.json")
    confirmed = {cid for cid, items in (evidence.get("changes") or {}).items() if items}
    report = load(ROOT / "data" / "reports" / "report_kepco.json")
    ids = [change["id"] for change in report.get("changes") or []]
    hit = [cid for cid in ids if cid in confirmed]
    missing = sorted(confirmed - set(ids))
    lines = [
        f"- 한전 변경 후보 {len(ids)}건 중 원문 대조로 확인된 실제 변경: **{pct(len(hit), len(ids))}** (정밀도)",
        f"- 원문 대조에서 확인됐는데 후보에 없는 것: {', '.join(missing) if missing else '없음'}",
        "- 원문 대조 기준일: " + str(evidence.get("reviewed_at")) + " (`evaluation/ground_truth/kepco.md`). "
        "필기 과락 기준 변경(6·7쪽)은 API 칸에 없어 코드가 놓침 (그때 기록)",
        "- 한수원·중부발전 변경점 원문 대조(T012·T013, 팀원)는 아직 없음 → 재지 않음",
    ]
    return lines


# ③ 핵심 숫자
def number_scores() -> list[str]:
    lines, total, found = [], 0, 0
    for key, name in CORE.items():
        path = ROOT / "evaluation" / "ground_truth" / f"{key}_summary.json"
        report_path = ROOT / "data" / "reports" / f"report_{key}.json"
        if not path.exists() or not report_path.exists():
            continue
        summary = load(path)
        report = load(report_path)
        # 화면에 쓰는 칸 전부 (변경 후보·한눈에 보기·모집단위·경쟁률). 지원 자격(requirements)은 뺌
        text = json.dumps({key: value for key, value in report.items() if key != "requirements"}, ensure_ascii=False)
        checks = []
        for value in summary.values():
            rows = value if isinstance(value, list) else [value] if isinstance(value, dict) else []
            for row in rows:
                if isinstance(row, dict) and "prev" in row and "curr" in row and row["prev"] != row["curr"]:
                    checks.append((row.get("label", ""), row["prev"], row["curr"]))
        hit = [label for label, prev, curr in checks
               if re.search(rf"(?<!\d){prev}(?!\d)", text) and re.search(rf"(?<!\d){curr}(?!\d)", text)]
        total += len(checks)
        found += len(hit)
        lines.append(f"- {name}: 정답지에서 바뀐 숫자 {len(checks)}개 중 리포트에 작년·올해 숫자가 모두 있는 것 {pct(len(hit), len(checks))}"
                     + (f" — 없음: {', '.join(label for label, *_ in checks if label not in hit)}" if len(hit) < len(checks) else ""))
    lines.append(f"- 합계 {pct(found, total)} (숫자가 리포트 어딘가에 있는지만 봄. 화면 문장이 맞는지는 사람 확인)")
    return lines


# ④ 근거 질문
def qa_scores() -> list[str]:
    path = ROOT / "evaluation" / "score_qa.md"
    if not path.exists():
        return ["- 아직 채점 안 함 (`tools/score_qa.py`)"]
    text = path.read_text(encoding="utf-8").splitlines()
    head = [line for line in text[:6] if line.startswith("#") or line.startswith("- ")]
    return [line.replace("# 근거 질문 채점", "- 마지막 채점").replace("(", "(", 1) if line.startswith("#") else line for line in head] + [
        "- 질문 평가표: 한수원·중부발전 5개씩 (그중 공고문에 없는 질문 1개씩), Claude 작성·팀원 검토 전"]


# ⑤ 30곳 범위
def coverage() -> list[str]:
    reports = sorted((ROOT / "data" / "reports").glob("report_*.json"))
    with_requirements, ocr, text_pdf, none = [], [], [], []
    for path in reports:
        report = load(path)
        requirements = report.get("requirements") or {}
        items = len(requirements.get("certificates") or []) + len(requirements.get("majors") or [])
        if items:
            with_requirements.append(report["institution"])
        bundle = ROOT / "stage2" / f"bundle_{report['curr']['sn']}.json"
        if not bundle.exists():
            none.append(report["institution"])
        elif load(bundle).get("source") in ("ocr", "hwp", "attach"):
            ocr.append(report["institution"])
        else:
            text_pdf.append(report["institution"])
    lines = [
        f"- 리포트: {len(reports)}곳",
        f"- 지원 자격(전공·자격증·가점) 있는 곳: {pct(len(with_requirements), len(reports))}",
        f"- 올해 공고문 원문 글자: PDF {len(text_pdf)}곳 · 그림·스캔을 AI가 옮겨 적음 {len(ocr)}곳"
        + (f" ({', '.join(ocr)})" if ocr else "") + (f" · 없음 {len(none)}곳 ({', '.join(none)})" if none else ""),
    ]
    missing = [load(path)["institution"] for path in reports if load(path)["institution"] not in with_requirements]
    if missing:
        lines.append(f"- 지원 자격 없는 곳: {', '.join(missing)} → 판정 '애매'")
    return lines


# ⑥ 테스트
def run_tests() -> list[str]:
    result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    tail = [line for line in result.stdout.splitlines() if line.strip()][-1:] or ["(출력 없음)"]
    failed = [line for line in result.stdout.splitlines() if line.startswith("FAILED")]
    return [f"- `pytest -q`: {tail[0]}"] + [f"  - {line}" for line in failed[:20]]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="최종 측정 → evaluation/final-report.md")
    parser.add_argument("--all", action="store_true", help="자동 테스트(pytest)까지 실행")
    args = parser.parse_args(argv)

    sections = [
        ("① 지원 자격·가점·화면 판정 (3곳 정답지 대비)", requirements_scores),
        ("② 작년 대비 변경점 (한전 원문 대조 대비)", change_scores),
        ("③ 핵심 숫자 (인원·배수·면접 배점, 정답지 요약 대비)", number_scores),
        ("④ 근거 질문 (마지막 AI 채점)", qa_scores),
        ("⑤ 30곳 데이터 범위", coverage),
    ]
    if args.all:
        sections.append(("⑥ 자동 테스트", run_tests))

    lines = [
        "# 공채레이더 최종 측정 결과",
        "",
        f"- 측정 시각: {datetime.now():%Y-%m-%d %H:%M} · `evaluation/evaluate.py{' --all' if args.all else ''}` 실행 결과 그대로",
        "- AI를 새로 부르지 않고 저장된 결과로 잼. 정답지는 3곳(한전·한수원·중부발전)뿐이라 나머지 27곳 정확도는 직접 잰 값이 아님",
        "- 측정하지 않은 것(시간 절감, 27곳 정확도, 한수원·중부발전 변경점)은 숫자를 만들지 않음",
        "- 개선 과정과 단계별 %는 `evaluation/정확도_개선_기록.md`",
        "",
    ]
    for title, func in sections:
        print(f"{title} ...")
        try:
            body = func()
        except Exception as exc:  # noqa: BLE001 - 한 항목이 실패해도 나머지는 기록
            body = [f"- 측정 실패: {exc}"]
        lines += [f"## {title}", "", *body, ""]
        for line in body:
            print("  " + line)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n결과: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
