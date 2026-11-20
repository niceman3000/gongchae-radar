# -*- coding: utf-8 -*-
"""
근거 질문 기능 채점 (T031·T032 질문 평가표 사용, 실제 AI 호출)

질문 목록: evaluation/qa_questions.json (사람이 읽는 표: evaluation/questions-khnp.md, questions-komipo.md)
통과 기준
  - 정답이 있는 질문: answered + 답에 핵심 값(keywords 중 하나) + 근거 쪽이 정답 쪽 중 하나
  - 정답이 없는 질문: not_found ('공고문에 명시 없음')
  - 원문 고르기만 따로: 정답 쪽이 고른 원문 조각에 들어갔는가 (AI 호출 없이도 잼)

실행 (키를 넣은 PowerShell 창에서, 질문 10개 약 $0.15):
  .\\.venv\\Scripts\\python.exe tools\\score_qa.py
결과: evaluation/score_qa.md
"""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.model_client import AnthropicClient  # noqa: E402
from src.qa_service import ask, find_passages  # noqa: E402


def pages_of(sn: str) -> dict | None:
    path = ROOT / "stage2" / f"bundle_{sn}.json"
    return json.loads(path.read_text(encoding="utf-8")).get("all_text") if path.exists() else None


def main() -> None:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    client = AnthropicClient(key) if key else None
    if not client:
        print("API 키가 없어 원문 고르기만 채점합니다 ($env:ANTHROPIC_API_KEY = \"키\" 후 다시 실행하면 AI 답까지 채점)")
    questions = json.loads((ROOT / "evaluation" / "qa_questions.json").read_text(encoding="utf-8"))
    only = sys.argv[1] if len(sys.argv) > 1 else ""  # 질문 일부 글자로 하나만 다시 (예: "직업기초")
    rows, passed, retrieved, total = [], 0, 0, 0
    for prefix, block in questions.items():
        report = json.loads((ROOT / "data" / "reports" / f"report_{prefix}.json").read_text(encoding="utf-8"))
        curr, prev = pages_of(str(report["curr"]["sn"])), pages_of(str(report["prev"]["sn"]))
        for item in block["questions"]:
            if only and only not in item["q"]:
                continue
            total += 1
            chosen = [p["page"] for p in find_passages(item["q"], curr, prev)]
            got_pages = (not chosen) if item["expect"] == "not_found" else any(p in chosen for p in item["pages"])
            retrieved += got_pages
            if client is None:
                rows.append((block["name"], item["q"], "원문 고르기 " + ("통과" if got_pages else "실패"), "-", "-"))
                continue
            result = ask(item["q"], curr_text=curr, prev_text=prev, client=client)
            if item["expect"] == "not_found":
                ok = result.status == "not_found"
            else:
                ok = (result.status == "answered"
                      and any(word in result.answer for word in item["keywords"])
                      and any(e["page"] in item["pages"] for e in result.evidence))
            passed += ok
            evidence = ", ".join(f"{e['page']}쪽" for e in result.evidence) or "-"
            rows.append((block["name"], item["q"], "통과" if ok else "실패", result.answer.replace("|", "/")[:120], evidence))
            print(f"  {'통과' if ok else '실패'} · {block['name']} · {item['q']} → {result.status} · {result.answer[:60]} ({evidence})"
                  + ("" if ok else f"\n      사유: {result.note or '-'}"))

    lines = [f"# 근거 질문 채점 ({datetime.now():%Y-%m-%d %H:%M})", "",
             f"- 원문 고르기 (정답 쪽이 AI에 보낼 조각에 들어감 / 없는 질문은 조각 0개): {retrieved}/{total} ({retrieved / total * 100:.0f}%)"]
    if client:
        lines.append(f"- 최종 답 통과 (핵심 값 + 근거 쪽 일치 / 없는 질문은 '명시 없음'): {passed}/{total} ({passed / total * 100:.0f}%)")
    lines += ["", "| 기관 | 질문 | 결과 | 답 | 근거 |", "|---|---|---|---|---|"]
    lines += [f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in rows]
    if only:  # 하나만 다시 돌린 결과는 기록 파일을 덮어쓰지 않는다
        print(f"\n원문 고르기 {retrieved}/{total}" + (f" · 최종 답 {passed}/{total}" if client else ""))
        return
    out = ROOT / "evaluation" / "score_qa.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n원문 고르기 {retrieved}/{total}" + (f" · 최종 답 {passed}/{total}" if client else "") + f" → {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
