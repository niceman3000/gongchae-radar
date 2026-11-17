# -*- coding: utf-8 -*-
"""
2차 확인: files / steps 구조, 한전 대졸 공고 2건(2025·2026 하반기) 원본 저장

실행 (같은 PowerShell 창이면 키를 다시 넣을 필요 없음)
  python api_test2.py

결과 파일 (다운로드 폴더, 인증키 없음)
  api_result2.txt          요약
  api_sample_item.json     files/steps가 들어 있는 공고 1건 원본
  api_kepco_<번호>.json    한전 공고 원본 (찾은 경우)
호출 횟수는 최대 약 60회로 제한합니다.
"""
import json
import os
import urllib.parse
import urllib.request

BASE = "http://apis.data.go.kr/1051000/recruitment"
ROWS = 100
TARGETS = {"290666", "304551"}   # 잡알리오 공고번호: 한전 4직급 대졸 2025·2026 하반기
OUT = []
CALLS = 0
MAX_CALLS = 60


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    OUT.append(s)


def call(key, path="list", **params):
    global CALLS
    if CALLS >= MAX_CALLS:
        raise RuntimeError("호출 한도 도달")
    CALLS += 1
    q = {"serviceKey": key, "resultType": "json"}
    q.update(params)
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(q)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            text = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return {"_error": str(e).replace(key, "***")}
    try:
        return json.loads(text)
    except Exception:
        return {"_error": "JSON 아님: " + text[:200].replace(key, "***")}


def save(name, obj):
    with open(name, "w", encoding="utf-8") as fp:
        json.dump(obj, fp, ensure_ascii=False, indent=2)
    log("저장:", name)


def main():
    key = os.environ.get("JOB_API_KEY", "").strip()
    if not key:
        raise SystemExit("JOB_API_KEY 환경변수가 없습니다.")

    # 1) files / steps 가 채워진 공고 찾기 (최근 공고, 진행중 포함)
    log("== 1. files / steps 구조")
    sample, kepco_code = None, None
    for page in range(1, 6):
        d = call(key, pageNo=page, numOfRows=ROWS)
        items = d.get("result") or []
        for it in items:
            if kepco_code is None and it.get("instNm") == "한국전력공사":
                kepco_code = it.get("pblntInstCd")
            if sample is None and it.get("files") and it.get("steps"):
                sample = it
        if sample and kepco_code:
            break
    if sample:
        log("files 예시:", json.dumps(sample.get("files"), ensure_ascii=False)[:600])
        log("steps 예시:", json.dumps(sample.get("steps"), ensure_ascii=False)[:800])
        save("api_sample_item.json", sample)
    else:
        log("files 와 steps 가 둘 다 채워진 공고를 못 찾음")
    log("한국전력공사 기관코드(pblntInstCd):", kepco_code)

    # 2) 한전 공고만 걸러서 대상 2건 찾기
    log("")
    log("== 2. 한전 대졸 공고 2건 찾기")
    found = {}
    if kepco_code:
        page = 1
        while page <= 40 and len(found) < len(TARGETS):
            d = call(key, pageNo=page, numOfRows=ROWS, pblntInstCd=kepco_code)
            items = d.get("result") or []
            if page == 1:
                log("한전 공고 총 건수:", d.get("totalCount"), d.get("_error", ""))
            if not items:
                break
            for it in items:
                sn = str(it.get("recrutPblntSn"))
                if sn in TARGETS:
                    found[sn] = it
            page += 1
        for sn, it in found.items():
            log(f"[{sn}] {it.get('recrutPbancTtl')} / 채용인원 {it.get('recrutNope')} / "
                f"files {len(it.get('files') or [])}개 / steps {len(it.get('steps') or [])}개")
            save(f"api_kepco_{sn}.json", it)
        missing = TARGETS - set(found)
        if missing:
            log("못 찾은 공고번호:", ", ".join(sorted(missing)),
                "(공고번호가 잡알리오 번호와 다를 수 있음)")
    else:
        log("기관코드를 몰라 건너뜀")

    # 3) 상세 조회 주소가 따로 있는지 시험
    log("")
    log("== 3. 상세 조회 주소 시험")
    for path, p in (("detail", {"sn": "290666"}), ("detail", {"recrutPblntSn": "290666"})):
        d = call(key, path=path, **p)
        log(f"{path} {p}:", d.get("_error") or f"resultCode={d.get('resultCode')} {str(d.get('resultMsg'))[:60]}")

    log("")
    log("총 호출 횟수:", CALLS)
    with open("api_result2.txt", "w", encoding="utf-8") as fp:
        fp.write("\n".join(OUT))
    print("\n끝. 다운로드 폴더의 결과 파일은 제가 직접 가져갈 수 있어요.")


if __name__ == "__main__":
    main()
