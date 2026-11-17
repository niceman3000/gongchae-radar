# -*- coding: utf-8 -*-
"""
2단계: Claude가 공고문 PDF(관련 쪽만)를 읽고 정해진 칸을 채운 뒤, 코드가 인용을 검증한다.
+ 1단계에서 '문구 변경'으로 넘어온 줄을 Claude가 실질/표현 변경으로 분류한다.

실행 (이 폴더에서, 표준 라이브러리만 사용)
  $env:ANTHROPIC_API_KEY = "sk-ant-..."
  python stage2.py                                         # 기본: 한전 쌍
  python stage2.py 287235 302314 "중부발전 4직급(제2차)"     # 다른 쌍

입력: bundle_290666.json, bundle_304551.json (PDF에서 뽑은 쪽별 텍스트·표), stage1_result.json
출력: extract_<번호>.json, text_class.json, usage.json   (API 키는 어디에도 저장되지 않음)
"""
import json
import os
import re
import time
import urllib.request

API = "https://api.anthropic.com/v1/messages"
MODEL_EXTRACT = os.environ.get("MODEL_EXTRACT", "claude-sonnet-5")
MODEL_CLASSIFY = os.environ.get("MODEL_CLASSIFY", "claude-haiku-4-5")
PAIR = ("290666", "304551")              # 한전 4직급 대졸 하반기 2025, 2026
PAIR_NAME = "한전 4직급 대졸(하반기)"
FOCUS_UNITS = "전기 직렬(배전, 송변전, 발전(전기) 등)"
USAGE = []

EXTRACT_SYSTEM = f"""너는 공공기관 채용공고문에서 정보를 추출하는 도구다. 규칙:
1. 아래 [공고문] 텍스트에 적힌 내용만 쓴다. 추측·일반 지식 금지.
2. 모든 값에 evidence를 단다: page(쪽 번호)와 quote(그 쪽 텍스트에서 그대로 복사한 30자 이내 구절).
   quote는 반드시 원문 글자 그대로여야 한다. 표 값이면 그 표의 행 이름이나 숫자가 들어간 구절을 복사한다.
3. 공고에 없으면 value를 null로, status를 "명시 없음"으로 둔다. 애매하면 status "확인 필요".
4. 모집단위는 {FOCUS_UNITS}만 추출한다. 공고 전체에 해당하는 내용은 notice_level에 넣는다.
5. 출력은 JSON 하나만. 설명 문장, 코드블록 표시 없이.
출력 형식:
{{"units":[{{"unit_name":"","headcount_by_region":[{{"region":"","value":0,"evidence":{{"page":0,"quote":""}}}}],
"headcount_total":{{"value":0,"evidence":{{"page":0,"quote":""}}}},
"required_qualifications":[{{"item":"","evidence":{{"page":0,"quote":""}}}}],
"certificate_bonus":[{{"certificate":"","points":0,"stage":"","evidence":{{"page":0,"quote":""}}}}],
"stages":[{{"stage":"","components":[{{"name":"","points":0}}],"pass_multiple":"","pass_rule":"","evidence":{{"page":0,"quote":""}}}}],
"regional_talent":{{"rule":"","evidence":{{"page":0,"quote":""}}}},
"status":"확인"}}],
"notice_level":{{"schedule":[{{"step":"","date":"","evidence":{{"page":0,"quote":""}}}}],
"advance_notices":[{{"content":"","effective_from":"","evidence":{{"page":0,"quote":""}}}}]}}}}"""

CLASSIFY_SYSTEM = """너는 채용공고의 작년/올해 문장 변화를 분류한다. 각 항목마다:
- label: "실질 변경"(지원 자격·점수·절차·대상이 실제로 달라짐) 또는 "표현 변경"(뜻은 같고 표현만 다름)
- who_is_affected: 영향을 받는 지원자 (없으면 "영향 없음")
- one_line: 지원자에게 보여 줄 한 줄 설명 (40자 이내, 주어진 문장에 근거해서만)
- confidence: "높음" 또는 "낮음"
입력에 없는 사실은 쓰지 않는다. 출력은 JSON 배열 하나만: [{"id":0,"label":"","who_is_affected":"","one_line":"","confidence":""}]"""


def call_claude(key, model, system, user, max_tokens=8000):
    body = json.dumps({"model": model, "max_tokens": max_tokens, "system": system,
                       "messages": [{"role": "user", "content": user}]}).encode("utf-8")
    req = urllib.request.Request(API, data=body, method="POST", headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"API 오류 {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
    text = "".join(c.get("text", "") for c in data.get("content", []))
    u = data.get("usage", {})
    USAGE.append({"model": model, "input_tokens": u.get("input_tokens"),
                  "output_tokens": u.get("output_tokens"), "seconds": round(time.time() - t0, 1)})
    return text


def parse_json(text):
    m = re.search(r"[\[{].*[\]}]", text, re.S)
    return json.loads(m.group(0)) if m else None


def norm(s):
    return re.sub(r"[\s|]", "", s or "")


def verify(obj, all_text, stats):
    """evidence.quote 가 해당 쪽 원문에 실제로 있는지 코드로 확인"""
    if isinstance(obj, dict):
        ev = obj.get("evidence")
        if isinstance(ev, dict) and ev.get("quote"):
            q, pg = norm(ev["quote"]), str(ev.get("page"))
            on_page = q in norm(all_text.get(pg, ""))
            anywhere = on_page or any(q in norm(t) for t in all_text.values())
            ev["verified"] = "쪽 일치" if on_page else ("다른 쪽에 있음" if anywhere else "원문에 없음")
            stats[ev["verified"]] = stats.get(ev["verified"], 0) + 1
        for v in obj.values():
            verify(v, all_text, stats)
    elif isinstance(obj, list):
        for v in obj:
            verify(v, all_text, stats)


def pages_prompt(bundle):
    parts = []
    for p in bundle["pages"]:
        parts.append(f"=== {p['page']}쪽 ===\n{p['text']}")
        if p["tables"].strip():
            parts.append(f"--- {p['page']}쪽 표 ---\n{p['tables']}")
    return "[공고문]\n" + "\n".join(parts)


def main():
    global PAIR, PAIR_NAME
    import sys
    if len(sys.argv) >= 4:  # python stage2.py <작년번호> <올해번호> "<1단계 결과의 쌍 이름>"
        PAIR, PAIR_NAME = (sys.argv[1], sys.argv[2]), sys.argv[3]
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY 환경변수가 없습니다.")

    # A) 공고문 추출 + 인용 검증
    for sn in PAIR:
        bundle = json.load(open(f"bundle_{sn}.json", encoding="utf-8"))
        print(f"[{sn}] {len(bundle['sent_pages'])}쪽 보냄 {bundle['sent_pages']} ...")
        result = None
        for attempt in range(2):
            result = parse_json(call_claude(key, MODEL_EXTRACT, EXTRACT_SYSTEM, pages_prompt(bundle)))
            if result:
                break
            print("  JSON 해석 실패, 한 번 더 시도")
        if not result:
            raise SystemExit("추출 실패")
        stats = {}
        verify(result, bundle["all_text"], stats)
        result["_meta"] = {"sn": sn, "model": MODEL_EXTRACT, "sent_pages": bundle["sent_pages"],
                           "quote_check": stats}
        json.dump(result, open(f"extract_{sn}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"  저장 extract_{sn}.json / 인용 검증 {stats}")

    # B) 1단계 '문구 변경' 줄 분류 (바뀐 두 줄만 보냄)
    s1 = json.load(open("stage1_result.json", encoding="utf-8"))[PAIR_NAME]
    items = [c for c in s1["changes"] if c["type"] == "text"]
    payload = [{"id": i, "field": c["field"], "prev": c["prev"], "curr": c["curr"]} for i, c in enumerate(items)]
    out = parse_json(call_claude(key, MODEL_CLASSIFY, CLASSIFY_SYSTEM,
                                 json.dumps(payload, ensure_ascii=False), max_tokens=2000)) or []
    for o in out:
        if isinstance(o, dict) and isinstance(o.get("id"), int) and o["id"] < len(payload):
            o.update({k: payload[o["id"]][k] for k in ("field", "prev", "curr")})
    json.dump(out, open("text_class.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"문구 변경 {len(payload)}건 분류 → text_class.json")

    json.dump(USAGE, open("usage.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    tin = sum(u["input_tokens"] or 0 for u in USAGE)
    tout = sum(u["output_tokens"] or 0 for u in USAGE)
    print(f"끝. 호출 {len(USAGE)}회, 입력 토큰 {tin:,}, 출력 토큰 {tout:,} → usage.json")


if __name__ == "__main__":
    main()
