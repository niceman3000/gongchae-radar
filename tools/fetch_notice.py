# -*- coding: utf-8 -*-
"""
공고번호로 API 상세 조회 + 공고문 PDF 다운로드 (표준 라이브러리만 사용)

사용법 (프로젝트 최상위 폴더에서)
  $env:JOB_API_KEY = "data.go.kr 일반 인증키(Decoding)"
  python tools/fetch_notice.py 290666 304551

결과
  data/api/api_detail_<번호>.json   API 상세 원본
  data/pdf/<번호>.pdf               공고문(첨부유형 A) PDF
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

DETAIL = "http://apis.data.go.kr/1051000/recruitment/detail"
ROOT = Path(__file__).resolve().parent.parent


def main():
    key = os.environ.get("JOB_API_KEY", "").strip()
    if not key or len(sys.argv) < 2:
        raise SystemExit("사용법: JOB_API_KEY 설정 후  python tools/fetch_notice.py <공고번호> [공고번호 ...]")
    (ROOT / "data/api").mkdir(parents=True, exist_ok=True)
    (ROOT / "data/pdf").mkdir(parents=True, exist_ok=True)
    for sn in sys.argv[1:]:
        url = DETAIL + "?" + urllib.parse.urlencode({"serviceKey": key, "resultType": "json", "sn": sn})
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        if str(data.get("resultCode")) != "200":
            print(sn, "API 오류:", data.get("resultMsg"))
            continue
        (ROOT / f"data/api/api_detail_{sn}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        item = data["result"][0] if isinstance(data["result"], list) else data["result"]
        notices = [f for f in item.get("files") or [] if f.get("atchFileType") == "A"]
        if not notices:
            print(sn, "공고문(A) 첨부 없음:", item.get("nonatchRsn"))
            continue
        f = notices[0]
        if not f["atchFileNm"].lower().endswith(".pdf"):
            print(sn, "PDF가 아님(HWP 등) → 수동 변환 필요:", f["atchFileNm"])
            continue
        req = urllib.request.Request(f["url"], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            pdf = r.read()
        out = ROOT / f"data/pdf/{sn}.pdf"
        out.write_bytes(pdf)
        print(f"{sn} {item.get('instNm')} | {item.get('recrutPbancTtl')} | PDF {len(pdf):,} bytes → {out.name}")


if __name__ == "__main__":
    main()
