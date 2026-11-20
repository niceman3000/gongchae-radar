# -*- coding: utf-8 -*-
"""
배포·제출 전 키 노출 점검 (tasks.md T036)

1) Git에 올라가는 파일(git ls-files + 아직 안 올린 새 파일)에서
   - 지금 PowerShell 창에 넣은 진짜 키 값(ANTHROPIC_API_KEY, JOB_API_KEY)이 그대로 들어 있는지
   - Anthropic 키 모양(sk-ant-...), data.go.kr 주소의 serviceKey=값 이 들어 있는지
2) .streamlit/secrets.toml, .env 가 Git에 올라가 있지 않은지 (.gitignore에 걸리는지)

키 값은 화면에 찍지 않는다 (파일 이름과 줄 번호만).
실행: .\\.venv\\Scripts\\python.exe tools\\check_secrets.py      (키를 넣은 창에서 돌리면 진짜 값까지 검사)
문제가 없으면 '키 노출 0' 출력, 있으면 종료 코드 1.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
SECRET_FILES = [".streamlit/secrets.toml", ".env"]
PATTERNS = {
    "Anthropic 키 모양": re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    "data.go.kr serviceKey 값": re.compile(r"serviceKey=(?!\{|<|%s|\"|')[A-Za-z0-9%+/=]{20,}"),
}
SKIP_SUFFIX = {".pdf", ".png", ".jpg", ".jpeg", ".otf", ".ttf", ".zip", ".hwp", ".pyc"}
MAX_BYTES = 5_000_000


def git_files() -> list[str]:
    def run(*args: str) -> list[str]:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return [line for line in out.stdout.splitlines() if line.strip()]

    return sorted(set(run("ls-files") + run("ls-files", "--others", "--exclude-standard")))


def is_ignored(path: str) -> bool:
    return subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT).returncode == 0


def main() -> int:
    problems: list[str] = []
    files = git_files()
    if not files:
        print("Git 파일 목록을 못 읽었습니다 (git 설치·폴더 확인).")
        return 1

    values = {name: os.environ.get(name, "").strip() for name in ("ANTHROPIC_API_KEY", "JOB_API_KEY")}
    values = {name: value for name, value in values.items() if len(value) >= 12}
    print(f"검사할 파일 {len(files)}개 · 진짜 키 값 비교: {', '.join(values) or '없음 (창에 키를 넣지 않음 → 모양으로만 검사)'}")

    for name in files:
        path = ROOT / name
        if path.suffix.lower() in SKIP_SUFFIX or not path.is_file() or path.stat().st_size > MAX_BYTES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for env_name, value in values.items():
                if value in line:
                    problems.append(f"{name}:{number} — {env_name} 진짜 값")
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    problems.append(f"{name}:{number} — {label}")

    for secret in SECRET_FILES:
        if secret in files:
            problems.append(f"{secret} — Git에 올라가 있음 (git rm --cached {secret})")
        elif (ROOT / secret).exists() and not is_ignored(secret):
            problems.append(f"{secret} — .gitignore에 안 걸림")

    if problems:
        print(f"\n키 노출 의심 {len(problems)}건:")
        for item in problems:
            print("  " + item)
        return 1
    print("\n키 노출 0 (진짜 값·키 모양·secrets 파일 모두 이상 없음)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
