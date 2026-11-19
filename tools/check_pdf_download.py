# -*- coding: utf-8 -*-
"""
공고문 PDF 다운로드 점검 (API 호출 없음, 인증키 필요 없음)

2026-11-19 수집에서 data/pdf/*.pdf가 전부 8,333바이트 웹페이지("청년 일자리 지원 서비스")로 받아졌다.
첨부 주소(opendata.alio.go.kr/recruit/downloadAtchFile)를 여러 방식으로 불러 보고
어느 방식이 진짜 PDF를 주는지 출력한다.

실행: .\\.venv\\Scripts\\python.exe tools\\check_pdf_download.py
"""
from __future__ import annotations

import http.cookiejar
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def sample_url() -> tuple[str, str]:
    """수집한 상세 JSON에서 공고문(PDF) 첨부 주소 하나를 고른다."""
    pairs = json.loads((ROOT / "config/auto_pairs.json").read_text(encoding="utf-8"))["pairs"]
    for pair in pairs:
        for key in ("curr_api", "prev_api"):
            data = json.loads((ROOT / pair[key]).read_text(encoding="utf-8"))
            item = data["result"][0] if isinstance(data.get("result"), list) else data.get("result")
            for file in item.get("files") or []:
                if file.get("atchFileType") == "A" and str(file.get("atchFileNm", "")).lower().endswith(".pdf"):
                    return file["url"], f"{pair['institution']} {file['atchFileNm']}"
    raise SystemExit("PDF 첨부가 있는 공고를 찾지 못했습니다.")


def try_open(name: str, opener, url: str, headers: dict) -> bool:
    request = urllib.request.Request(url, headers=headers)
    try:
        with opener.open(request, timeout=30) as response:
            body = response.read()
            final = response.geturl()
            kind = response.headers.get("Content-Type")
            disposition = response.headers.get("Content-Disposition")
    except Exception as exc:  # noqa: BLE001
        print(f"[{name}] 실패: {exc}")
        return False
    is_pdf = body[:5] == b"%PDF-"
    print(f"[{name}] {'PDF 맞음' if is_pdf else 'PDF 아님'} | {len(body):,}바이트 | 최종 주소 {final}")
    print(f"      Content-Type: {kind} | Content-Disposition: {disposition}")
    if not is_pdf:
        print(f"      앞부분: {body[:80]!r}")
    return is_pdf


def main() -> None:
    url, label = sample_url()
    print(f"점검할 파일: {label}\n주소: {url}\n")
    plain = urllib.request.build_opener()
    jar = http.cookiejar.CookieJar()
    session = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    results = {}
    results["1 지금 방식(UA만)"] = try_open("1 지금 방식(UA만)", plain, url, {"User-Agent": "Mozilla/5.0"})
    results["2 브라우저 UA+Referer"] = try_open("2 브라우저 UA+Referer", plain, url, {
        "User-Agent": UA, "Referer": "https://opendata.alio.go.kr/", "Accept": "*/*"})
    try:
        session.open(urllib.request.Request("https://opendata.alio.go.kr/", headers={"User-Agent": UA}), timeout=30).read()
    except Exception as exc:  # noqa: BLE001
        print(f"(첫 화면 방문 실패: {exc})")
    results["3 첫 화면 방문 후(쿠키)"] = try_open("3 첫 화면 방문 후(쿠키)", session, url, {
        "User-Agent": UA, "Referer": "https://opendata.alio.go.kr/", "Accept": "*/*"})
    results["4 http 주소"] = try_open("4 http 주소", plain, url.replace("https://", "http://"), {
        "User-Agent": UA, "Referer": "http://opendata.alio.go.kr/"})

    from collect_institutions import attachment_urls
    new_url = attachment_urls(url)[0]
    print(f"\n새 주소: {new_url}")
    results["5 새 주소(www.alio.go.kr)"] = try_open("5 새 주소(www.alio.go.kr)", plain, new_url, {
        "User-Agent": UA, "Referer": "https://job.alio.go.kr/", "Accept": "*/*"})

    ok = [name for name, passed in results.items() if passed]
    print("\n결과:", ("성공한 방식 → " + ", ".join(ok)) if ok else "모든 방식 실패 (위 '최종 주소'와 '앞부분'을 Claude에게 보여 주세요)")


if __name__ == "__main__":
    sys.exit(main())
