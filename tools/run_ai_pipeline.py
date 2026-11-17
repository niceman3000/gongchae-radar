"""공고쌍의 AI 구조화·문구 분류·리포트 재생성을 실행한다."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tomllib


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ai_pipeline import (  # noqa: E402
    DEFAULT_CLASSIFY_MODEL,
    DEFAULT_EXTRACT_MODEL,
    AiPipelineError,
    run_pair,
)
from src.model_client import AnthropicClient, ModelClientError  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair", default="kepco-2025-2026-h2")
    parser.add_argument("--check", action="store_true", help="호출 없이 실행 준비상태만 확인")
    return parser.parse_args()


def load_secret(name: str) -> str:
    environment_value = os.environ.get(name, "").strip()
    if environment_value:
        return environment_value
    secrets_path = ROOT / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return ""
    try:
        with secrets_path.open("rb") as stream:
            value = tomllib.load(stream).get(name, "")
    except (OSError, tomllib.TOMLDecodeError):
        return ""
    return str(value).strip()


def main() -> None:
    args = parse_args()
    key = load_secret("ANTHROPIC_API_KEY")
    if args.check:
        print(f"pair={args.pair}")
        print(f"ANTHROPIC_API_KEY={'configured' if key else 'missing'}")
        print(f"extract_model={load_secret('MODEL_EXTRACT') or DEFAULT_EXTRACT_MODEL}")
        print(f"classify_model={load_secret('MODEL_CLASSIFY') or DEFAULT_CLASSIFY_MODEL}")
        return

    try:
        client = AnthropicClient(key)
        paths = run_pair(
            args.pair,
            client,
            extract_model=load_secret("MODEL_EXTRACT") or DEFAULT_EXTRACT_MODEL,
            classify_model=load_secret("MODEL_CLASSIFY") or DEFAULT_CLASSIFY_MODEL,
        )
    except (AiPipelineError, ModelClientError) as exc:
        raise SystemExit(str(exc)) from exc

    for path in paths:
        print(f"생성: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
