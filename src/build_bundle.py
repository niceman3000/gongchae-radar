# -*- coding: utf-8 -*-
"""PDF -> 쪽별 텍스트(+표) 묶음. AI에는 관련 쪽만 보낸다 (토큰 절약)."""
import json, re, sys
import pdfplumber

KEYS = ["채용인원", "모집", "배수", "배점", "가점", "필수", "자격", "면접", "필기", "서류",
        "지역", "예고", "일정", "합격", "커트라인", "전형"]

def table_text(tables):
    out = []
    for t in tables:
        for row in t:
            cells = [re.sub(r"\s+", " ", c or "").strip() for c in row]
            if any(cells):
                out.append("| " + " | ".join(cells) + " |")
        out.append("")
    return "\n".join(out)

def build(pdf_path, max_pages=10):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, p in enumerate(pdf.pages, 1):
            text = p.extract_text() or ""
            tables = p.extract_tables() or []
            score = sum(text.count(k) for k in KEYS) + 3 * len(tables)
            pages.append({"page": i, "score": score, "text": text,
                          "tables": table_text(tables)})
    # 본문(표지 다음 ~ '붙임 목차' 전) + 핵심 붙임(지원가능학과, 자격증 가점표)
    toc = next((p["page"] for p in pages if re.search(r"붙임\s*목차", p["text"])), None)
    if toc:
        body = [p for p in pages if 1 < p["page"] < toc]
        appx = [p for p in pages if p["page"] > toc and
                re.search(r"붙임\s*\d+\s*(지원\s*가능\s*학과|자격증\s*보유\s*가점표)", p["text"])]
        chosen = body + appx
    else:  # 목차가 없는 공고는 관련도 점수 상위 쪽
        chosen = sorted(sorted(pages, key=lambda x: -x["score"])[:max_pages], key=lambda x: x["page"])
    return {"pdf": pdf_path, "total_pages": len(pages),
            "sent_pages": [c["page"] for c in chosen],
            "pages": [{"page": c["page"], "text": c["text"], "tables": c["tables"]} for c in chosen],
            "all_text": {str(p["page"]): p["text"] + "\n" + p["tables"] for p in pages}}

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    b = build(src)
    json.dump(b, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
    sent = sum(len(p["text"]) + len(p["tables"]) for p in b["pages"])
    full = sum(len(v) for v in b["all_text"].values())
    print(f"{src}: {b['total_pages']}쪽 중 {len(b['sent_pages'])}쪽 선택 {b['sent_pages']} / 글자 {sent:,} of {full:,}")
