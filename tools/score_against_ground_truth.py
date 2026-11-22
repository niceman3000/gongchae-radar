# -*- coding: utf-8 -*-
"""
AI 추출 결과 채점 (정답지 = 핵심 3곳 원문 대조 결과, AI 호출 없음)

30곳 모두 같은 자동 과정(코드 비교 + AI 조건 추출)으로 화면에 보여준다.
그 정확도를 재려고 핵심 3곳(한전·한수원·중부발전)은 원문을 대조한 정답지를 따로 둔다:
  evaluation/ground_truth/<기관>_requirements.json   ← 정답지
  evaluation/ai_extracted/<기관>_requirements.json   ← AI 결과 (화면에 쓰는 것)

채점 항목
  1) 자격증 가점: (직렬, 자격증, 점수)가 정답지와 같은가 → 재현율(정답 중 맞힌 비율)·정밀도(AI 답 중 맞은 비율)
  2) 지원 가능 자격증(비전공자 지원 등): (직렬, 자격증) 재현율·정밀도
  3) 사용자 화면 판정 일치율: 직렬 × 자격증(없음 + 자주 쓰는 자격증 하나씩) 조건마다
     정답지로 판정한 결과와 AI 결과로 판정한 결과(지원 가능/애매/불가, 가점 합)가 같은가

실행 (리포트를 만든 뒤):
  .\\.venv\\Scripts\\python.exe tools\\score_against_ground_truth.py
결과: evaluation/score_requirements.md
"""
from __future__ import annotations

from datetime import date
import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.certificates import COMMON_CERTIFICATES, GRADE_RANK, item_names, normalize  # noqa: E402
from src.eligibility import UserCondition, evaluate  # noqa: E402
from src.report_builder import _reviewed_requirements, load_api_item  # noqa: E402

CORE = {"kepco": "한국전력공사", "khnp": "한국수력원자력", "komipo": "한국중부발전"}
GRADES = sorted(GRADE_RANK, key=GRADE_RANK.get)


def _key(name: str) -> str:
    """'한국사능력검정시험3급이상'과 '한국사능력검정시험3급'은 같은 기준 (11-22: 양쪽에 똑같이 적용)"""
    return re.sub(r"이상$", "", normalize(name))


def expand(match: dict) -> set[str]:
    """인정 목록 → 자격증 이름 집합 (이름 나열 + 종목×등급). 앱 판정과 같은 규칙으로 묶음 종목(비파괴검사)을 펼침."""
    names = {_key(name) for name in match.get("names") or []}
    for item in item_names(match.get("items") or []):
        for grade in match.get("grades") or []:
            names.add(_key(f"{item}{grade}"))
    return names


def table(requirements: dict, kinds: set[str]) -> dict[tuple[str, str], set]:
    """{(직렬 또는 '*', 자격증): {점수}} — 직렬이 비어 있으면 모든 직렬('*')."""
    out: dict[tuple[str, str], set] = {}
    for item in requirements.get("items") or []:
        if item.get("kind") not in kinds:
            continue
        for cert in expand(item.get("match") or {}):
            out.setdefault((item.get("track") or "*", cert), set()).add(item.get("points"))
    return out


def lookup(other: dict, track: str, cert: str) -> set:
    return other.get((track, cert), set()) | other.get(("*", cert), set()) | (
        set().union(*[points for (t, c), points in other.items() if c == cert]) if track == "*" else set()
    )


def compare_table(truth: dict, ai: dict, with_points: bool) -> tuple[int, int, int, int, list[str]]:
    """(정답 중 맞힘, 정답 수, AI 중 맞음, AI 수, 틀린 예)"""
    misses = []
    hit_truth = 0
    for (track, cert), points in truth.items():
        found = lookup(ai, track, cert)
        ok = bool(found) and (not with_points or bool(points & found))
        hit_truth += ok
        if not ok and len(misses) < 8:
            misses.append(f"정답에만: {track} {cert} {sorted(map(str, points)) if with_points else ''}".rstrip())
    hit_ai = 0
    for (track, cert), points in ai.items():
        found = lookup(truth, track, cert)
        ok = bool(found) and (not with_points or bool(points & found))
        hit_ai += ok
        if not ok and len(misses) < 16:
            misses.append(f"AI에만: {track} {cert} {sorted(map(str, points)) if with_points else ''}".rstrip())
    return hit_truth, len(truth), hit_ai, len(ai), misses


def pct(a: int, b: int) -> str:
    return f"{a / b * 100:.0f}% ({a}/{b})" if b else "- (0/0)"


def judgement_agreement(report: dict, truth_req: dict, ai_req: dict) -> tuple[int, int, list[str]]:
    """같은 조건으로 정답지 판정 vs AI 판정이 같은 비율."""
    truth_report = {**report, "requirements": truth_req}
    report = {**report, "requirements": ai_req}
    regions = (report.get("requirements") or {}).get("regions") or []
    region = regions[0] if regions else "서울"
    tracks = sorted({unit["track"] for unit in (report.get("requirements") or {}).get("units") or []} - {"기타"})
    same = total = 0
    diffs = []
    for track in tracks:
        for certs in [()] + [(name,) for name in COMMON_CERTIFICATES]:
            condition = UserCondition(track, region, certs)
            a, b = evaluate(condition, truth_report), evaluate(condition, report)
            # 가점은 모집단위 하나에 지원하므로 더하지 않고 '받을 수 있는 가장 높은 가점'으로 비교한다
            # (11-19 중부발전: 대졸 10점 + 고졸 10점을 더해 20점으로 잘못 셈)
            key_a = (a.status, max([float(row["points"] or 0) for row in a.bonus] or [0]))
            key_b = (b.status, max([float(row["points"] or 0) for row in b.bonus] or [0]))
            total += 1
            if key_a == key_b:
                same += 1
            elif len(diffs) < 10:
                diffs.append(f"{track}·{certs[0] if certs else '자격증 없음'}: 정답 {a.label} 가점 {key_a[1]:g} / AI {b.label} 가점 {key_b[1]:g}")
    return same, total, diffs


def main() -> None:
    pairs = {pair["pair_id"].split("-", 1)[0]: pair for pair in json.loads(
        (ROOT / "config" / "demo_pairs.json").read_text(encoding="utf-8"))["pairs"]}
    lines = [f"# AI 지원 자격·가점 추출 채점 ({date.today().isoformat()})", "",
             "정답지: `evaluation/ground_truth/<기관>_requirements.json` (핵심 3곳 원문 대조) · "
             "AI 결과: `evaluation/ai_extracted/<기관>_requirements.json` (화면에 쓰는 것)", ""]
    totals = {"bonus": [0, 0, 0, 0], "accepted": [0, 0, 0, 0], "judge": [0, 0]}
    for prefix, name in CORE.items():
        truth_path = ROOT / "evaluation" / "ground_truth" / f"{prefix}_requirements.json"
        ai_path = ROOT / "evaluation" / "ai_extracted" / f"{prefix}_requirements.json"
        report_path = ROOT / "data" / "reports" / f"report_{prefix}.json"
        if not (truth_path.exists() and ai_path.exists() and report_path.exists()):
            print(f"  {name}: 정답지·AI 결과·리포트 중 없는 파일이 있어 건너뜀")
            continue
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        ai = json.loads(ai_path.read_text(encoding="utf-8"))
        report = json.loads(report_path.read_text(encoding="utf-8"))

        bonus = compare_table(table(truth, {"bonus"}), table(ai, {"bonus"}), True)
        accepted = compare_table(table(truth, {"accepted", "required"}), table(ai, {"accepted", "required"}), False)
        pair = pairs[prefix]
        curr_api = load_api_item(ROOT / pair["curr_api"])
        bundle_path = ROOT / "stage2" / f"bundle_{pair['curr_sn']}.json"
        all_text = json.loads(bundle_path.read_text(encoding="utf-8")).get("all_text") if bundle_path.exists() else None
        truth_req = {**(report.get("requirements") or {}),
                     **_reviewed_requirements(curr_api, truth, all_text, pair["curr_sn"])}
        ai_req = {**(report.get("requirements") or {}),
                  **_reviewed_requirements(curr_api, ai, all_text, pair["curr_sn"])}
        same, total, diffs = judgement_agreement(report, truth_req, ai_req)

        for key, value in (("bonus", bonus), ("accepted", accepted)):
            for index in range(4):
                totals[key][index] += value[index]
        totals["judge"][0] += same
        totals["judge"][1] += total
        lines += [f"## {name}", "", f"- 정답지 정리 범위: {truth.get('scope') or '-'} / AI 정리 범위: {ai.get('scope') or '-'}",
                  f"- 자격증 가점 (직렬·자격증·점수): 재현율 {pct(bonus[0], bonus[1])} · 정밀도 {pct(bonus[2], bonus[3])}",
                  f"- 지원 가능 자격증 (직렬·자격증): 재현율 {pct(accepted[0], accepted[1])} · 정밀도 {pct(accepted[2], accepted[3])}",
                  f"- 화면 판정 일치 (지원 상태 + 가점 합): {pct(same, total)}", ""]
        if bonus[4] or accepted[4] or diffs:
            lines.append("틀린 예 (일부)")
            lines += [f"- {text}" for text in (bonus[4][:6] + accepted[4][:4] + diffs[:6])]
            lines.append("")
        print(f"  {name}: 가점 재현 {pct(bonus[0], bonus[1])}·정밀 {pct(bonus[2], bonus[3])} / "
              f"지원 자격증 재현 {pct(accepted[0], accepted[1])} / 판정 일치 {pct(same, total)}")

    b, a, j = totals["bonus"], totals["accepted"], totals["judge"]
    summary = [f"## 3곳 합계", "",
               f"- 자격증 가점: 재현율 {pct(b[0], b[1])} · 정밀도 {pct(b[2], b[3])}",
               f"- 지원 가능 자격증: 재현율 {pct(a[0], a[1])} · 정밀도 {pct(a[2], a[3])}",
               f"- 화면 판정 일치: {pct(j[0], j[1])}", "",
               "재현율 = 정답지 항목 중 AI가 맞힌 비율, 정밀도 = AI가 낸 항목 중 정답지와 맞는 비율.",
               "판정 일치 = 직렬 × (자격증 없음 + 자주 쓰는 자격증 하나씩) 조건마다 정답지와 AI 결과로 판정(지원 상태 + 받을 수 있는 최고 가점)이 같은 비율.",
               "주의: 정답지의 정리 범위(각 파일의 scope, 예: 중부발전은 대졸 기계·전기)를 넘는 AI 항목은 '정답지에 없음'으로 세져 정밀도가 낮게 나올 수 있다. 틀린 예를 사람이 원문으로 확인할 것.", ""]
    lines[4:4] = summary
    out = ROOT / "evaluation" / "score_requirements.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n합계: 가점 재현 {pct(b[0], b[1])} · 정밀 {pct(b[2], b[3])} / 판정 일치 {pct(j[0], j[1])}")
    print(f"결과: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
