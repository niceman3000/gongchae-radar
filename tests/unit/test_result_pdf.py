"""결과 PDF (T047) — 한글이 찍히고, 판정·가점·근거가 들어가는지."""

from __future__ import annotations

import json
from pathlib import Path

import pypdfium2 as pdfium

from src.eligibility import UserCondition, evaluate_all
from src.result_pdf import build_result_pdf, clean, notice_url

ROOT = Path(__file__).resolve().parents[2]


def _pdf_text(data: bytes) -> str:
    document = pdfium.PdfDocument(data)
    return "\n".join(document[index].get_textpage().get_text_range() for index in range(len(document)))


def test_kepco_result_pdf_has_judgement_bonus_and_evidence() -> None:
    report = json.loads((ROOT / "data" / "reports" / "report_kepco.json").read_text(encoding="utf-8"))
    condition = UserCondition.from_mapping({"track": "전기", "region": "서울", "certificates": ["전기기사"]})
    result = evaluate_all(condition, [report])[0]
    data = build_result_pdf(condition, [(result, report, "채용인원: 421 → 490")], made_at="2026.11.20")

    assert data[:5] == b"%PDF-"
    text = _pdf_text(data)
    assert "공채레이더" in text and "내 조건: 전기 직렬" in text
    assert "한국전력공사" in text and "지원 가능" in text
    assert "전기기사: 배전(일반) 10점" in text
    assert "올해 공고" in text and "쪽" in text  # 근거 인용
    assert "채용인원: 421 → 490" in text
    assert "합격 가능성이나 순위가 아니라" in text


def test_empty_result_still_makes_pdf() -> None:
    condition = UserCondition.from_mapping({"track": "사무", "region": "서울", "certificates": []})
    text = _pdf_text(build_result_pdf(condition, [], made_at="2026.11.20"))
    assert "조건에 맞는 공고 0건" in text


def test_clean_drops_missing_glyphs_and_old_url_is_rewritten() -> None:
    assert clean("▸ 가점\t10점") == "> 가점 10점"
    assert clean("A\U0001F600B") == "AB"
    report = {"curr": {"source_url": "https://opendata.alio.go.kr/recruit/downloadAtchFile?recrutAtchFileNo=3030414"}}
    assert notice_url(report) == "https://www.alio.go.kr/download/download.json?fileNo=3030414"
