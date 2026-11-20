"""내 조건 맞춤 결과를 PDF로 만들기 (11-20, T047). AI 호출 없음 — 화면에 보이는 판정 결과를 그대로 옮긴다.

글꼴: assets/fonts/NotoSansKR-*.otf (Noto Sans CJK KR에서 한글·기호만 남긴 것, SIL Open Font License)
배포 서버(Streamlit Cloud)에는 한글 글꼴이 없어서 저장소에 같이 넣는다.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from fpdf import FPDF

FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"
STATUS_COLOR = {"eligible": (22, 128, 61), "ambiguous": (180, 110, 0), "ineligible": (190, 30, 45)}
GRAY = (110, 110, 110)
SIDE_LABEL = {"curr": "올해 공고", "prev": "작년 공고"}
NOTICE = ("합격 가능성이나 순위가 아니라, 공고에 적힌 지원 조건과 내 조건을 비교한 결과입니다. "
          "확정할 수 없는 조건이 있으면 '애매'로 표시합니다. 공고 내용은 정부 채용정보와 공고문에서 자동으로 "
          "정리했어요. 지원 전에 공고문 원문을 꼭 확인하세요.")


# 글꼴에 없는 기호 → 비슷한 기호 (11-20 시험에서 나온 것)
REPLACE = str.maketrans({"▸": ">", "▶": ">", "‣": "•", "∙": "·", "⦁": "•", "∼": "~", "\t": " ",
                         "\u00a0": " ", "\u200b": ""})
_GLYPHS: set[int] = set()


def _glyphs() -> set[int]:
    if not _GLYPHS:
        from fontTools.ttLib import TTFont  # fpdf2가 같이 설치함

        _GLYPHS.update(TTFont(str(FONT_DIR / "NotoSansKR-Regular.otf")).getBestCmap())
    return _GLYPHS


def clean(text: Any) -> str:
    """글꼴에 없는 글자는 비슷한 기호로 바꾸고, 그래도 없으면 뺀다 (빈 네모로 찍히지 않게)"""
    glyphs = _glyphs()
    return "".join(char for char in str(text or "").translate(REPLACE) if char == "\n" or ord(char) in glyphs)


def notice_url(report: Mapping[str, Any]) -> str:
    """공고 원문 주소. 옛 주소(opendata.alio.go.kr)는 첫 화면으로 가 버려서 새 다운로드 주소로 바꾼다."""
    url = str((report.get("curr") or {}).get("source_url") or "")
    match = re.search(r"recrutAtchFileNo=(\d+)", url)
    return f"https://www.alio.go.kr/download/download.json?fileNo={match.group(1)}" if match else url


def deadline_text(value: str) -> str:
    if len(value) == 8 and value.isdigit():
        return f"{value[:4]}.{value[4:6]}.{value[6:]}"
    return value or "-"


def bonus_text(result: Any, track: str) -> str:
    by_cert: dict[str, list[str]] = {}
    for row in result.bonus:
        where = "·".join(row["units"]) if row["units"] else f"{track} 직렬"
        by_cert.setdefault(row["certificate"], []).append(f"{where} {row['points']}{row.get('unit') or '점'}")
    return " / ".join(f"{cert}: {', '.join(parts)}" for cert, parts in by_cert.items())


class _Doc(FPDF):
    def __init__(self, made_at: str) -> None:
        super().__init__(format="A4")
        self.made_at = made_at
        self.add_font("kr", "", str(FONT_DIR / "NotoSansKR-Regular.otf"))
        self.add_font("kr", "B", str(FONT_DIR / "NotoSansKR-Bold.otf"))
        self.set_auto_page_break(True, margin=16)
        self.set_margins(16, 16, 16)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("kr", "", 8)
        self.set_text_color(*GRAY)
        self.cell(0, 6, f"공채레이더 · {self.made_at} 기준 · {self.page_no()}쪽", align="C")
        self.set_text_color(0, 0, 0)

    # ---- 작은 도우미
    def text_block(self, text: str, size: float = 10, style: str = "", color=(0, 0, 0), height: float = 5.6) -> None:
        self.set_font("kr", style, size)
        self.set_text_color(*color)
        self.multi_cell(0, height, clean(text), align="L", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)

    def bullets(self, items: Iterable[str], size: float = 9.5) -> None:
        self.set_font("kr", "", size)
        for item in items:
            self.set_x(self.l_margin + 2)
            self.multi_cell(0, 5.2, f"• {clean(item)}", align="L", new_x="LMARGIN", new_y="NEXT")

    def label(self, text: str) -> None:
        self.ln(1.5)
        self.text_block(text, size=10, style="B")


def _summary_table(doc: _Doc, rows: list[tuple[Any, str]], track: str) -> None:
    widths = (40, 72, 24, 42)
    doc.set_font("kr", "B", 9)
    doc.set_fill_color(240, 242, 245)
    for width, head in zip(widths, ("기관", "공고", "판정", "내 가점")):
        doc.cell(width, 7, head, border=1, fill=True)
    doc.ln()
    doc.set_font("kr", "", 8.5)
    for result, _ in rows:
        points = sorted({f"{row['points']}{row.get('unit') or '점'}" for row in result.bonus})
        cells = (result.institution, result.title, result.label or "-", ", ".join(points) or "-")
        line_counts = [len(doc.multi_cell(width, 5, clean(text), align="L", dry_run=True, output="LINES")) for width, text in zip(widths, cells)]
        height = 5 * max(line_counts)
        if doc.get_y() + height > doc.page_break_trigger:
            doc.add_page()
        y = doc.get_y()
        x = doc.l_margin
        for index, (width, text) in enumerate(zip(widths, cells)):
            doc.set_xy(x, y)
            if index == 2:
                doc.set_text_color(*STATUS_COLOR.get(result.status or "", (0, 0, 0)))
                doc.set_font("kr", "B", 8.5)
            doc.multi_cell(width, 5, clean(text), align="L", border=0)
            doc.set_text_color(0, 0, 0)
            doc.set_font("kr", "", 8.5)
            doc.rect(x, y, width, height)
            x += width
        doc.set_xy(doc.l_margin, y + height)


def _section(doc: _Doc, result: Any, report: Mapping[str, Any], track: str, change: str | None) -> None:
    if doc.get_y() > doc.page_break_trigger - 40:
        doc.add_page()
    doc.ln(4)
    doc.set_draw_color(200, 200, 200)
    doc.line(doc.l_margin, doc.get_y(), doc.w - doc.r_margin, doc.get_y())
    doc.ln(2)
    doc.text_block(result.institution, size=13, style="B", height=7)
    doc.text_block(result.title, size=10)
    category = f"{report['category']} 공기업 · " if report.get("category") else ""
    doc.text_block(f"{category}접수 마감 {deadline_text(result.deadline)}", size=8.5, color=GRAY)
    doc.text_block(f"판정: {result.label or '-'}", size=11, style="B",
                   color=STATUS_COLOR.get(result.status or "", (0, 0, 0)), height=7)

    doc.label("판단 이유")
    doc.bullets(result.reasons)
    if result.review_items:
        doc.label("직접 확인할 것")
        doc.bullets(result.review_items)
    bonus = bonus_text(result, track)
    if bonus:
        doc.label("내 자격증 가점")
        doc.bullets([bonus] + ([result.bonus_rule] if result.bonus_rule else []))
    if result.common_checks:
        doc.label("모든 지원자 공통 확인")
        doc.bullets(result.common_checks)
    if change:
        doc.label("작년 대비 대표 변경")
        doc.bullets([change])
    if result.units:
        doc.label(f"모집단위별 판정 {len(result.units)}개")
        doc.bullets(f"{unit['name']}: {unit['label']} — {unit['reason']}" for unit in result.units)
    evidence = []
    seen = set()
    for item in result.evidence:
        key = (item.get("side"), item.get("page"), item.get("quote"))
        if key not in seen:
            seen.add(key)
            evidence.append(item)
    if evidence:
        doc.label(f"판정에 쓴 공고 근거 {len(evidence)}개")
        doc.bullets([f"{SIDE_LABEL.get(item.get('side'), '공고')} {item.get('page')}쪽: “{item.get('quote')}”"
                     for item in evidence], size=8.5)
    url = notice_url(report)
    if url:
        doc.text_block(f"공고 원문: {url}", size=8, color=GRAY)


def build_result_pdf(
    condition: Any,
    entries: list[tuple[Any, Mapping[str, Any], str | None]],
    other_region: list[tuple[Any, Mapping[str, Any], str | None]] = (),
    no_track: list[str] = (),
    made_at: str | None = None,
) -> bytes:
    """entries / other_region: (판정 결과, 리포트, 대표 변경 한 줄) 목록 → PDF 바이트"""
    made_at = made_at or date.today().strftime("%Y.%m.%d")
    doc = _Doc(made_at)
    doc.add_page()
    doc.text_block("공채레이더 · 내 조건 맞춤 결과", size=17, style="B", height=9)
    certificates = ", ".join(condition.certificates) or "없음"
    doc.text_block(f"내 조건: {condition.track} 직렬 · {', '.join(condition.regions)} · 자격증 {certificates}", size=10.5)
    doc.text_block(f"만든 날짜: {made_at}", size=9, color=GRAY)
    doc.ln(2)
    doc.text_block(NOTICE, size=8.5, color=GRAY, height=4.8)
    doc.ln(3)

    doc.text_block(f"조건에 맞는 공고 {len(entries)}건", size=12, style="B", height=7)
    if entries:
        _summary_table(doc, [(result, report) for result, report, _ in entries], condition.track)
    else:
        doc.text_block("희망 직렬과 지역이 모두 맞는 공고가 없습니다.", size=9.5)
    if other_region:
        doc.ln(3)
        doc.text_block(f"희망 지역에 근무지가 없는 공고 {len(other_region)}건", size=12, style="B", height=7)
        _summary_table(doc, [(result, report) for result, report, _ in other_region], condition.track)
    if no_track:
        doc.ln(2)
        doc.text_block(f"{condition.track} 직렬을 뽑지 않는 공고: " + ", ".join(no_track), size=8.5, color=GRAY)

    for result, report, change in list(entries) + list(other_region):
        _section(doc, result, report, condition.track, change)
    return bytes(doc.output())
