# -*- coding: utf-8 -*-
"""
공공기관 채용정보 오픈API 확인용 테스트 (표준 라이브러리만 사용)

확인하는 것
  1) API가 정상 응답하는지
  2) 과거 공고가 언제까지 조회되는지 (가장 오래된 공고 날짜)
  3) 응답에 공고문 PDF 같은 첨부파일 정보가 들어 있는지

실행 방법 (Windows PowerShell)
  $env:JOB_API_KEY = "여기에_일반인증키(Decoding)"
  python api_test.py

결과는 화면과 api_result.txt 에 저장됩니다. 인증키는 결과에 찍히지 않습니다.
api_result.txt 내용만 공유하세요. 인증키는 절대 공유하지 마세요.
"""
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from collections import Counter

BASE_URL = "http://apis.data.go.kr/1051000/recruitment/list"
ROWS = 100
OUT = []


def log(*args):
    line = " ".join(str(a) for a in args)
    print(line)
    OUT.append(line)


def call(key, **params):
    q = {"serviceKey": key, "resultType": "json", "numOfRows": ROWS}
    q.update(params)
    url = BASE_URL + "?" + urllib.parse.urlencode(q)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            text = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        # 오류 메시지에 인증키가 섞이지 않도록 가림
        raise SystemExit("요청 실패: " + str(e).replace(key, "***"))
    try:
        data = json.loads(text)
    except Exception:
        raise SystemExit("JSON 해석 실패. 응답 앞부분: " + text[:300].replace(key, "***"))
    if str(data.get("resultCode")) != "200":
        raise SystemExit(f"API 오류 {data.get('resultCode')}: {data.get('resultMsg')}")
    return data


def date_fields(item):
    return {k: v for k, v in item.items()
            if any(t in k.lower() for t in ("ymd", "dt", "date"))}


def main():
    key = os.environ.get("JOB_API_KEY", "").strip()
    if not key:
        raise SystemExit("JOB_API_KEY 환경변수가 없습니다. 실행 방법을 확인하세요.")

    # 1) 첫 페이지 (마감된 공고 포함)
    first = call(key, pageNo=1, ongoingYn="N")
    total = int(first.get("totalCount") or 0)
    items = first.get("result") or []
    log("== 1. 기본 응답")
    log("전체 공고 수(totalCount):", total)
    log("첫 페이지 건수:", len(items))
    if not items:
        raise SystemExit("결과가 비어 있습니다.")
    log("공고 1건의 필드 이름:", ", ".join(items[0].keys()))
    log("첫 페이지 첫 공고 날짜 필드:", json.dumps(date_fields(items[0]), ensure_ascii=False))

    # 2) 마지막 페이지 = 가장 오래된 공고 쪽
    last_page = max(1, math.ceil(total / ROWS))
    last = call(key, pageNo=last_page, ongoingYn="N")
    last_items = last.get("result") or []
    log("")
    log("== 2. 과거 공고 조회 범위")
    log("마지막 페이지 번호:", last_page, "/ 건수:", len(last_items))
    if last_items:
        log("마지막 페이지 마지막 공고 날짜 필드:",
            json.dumps(date_fields(last_items[-1]), ensure_ascii=False))
        log("마지막 페이지 마지막 공고 제목:",
            str(last_items[-1].get("recrutPbancTtl", ""))[:80])

    # 3) 첨부파일 정보
    log("")
    log("== 3. 첨부파일 정보")
    file_keys = [k for k in items[0].keys() if "file" in k.lower() or "atch" in k.lower()]
    log("첨부 관련 필드 이름:", file_keys or "없음")
    types = Counter()
    sample = None
    for it in items:
        for k in file_keys:
            v = it.get(k)
            if isinstance(v, list):
                for f in v:
                    if isinstance(f, dict):
                        types[str(f.get("atchType"))] += 1
                        if sample is None and str(f.get("atchType")) == "A":
                            sample = f
    log("첫 페이지 첨부 유형 개수 (A=공고문, B=입사지원서, C=직무기술서, Z=기타):", dict(types))
    if sample:
        log("공고문(A) 첨부 예시:", json.dumps(sample, ensure_ascii=False)[:400])

    with open("api_result.txt", "w", encoding="utf-8") as fp:
        fp.write("\n".join(OUT))
    print("\napi_result.txt 에 저장했습니다. 이 파일 내용만 공유하세요.")


if __name__ == "__main__":
    main()
