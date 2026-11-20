# -*- coding: utf-8 -*-
"""
근거 질문 기능 점검 (화면 없이 질문 하나 보내 보기)

실행 (키를 넣은 PowerShell 창에서):
  .\\.venv\\Scripts\\python.exe tools\\check_qa.py
  .\\.venv\\Scripts\\python.exe tools\\check_qa.py "전기기사 가점 몇 점이야?" khnp
비용: 질문 하나 약 $0.015
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.model_client import AnthropicClient  # noqa: E402
from src.qa_service import DEFAULT_QA_MODEL, ask, find_passages  # noqa: E402


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else "토익 몇 점 필요해?"
    prefix = sys.argv[2] if len(sys.argv) > 2 else "kepco"
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    print(f"1) API 키: {'있음 (' + key[:7] + '...)' if key else '없음 → $env:ANTHROPIC_API_KEY = \"키\" 를 이 창에서 먼저 입력'}")
    print(f"   모델: {DEFAULT_QA_MODEL}")

    report = json.loads((ROOT / "data" / "reports" / f"report_{prefix}.json").read_text(encoding="utf-8"))
    def pages(sn):
        path = ROOT / "stage2" / f"bundle_{sn}.json"
        return json.loads(path.read_text(encoding="utf-8")).get("all_text") if path.exists() else None
    curr, prev = pages(report["curr"]["sn"]), pages(report["prev"]["sn"])
    print(f"2) 공고: {report['institution']} · 공고문 글자 {'있음' if curr else '없음'}")
    passages = find_passages(question, curr, prev)
    print(f"3) 질문 '{question}' → 관련 원문 {len(passages)}조각 (쪽: {[item['page'] for item in passages]})")
    if not key:
        return

    client = AnthropicClient(key)
    try:  # 원본 응답도 보기
        raw = client.complete(model=DEFAULT_QA_MODEL, system="한 단어로 답해.", user="안녕", max_tokens=200,
                              **({"thinking": {"type": "between_tools"}} if DEFAULT_QA_MODEL == "claude-sonnet-5-5" else {}))
        print(f"4) AI 연결 시험: 성공 · 답 '{raw.text[:30]}' · stop_reason={raw.stop_reason}")
    except Exception as exc:  # noqa: BLE001
        print(f"4) AI 연결 시험: 실패 → {exc}")
        return
    result = ask(question, curr_text=curr, prev_text=prev, client=client)
    print(f"5) 결과: {result.status} · AI 불렀나: {result.model_called} · 사유: {result.note or '-'}")
    print(f"   답: {result.answer}")
    for item in result.evidence:
        print(f"   근거: {item['side']} {item['page']}쪽 “{item['quote']}”")


if __name__ == "__main__":
    main()
