# -*- coding: utf-8 -*-
"""
1단계 비교 (코드만, AI 호출 없음)

입력: 공공기관 채용정보 API 상세 조회 결과 두 개 (작년, 올해)
출력: 변경 후보 목록 (JSON) + 사람이 읽는 요약 (Markdown)

분류
  number   숫자+단위(배수·점·명·%)가 바뀜          -> 실질 변경 후보 (우선 확인)
  added    올해 새로 생긴 줄                         -> 실질 변경 후보, 2단계 AI 확인
  removed  올해 사라진 줄                            -> 실질 변경 후보, 2단계 AI 확인
  date     날짜만 바뀜 (어학 유효기간 등 매년 갱신)  -> 통상 갱신, 낮은 우선순위
  rename   행정구역 등 명칭만 바뀜                   -> 표현 변경
  expression 쉼표·괄호·'단,'만 달라 의미가 같음      -> 코드에서 제외
  text     그 밖의 문구 변경                         -> 2단계 AI가 실질/표현 분류
"""
import difflib
import json
import re
import sys
from pathlib import Path

TEXT_FIELDS = {
    "scrnprcdrMthdExpln": "전형방법",
    "aplyQlfcCn": "응시자격",
    "disqlfcRsn": "결격사유",
    "prefCn": "우대사항",
}
LIST_FIELDS = {
    "workRgnNmLst": "근무지역",
    "ncsCdNmLst": "직무분야(NCS)",
    "hireTypeNmLst": "고용형태",
    "acbgCondNmLst": "학력조건",
}
BOILERPLATE = re.compile(r"자세한 사항은 첨부파일")
# 같은 지역의 다른 이름 (2026년 광주·전남 통합 명칭 등). 비교 전에 한 이름으로 맞춘다.
ALIASES = [
    (re.compile(r"광주광역시\s*,\s*전라남도"), "전남광주"),
    (re.compile(r"광주\s*,\s*전남"), "전남광주"),
    (re.compile(r"광주전남"), "전남광주"),
]
NUM_UNIT = re.compile(r"\d+(?:\.\d+)?\s*(?:배수|점|명|%|개월)")
DATE = re.compile(r"'?\d{2}\.\s*\d{1,2}\.\s*\d{1,2}\.?|\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?"
                  r"|'?\d{2,4}년(?:도)?(?:\s*\d{1,2}월)?(?:\s*\d{1,2}일)?")
CONTENT_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
STANDALONE_DISCOURSE = re.compile(r"(?<![\w])단\s*[,，]\s*")


def canon(s):
    """띄어쓰기·문장부호 차이 제거 (표기만 다른 줄 걸러내기)"""
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u00b7", ",")
    return re.sub(r"[\s:]", "", s)


def expression_canon(s):
    """의미를 바꾸지 않는 제한적 표기 차이만 제거한다."""
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u00b7", ",")
    s = STANDALONE_DISCOURSE.sub("", s)
    return re.sub(r"[^\w]", "", s).replace("_", "")


def content_numbers(s):
    """표현 필터가 숫자·날짜 변경을 삼키지 않도록 모든 숫자를 보존한다."""
    return [value.replace(",", "") for value in CONTENT_NUMBER.findall(s or "")]


def load_item(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    res = data.get("result", data)
    return res[0] if isinstance(res, list) else res


def norm_alias(s):
    hit = False
    for pat, rep in ALIASES:
        s2 = pat.sub(rep, s)
        hit = hit or (s2 != s)
        s = s2
    return s, hit


def lines_of(text):
    out = []
    for raw in (text or "").replace("\r", "").split("\n"):
        line = re.sub(r"\s+", " ", raw).strip()
        if line and not BOILERPLATE.search(line):
            out.append(line)
    return out


def classify_pair(a, b):
    """한 줄이 바뀐 경우 분류"""
    if canon(a) == canon(b):
        return "format", {}
    if content_numbers(a) == content_numbers(b) and expression_canon(a) == expression_canon(b):
        return "expression", {}
    a_n, ha = norm_alias(a)
    b_n, hb = norm_alias(b)
    if canon(a_n) == canon(b_n):
        return "rename", {}
    a_n, b_n = a_n.replace("\u2019", "'"), b_n.replace("\u2019", "'")
    nums_a, nums_b = NUM_UNIT.findall(a_n), NUM_UNIT.findall(b_n)
    if sorted(nums_a) != sorted(nums_b):
        return "number", {"prev_numbers": nums_a, "curr_numbers": nums_b}
    if canon(DATE.sub("<D>", a_n)) == canon(DATE.sub("<D>", b_n)):
        return "date", {}
    return "text", {}


def diff_text(prev, curr):
    a, b = lines_of(prev), lines_of(curr)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    changes = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        olds, news = a[i1:i2], b[j1:j2]
        # 바뀐 줄끼리 가장 비슷한 것 짝짓기
        used = set()
        for o in olds:
            best, score = None, 0.0
            for k, n in enumerate(news):
                if k in used:
                    continue
                r = difflib.SequenceMatcher(a=o, b=n).ratio()
                if r > score:
                    best, score = k, r
            if best is not None and score >= 0.55:
                used.add(best)
                kind, extra = classify_pair(o, news[best])
                changes.append({"type": kind, "prev": o, "curr": news[best], **extra})
            else:
                changes.append({"type": "removed", "prev": o, "curr": None})
        for k, n in enumerate(news):
            if k not in used:
                changes.append({"type": "added", "prev": None, "curr": n})
    return changes


def split_list(s):
    s, _ = norm_alias(s or "")
    return [x.strip() for x in s.split(",") if x.strip()]


def unit_base(name):
    """모집단위 이름 정규화: '배전(일반)' -> '배전', '전기(신입_대졸수준)_일반' -> '전기(신입_대졸수준)'"""
    n = re.sub(r"_(일반|보훈|장애|장애인)$", "", name)
    n = re.sub(r"\((일반|보훈|장애|장애인|가|나)\)$", "", n)
    return n.strip()


def steps_summary(item):
    """모집단위별 단계 행을 묶어 숫자가 있는 것만 정리"""
    units = {}
    for s in item.get("steps") or []:
        u = s.get("recrutPbancTtl")
        units.setdefault(u, []).append({
            "selected": s.get("recrutNope"), "applied": s.get("aplyNope"),
            "date": s.get("rsnOcrnYmd")})
    return units


def compare(prev, curr):
    out = {
        "prev": {"sn": prev.get("recrutPblntSn"), "title": prev.get("recrutPbancTtl"),
                 "period": f"{prev.get('pbancBgngYmd')}~{prev.get('pbancEndYmd')}"},
        "curr": {"sn": curr.get("recrutPblntSn"), "title": curr.get("recrutPbancTtl"),
                 "period": f"{curr.get('pbancBgngYmd')}~{curr.get('pbancEndYmd')}"},
        "changes": [],
    }
    add = out["changes"].append

    # 숫자: 채용인원
    if prev.get("recrutNope") != curr.get("recrutNope"):
        add({"field": "채용인원", "type": "number",
             "prev": prev.get("recrutNope"), "curr": curr.get("recrutNope")})

    # 목록형
    for f, label in LIST_FIELDS.items():
        a, b = split_list(prev.get(f)), split_list(curr.get(f))
        gone, new = [x for x in a if x not in b], [x for x in b if x not in a]
        if gone or new:
            add({"field": label, "type": "list", "removed": gone, "added": new})

    # 모집단위 (steps 이름 기준)
    ua, ub = steps_summary(prev), steps_summary(curr)
    ba = {unit_base(u) for u in ua}
    bb = {unit_base(u) for u in ub}
    if ba != bb:
        add({"field": "모집단위", "type": "list",
             "removed": sorted(ba - bb), "added": sorted(bb - ba)})
    split_new = sorted(u for u in ub if u not in ua and unit_base(u) in ba)
    if split_new:
        add({"field": "모집단위 세분화", "type": "added", "curr": split_new})

    # 문장형
    seen, fmt, expression = set(), 0, 0
    for f, label in TEXT_FIELDS.items():
        for c in diff_text(prev.get(f), curr.get(f)):
            if c["type"] == "format":
                fmt += 1
                continue
            if c["type"] == "expression":
                expression += 1
                continue
            k = (label, c["type"], c.get("prev"), c.get("curr"))
            if k in seen:
                continue
            seen.add(k)
            add({"field": label, **c})
    out["format_only_lines"] = fmt
    out["expression_only_lines"] = expression

    # 경쟁률 데이터 유무 (기관이 API에 공시했는지)
    def has_numbers(units):
        return any(r["applied"] is not None for rows in units.values() for r in rows)
    out["competition_in_api"] = {"prev": has_numbers(ua), "curr": has_numbers(ub)}

    # 2단계(AI)로 넘길 공고문 PDF
    out["notice_pdfs"] = {
        side: [f.get("url") for f in (it.get("files") or []) if f.get("atchFileType") == "A"]
        for side, it in (("prev", prev), ("curr", curr))}
    return out


PRIORITY = {"number": 0, "added": 1, "removed": 1, "list": 1, "text": 2, "rename": 3, "date": 4}
LABEL = {"number": "숫자 변경", "added": "새로 생김", "removed": "사라짐", "list": "목록 변경",
         "text": "문구 변경(AI 분류 대상)", "rename": "명칭만 변경", "date": "날짜만 갱신"}


def to_markdown(name, r):
    lines = [f"## {name}",
             f"- 작년: [{r['prev']['sn']}] {r['prev']['title']} ({r['prev']['period']})",
             f"- 올해: [{r['curr']['sn']}] {r['curr']['title']} ({r['curr']['period']})",
             f"- API 경쟁률 공시: 작년 {'있음' if r['competition_in_api']['prev'] else '없음'}, "
             f"올해 {'있음' if r['competition_in_api']['curr'] else '없음'}",
             f"- 띄어쓰기·문장부호만 다른 줄 {r['format_only_lines']}개는 제외", ""]
    if r.get("expression_only_lines"):
        lines.insert(-1, f"- 쉼표·괄호·'단,'만 달라 의미가 같은 줄 {r['expression_only_lines']}개는 제외")
    for c in sorted(r["changes"], key=lambda c: PRIORITY.get(c["type"], 9)):
        tag = LABEL.get(c["type"], c["type"])
        if c["type"] == "list":
            body = f"추가 {c['added'] or '-'} / 삭제 {c['removed'] or '-'}"
        elif c["type"] == "added":
            body = f"+ {c['curr']}"
        elif c["type"] == "removed":
            body = f"- {c['prev']}"
        else:
            body = f"{c['prev']}  →  {c['curr']}"
        lines.append(f"- **[{tag}] {c['field']}**: {body}")
    return "\n".join(lines) + "\n"


def main():
    pairs = [a.split(":") for a in sys.argv[1:]]  # 이름:작년.json:올해.json
    report, md = {}, ["# 1단계 비교 결과 (코드만, AI 호출 0회)\n"]
    for name, p, c in pairs:
        r = compare(load_item(p), load_item(c))
        report[name] = r
        md.append(to_markdown(name, r))
    Path("stage1_result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("stage1_result.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
