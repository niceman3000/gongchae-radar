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
from src.clock import today_kst

FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"
STATUS_COLOR = {"eligible": (22, 128, 61), "ambiguous": (180, 110, 0), "ineligible": (190, 30, 45)}
GRAY = (110, 110, 110)
SIDE_LABEL = {"curr": "올해 공고", "prev": "작년 공고"}
NOTICE = ("합격 가능성이나 순위가 아니라, 공고에 적힌 지원 조건과 내 조건을 비교한 결과예요. "
          "확정할 수 없는 조건이 있으면 '애매'로 표시해요. 공고 내용은 정부 채용정보와 공고문에서 자동으로 "
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


BLUE = (36, 83, 230)
INK = (22, 32, 46)
LINE = (221, 226, 234)
PAST_LABEL = {"eligible": "조건 맞음", "ambiguous": "애매", "ineligible": "조건 안 맞음"}
LANGUAGE = re.compile(r"토익|TOEIC|어학|외국어")


def _short(text: Any, limit: int) -> str:
    text = " ".join(clean(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _days_left(value: str, today: date) -> int | None:
    if len(value) == 8 and value.isdigit():
        return (date(int(value[:4]), int(value[4:6]), int(value[6:])) - today).days
    return None


def _best_bonus(result: Any) -> str:
    points = []
    for row in result.bonus:
        try:
            points.append((row.get("unit") or "점", float(row["points"])))
        except (TypeError, ValueError):
            continue
    if not points:
        return "-"
    unit, value = max(points, key=lambda item: (item[0] == "점", item[1]))
    return f"최대 {value:g}{unit}"


def _reason(result: Any) -> str:
    """판정을 가른 이유 한 줄 (화면 목록과 같은 규칙)"""
    status = result.status or "ambiguous"
    unit = next((item for item in result.units if item.get("status") == status), None)
    if status == "ambiguous" and result.review_items:
        reason = result.review_items[0]
    elif unit:
        reason = unit.get("reason") or ""
    else:
        reason = result.reasons[-1] if result.reasons else ""
    from src.eligibility import readable_unit_name

    return (f"{readable_unit_name(unit['name'])} · " if unit and status != "ambiguous" else "") + str(reason)


def _heading(doc: _Doc, title: str, count: int | None = None, hint: str = "") -> None:
    if doc.get_y() > doc.page_break_trigger - 30:
        doc.add_page()
    doc.ln(5)
    doc.set_draw_color(*INK)
    doc.set_line_width(0.6)
    doc.line(doc.l_margin, doc.get_y(), doc.w - doc.r_margin, doc.get_y())
    doc.set_line_width(0.2)
    doc.ln(2.5)
    doc.set_font("kr", "B", 13)
    doc.set_text_color(*INK)
    width = doc.get_string_width(clean(title)) + 2
    doc.cell(width, 7, clean(title))
    if count is not None:
        doc.set_text_color(*BLUE)
        doc.cell(12, 7, str(count))
    if hint:
        doc.set_font("kr", "", 8.5)
        doc.set_text_color(*GRAY)
        doc.cell(0, 7, clean(hint), align="R")
    doc.ln(9)
    doc.set_text_color(0, 0, 0)


def _tiles(doc: _Doc, items: list[tuple[str, str, tuple[int, int, int]]]) -> None:
    gap = 3
    width = (doc.w - doc.l_margin - doc.r_margin - gap * (len(items) - 1)) / len(items)
    y = doc.get_y()
    for index, (label, value, color) in enumerate(items):
        x = doc.l_margin + index * (width + gap)
        doc.set_fill_color(243, 245, 248)
        doc.rect(x, y, width, 19, style="F")
        doc.set_xy(x + 4, y + 2.5)
        doc.set_font("kr", "", 8.5)
        doc.set_text_color(*GRAY)
        doc.cell(width - 8, 5, clean(label))
        doc.set_xy(x + 4, y + 8)
        doc.set_font("kr", "B", 16)
        doc.set_text_color(*color)
        doc.cell(width - 8, 8, clean(value))
    doc.set_text_color(0, 0, 0)
    doc.set_xy(doc.l_margin, y + 23)


def _open_card(doc: _Doc, result: Any, report: Mapping[str, Any], track: str, today: date) -> None:
    """접수 중 공고 한 건: 기관·판정 / 공고·마감·가점 / 이유 / 확인할 것 2개 / 근거 1개 / 원문"""
    if doc.get_y() > doc.page_break_trigger - 45:
        doc.add_page()
    status = result.status or "ambiguous"
    full = doc.w - doc.l_margin - doc.r_margin
    doc.set_draw_color(*LINE)
    doc.line(doc.l_margin, doc.get_y(), doc.w - doc.r_margin, doc.get_y())
    doc.ln(3)
    y = doc.get_y()
    doc.set_font("kr", "B", 13)
    doc.set_text_color(*INK)
    doc.cell(full - 45, 7, clean(result.institution))
    days = _days_left(result.deadline, today)
    doc.set_font("kr", "B", 11)
    doc.set_text_color(*STATUS_COLOR.get(status, INK))
    doc.cell(45, 7, clean(f"{'D-' + str(days) + '  ' if days is not None else ''}{result.label or '-'}"), align="R")
    doc.set_xy(doc.l_margin, y + 7.5)
    bonus = bonus_text(result, track)
    doc.text_block(f"{_short(result.title, 48)}  |  {deadline_text(result.deadline)} 마감"
                   + (f"  |  내 가점 {_best_bonus(result)}" if result.bonus else ""), size=9, color=GRAY, height=5)
    doc.ln(1)
    doc.text_block(_short(_reason(result), 110), size=10.5, style="B", color=INK, height=6)
    checks = [str(item) for item in list(result.review_items) + list(result.common_checks)]
    checks = sorted(checks, key=lambda item: not LANGUAGE.search(item))[:3]
    if bonus:
        checks.insert(0, f"내 자격증 가점: {bonus}")
    if checks:
        doc.ln(0.5)
        doc.bullets([_short(item, 105) for item in checks], size=9)
    evidence = next(iter(result.evidence), None)
    if evidence:
        doc.text_block(f"근거  {SIDE_LABEL.get(evidence.get('side'), '공고')} {evidence.get('page')}쪽 · "
                       f"“{_short(evidence.get('quote'), 80)}”", size=8.5, color=GRAY, height=4.8)
    url = notice_url(report)
    if url:
        doc.set_font("kr", "", 8.5)
        doc.set_text_color(*BLUE)
        doc.cell(0, 5, "공고 원문 열기", link=url, new_x="LMARGIN", new_y="NEXT")
        doc.set_text_color(0, 0, 0)
    doc.ln(2)


def _fit(doc: _Doc, text: str, width: float) -> str:
    """칸 너비에 맞게 자르기 (지금 글꼴 기준)"""
    text = clean(text)
    if doc.get_string_width(text) <= width - 1.5:
        return text
    while text and doc.get_string_width(text + "…") > width - 1.5:
        text = text[:-1]
    return text + "…"


def _table(doc: _Doc, rows: list[tuple[Any, Mapping[str, Any]]], past: bool) -> None:
    """지난 공고 등: 한 공고 = 한 줄 (기관 · 판정 · 마감 · 내 가점 · 이유)"""
    widths = (40, 21, 18, 19, 80)
    heads = ("기관", "판정", "마감", "내 가점", "이유")
    doc.set_font("kr", "B", 8.5)
    doc.set_text_color(*GRAY)
    for width, head in zip(widths, heads):
        doc.cell(width, 6.5, head)
    doc.ln()
    doc.set_draw_color(*INK)
    doc.line(doc.l_margin, doc.get_y(), doc.w - doc.r_margin, doc.get_y())
    doc.set_draw_color(*LINE)
    for result, report in rows:
        status = result.status or "ambiguous"
        cells = (result.institution,
                 PAST_LABEL.get(status, "-") if past else (result.label or "-"),
                 deadline_text(result.deadline)[2:], _best_bonus(result), _reason(result))
        # 이유는 자르지 않고 줄을 바꿈 (11-21 사용자: PDF에서 이유가 잘림), 최대 3줄
        doc.set_font("kr", "", 8.8)
        reason_lines = doc.multi_cell(widths[4], 4.6, clean(cells[4]), dry_run=True, output="LINES")[:3]
        if len(doc.multi_cell(widths[4], 4.6, clean(cells[4]), dry_run=True, output="LINES")) > 3:
            reason_lines[-1] = _fit(doc, reason_lines[-1] + "…", widths[4])
        height = max(7.5, 4.6 * len(reason_lines) + 2.9)
        if doc.get_y() + height > doc.page_break_trigger:
            doc.add_page()
        y = doc.get_y()
        x = doc.l_margin
        for index, (width, text) in enumerate(zip(widths, cells)):
            doc.set_xy(x, y)
            doc.set_font("kr", "B" if index in (0, 1) else "", 8.8)
            doc.set_text_color(*(STATUS_COLOR.get(status, INK) if index == 1 else INK if index == 0 else (60, 70, 86)))
            if index == 4:
                doc.set_xy(x, y + 1.45)
                doc.multi_cell(width, 4.6, "\n".join(reason_lines), align="L")
            else:
                text = _fit(doc, text, width)
                doc.cell(width, 7.5, text, link=notice_url(report) if index == 0 and notice_url(report) else "")
            x += width
        doc.set_xy(doc.l_margin, y + height)
        doc.line(doc.l_margin, doc.get_y(), doc.w - doc.r_margin, doc.get_y())
    doc.set_text_color(0, 0, 0)


def build_result_pdf(
    condition: Any,
    entries: list[tuple[Any, Mapping[str, Any], str | None]],
    other_region: list[tuple[Any, Mapping[str, Any], str | None]] = (),
    no_track: list[str] = (),
    made_at: str | None = None,
) -> bytes:
    """entries / other_region: (판정 결과, 리포트, 대표 변경 한 줄) 목록 → PDF 바이트.
    11-21: 공고마다 전체 내용을 늘어놓아 18쪽 → 화면과 같은 구조로 2~3쪽 (접수 중만 카드, 나머지는 한 줄 표)"""
    today = today_kst()
    made_at = made_at or today.strftime("%Y.%m.%d")
    doc = _Doc(made_at)
    doc.add_page()
    doc.text_block("공채레이더 · 내 맞춤 공고", size=18, style="B", color=INK, height=10)
    certificates = ", ".join(condition.certificates) or "자격증 없음"
    regions = "지역 상관없음" if len(condition.regions) >= 17 else ", ".join(condition.regions)
    doc.text_block(f"{condition.track} · {regions} · {certificates}   ({made_at} 기준)", size=10, color=GRAY)
    doc.ln(4)

    def is_open(result: Any) -> bool:  # 화면과 같은 기준: 공고문 접수 기간·마감 시각 (11-22 오류 수정 작업서 01)
        if getattr(result, "app_state", ""):
            return result.app_state == "open"
        days = _days_left(result.deadline, today)
        return days is not None and days >= 0

    open_now = sorted((item for item in entries if is_open(item[0])), key=lambda item: item[0].deadline)
    past = sorted((item for item in entries if not is_open(item[0]) and getattr(item[0], "app_state", "") != "upcoming"),
                  key=lambda item: item[0].deadline, reverse=True)
    upcoming = [item for item in entries if getattr(item[0], "app_state", "") == "upcoming"]
    counts = {key: sum(1 for result, _, _ in entries if result.status == key) for key in STATUS_COLOR}
    _tiles(doc, [(f"{condition.track} 직렬 공고", f"{len(entries)}건", INK), ("지금 접수 중", f"{len(open_now)}건", BLUE),
                 ("조건 맞음", str(counts["eligible"]), STATUS_COLOR["eligible"]),
                 ("애매", str(counts["ambiguous"]), STATUS_COLOR["ambiguous"]),
                 ("안 맞음", str(counts["ineligible"]), STATUS_COLOR["ineligible"])])
    doc.text_block(NOTICE, size=8, color=GRAY, height=4.4)

    _heading(doc, "지금 접수 중", len(open_now), "마감 빠른 순")
    if open_now:
        for result, report, _ in open_now:
            _open_card(doc, result, report, condition.track, today)
    else:
        doc.text_block("지금 접수 중인 공고는 없어요. 아래 지난 공고로 다음 채용을 준비해 보세요.", size=9.5, color=GRAY)

    if upcoming:
        _heading(doc, "접수 예정", len(upcoming), "접수 시작 전")
        _table(doc, [(result, report) for result, report, _ in upcoming], past=True)
    if past:
        _heading(doc, "지난 공고", len(past), "다음 채용 대비 · 기관 이름을 누르면 공고 원문")
        _table(doc, [(result, report) for result, report, _ in past], past=True)
    if not entries:
        doc.text_block("희망 직렬과 지역이 모두 맞는 공고가 없어요.", size=9.5)

    if other_region:
        _heading(doc, "희망 지역에 근무지가 없는 공고", len(other_region), "직렬은 맞지만 근무지역이 달라요")
        _table(doc, [(result, report) for result, report, _ in other_region], past=True)
    if no_track:
        doc.ln(4)
        doc.text_block(f"{condition.track} 직렬을 뽑지 않는 공고: " + ", ".join(no_track), size=8.5, color=GRAY)
    return bytes(doc.output())
