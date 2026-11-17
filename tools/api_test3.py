# -*- coding: utf-8 -*-
"""3차 확인: 상세 조회(detail?sn=)로 첨부파일·전형단계(경쟁률) 확인. 호출 6회.
실행: python api_test3.py   (같은 창이면 키 재입력 불필요)
결과: 다운로드 폴더 api_detail_<번호>.json (인증키 없음)"""
import json, os, urllib.parse, urllib.request

BASE = "http://apis.data.go.kr/1051000/recruitment/detail"
SNS = ["290666", "304551", "288681", "302968", "287235", "302314"]  # 한전, 한수원, 중부발전 (작년/올해)

key = os.environ.get("JOB_API_KEY", "").strip()
if not key:
    raise SystemExit("JOB_API_KEY 환경변수가 없습니다.")
for sn in SNS:
    url = BASE + "?" + urllib.parse.urlencode({"serviceKey": key, "resultType": "json", "sn": sn})
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            text = r.read().decode("utf-8", errors="replace")
        data = json.loads(text)
    except Exception as e:
        print(sn, "실패:", str(e).replace(key, "***")[:150])
        continue
    with open(f"api_detail_{sn}.json", "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)
    res = data.get("result")
    item = res[0] if isinstance(res, list) and res else res if isinstance(res, dict) else {}
    print(sn, "저장 /", str(item.get("recrutPbancTtl", ""))[:40],
          "/ files", len(item.get("files") or []), "/ steps", len(item.get("steps") or []))
print("끝")
