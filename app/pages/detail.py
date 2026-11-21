"""화면 2. 공고 상세: 판정 → 작년과 달라진 점(질문 5개) → 올해 일정 → 공고문에 물어보기 → 원문 대조
(11-21 구조 개편 명세 3번). 예전 '공고 비교'와 '공고문에 물어보기'를 합쳤다.
"""

from __future__ import annotations

from datetime import date
from html import escape
import re
from typing import Any, Mapping

import streamlit as st

from app.flow import condition_line, current_condition, search_href, top_bar, user_conditions
from app.pages.matches import (LANGUAGE, PAST_LABELS, VERDICT_TEXT, _bonus_lines, _d_day, _short_title,
                               _unique_evidence, is_open)
from app.pages.qa import render_qa_box
from app.pages.report import _is_minor, _mentions_track, _render_sources, _units
from app.report_data import DATA_NOTICE, load_reports
from app.ui_components import DIFF_LEGEND, apply_styles, change_row
from src.change_summary import date_only_change, normalize, schedule, summarize
from src.eligibility import evaluate, expand_regions, readable_unit_name
from src.result_pdf import notice_url

STATUS_CLASS = {"같음": "same", "바뀜": "changed", "새로": "new", "비교 어려움": "hard", "정보 없음": "none"}
RAW_GROUPS = (  # 원문 대조 묶음
    ("인원", {"인원"}),
    ("전형", {"전형"}),
    ("자격", {"자격", "결격사유", "학력조건", "모집단위", "직무분야(NCS)"}),
    ("가점", {"가점"}),
    ("기타", None),
)


def _ymd(value: str) -> str:
    return f"{value[:4]}.{value[4:6]}.{value[6:]}" if len(value) == 8 and value.isdigit() else value


def _prev_label(report: Mapping[str, Any]) -> str:
    """'작년 공고: 2026년 상반기 신입사원 (2025.10 공고)' — 연도만 쓰지 않는다 (공고명 연도와 엇갈림)"""
    prev = report["prev"]
    title = re.sub(r"^[\[(]?" + re.escape(str(report["institution"])) + r"(\(주\))?[\])]?\s*", "", str(prev["title"]))
    title = re.sub(r"\s*\([^()]*(\([^()]*\))?[^()]*\)", "", title).replace("채용공고", "").replace("채용 공고", "").strip()
    start = str((prev.get("period") or {}).get("start") or "")
    when = f" ({start[:4]}.{start[4:6]} 공고)" if len(start) == 8 else ""
    return f"작년 공고: {title}{when}"


def _header(report: Mapping[str, Any]) -> None:
    curr = report["curr"]
    period = curr.get("period") or {}
    end = str(period.get("end") or "")
    category = f" · {report['category']} 공기업" if report.get("category") else ""
    regions = expand_regions((report.get("requirements") or {}).get("regions") or [])
    where = f" · 근무지 {'·'.join(regions[:3])}{' 등' if len(regions) > 3 else ''}" if regions else ""
    status = (f'<span class="m-dday">{escape(_d_day(end))}</span>' if is_open(end)
              else '<span class="d-closed">접수 마감</span>')
    title = re.sub(r"^[\[(]?" + re.escape(str(report["institution"])) + r"(\(주\))?[\])]?\s*", "", str(curr["title"]))
    st.markdown(
        f'<div class="d-org">{escape(str(report["institution"]))}{escape(category)}</div>'
        f'<div class="d-title">{escape(title)}</div>'
        f'<div class="d-meta">접수 {_ymd(str(period.get("start") or ""))} ~ {_ymd(end)[5:]} {status}{escape(where)}</div>',
        unsafe_allow_html=True,
    )
    left, right, _ = st.columns([1.1, 1.2, 3])
    url = notice_url(report)
    if url:
        left.link_button("공고문 PDF 열기", url, use_container_width=True)
    right.markdown('<a class="d-outline" href="#ask" target="_self">공고문에 물어보기</a>', unsafe_allow_html=True)


def _section(title: str, side: str = "", anchor: str = "") -> None:
    anchor_html = f'<a id="{anchor}"></a>' if anchor else ""
    side_html = f'<span class="d-side">{escape(side)}</span>' if side else ""
    st.markdown(f'{anchor_html}<div class="d-sec">{escape(title)}{side_html}</div>', unsafe_allow_html=True)


def _verdict(report: Mapping[str, Any], condition: Mapping[str, Any] | None) -> str:
    """구역 1. 나는 지원할 수 있나 → 이 공고를 판정한 직렬 (5줄 요약의 '직렬 인원' 안내에 씀)"""
    _section("나는 지원할 수 있나")
    if not condition:
        st.markdown(f'<div class="m-empty">조건을 넣으면 지원할 수 있는지 알려 드려요. '
                    f'<a href="{escape(search_href(None))}" target="_self">조건 넣으러 가기 ›</a></div>',
                    unsafe_allow_html=True)
        return ""
    results = [(evaluate(item, report), item.track) for item in user_conditions(condition)]
    results.sort(key=lambda pair: ({"match": 0, "region_mismatch": 1, "track_missing": 2}[pair[0].relevance],
                                   {"eligible": 0, "ambiguous": 1, "ineligible": 2}.get(pair[0].status or "", 3)))
    result, track = results[0]
    if result.relevance == "track_missing":
        st.markdown(f'<div class="m-empty">이 공고에는 {escape(track)} 직렬 모집단위가 없어요.</div>', unsafe_allow_html=True)
        return track
    status = result.status or "ambiguous"
    open_now = is_open(result.deadline)
    label = VERDICT_TEXT[status] if open_now else PAST_LABELS.get(status, result.label or "")
    unit = next((item for item in result.units if item.get("status") == status), None)
    unit_text = f' · <span class="d-unit-name">{escape(readable_unit_name(str(unit["name"])))}</span>' if unit else ""
    if status == "ambiguous" and result.review_items:
        reason = result.review_items[0]
    elif unit:
        reason = unit.get("reason") or ""
    else:
        reason = result.reasons[-1] if result.reasons else ""
    page = next((item for item in result.evidence if item.get("side") == "curr" and item.get("page")), None)
    page_text = f' <span class="d-page-ref">(올해 {page["page"]}쪽)</span>' if page else ""
    region = "" if result.relevance == "match" else ' <span class="d-page-ref">· 희망 지역에 근무지가 없어요</span>'
    st.markdown(f'<div class="d-verdict v-{status}">{escape(label)}{unit_text}</div>'
                f'<div class="d-reason">{escape(str(reason))}{page_text}{region}</div>', unsafe_allow_html=True)
    checks: list[str] = []
    language = next((item for item in list(result.review_items) + list(result.common_checks) if LANGUAGE.search(item)), None)
    if language:
        head, _, tail = language.partition("(")
        checks.append(f"<b>{escape(head.strip())}</b>" + (f" ({escape(tail)}" if tail else ""))
    bonus = _bonus_lines(result, track)
    if bonus:
        checks.append("내 자격증 가점: " + escape(" / ".join(bonus)))
    special = next((item for item in result.review_items if "대상자" in item or "특별전형" in item or "판정에서 뺐어요" in item), None)
    if special and special != reason:
        checks.append(escape(special))
    if checks:
        st.markdown('<ul class="d-list">' + "".join(f"<li>{item}</li>" for item in checks[:3]) + "</ul>",
                    unsafe_allow_html=True)
    rest = [item for item in result.common_checks if item != language]
    if rest:
        with st.expander(f"모든 지원자 공통 조건 {len(rest)}개"):
            st.markdown('<ul class="d-list">' + "".join(f"<li>{escape(item)}</li>" for item in rest) + "</ul>",
                        unsafe_allow_html=True)
    if len(result.units) >= 2:
        lines = "".join(
            f'<li><b>{escape(readable_unit_name(str(item["name"])))}</b> · '
            f'<span class="v-{item.get("status", "ambiguous")}">'
            f'{escape(item["label"] if open_now else PAST_LABELS.get(item.get("status"), item["label"]))}</span>'
            f' · {escape(str(item["reason"]))}</li>' for item in result.units)
        st.markdown(f'<div class="d-units-head">모집단위별 판정 {len(result.units)}개</div><ul class="d-list d-units">{lines}</ul>',
                    unsafe_allow_html=True)
    evidence = _unique_evidence(result.evidence)
    if evidence:
        with st.expander(f"판정에 쓴 공고 근거 {len(evidence)}개"):
            rows = "".join(
                f'<tr><td class="d-page">{"올해" if item.get("side") == "curr" else "작년"} {escape(str(item.get("page")))}쪽</td>'
                f'<td>“{escape(str(item.get("quote")))}”</td></tr>' for item in evidence)
            st.markdown(f'<table class="d-table d-evidence"><thead><tr><th>쪽</th><th>공고문 원문</th></tr></thead>'
                        f"<tbody>{rows}</tbody></table>", unsafe_allow_html=True)
    return track


def _changes(report: Mapping[str, Any], track: str) -> None:
    """구역 2. 작년과 달라진 점: 고정 5줄 (질문 | 상태 | 답 | 원문 대조 ›)"""
    _section("작년과 달라진 점", _prev_label(report))
    rows = []
    for row in summarize(report, track):
        link = ('<a href="#schedule" target="_self">전체 일정 ›</a>' if row.key == "schedule"
                else '<a href="#raw" target="_self">원문 대조 ›</a>')
        note = f'<span class="s-note">{escape(row.note)}</span> ' if row.note else ""
        rows.append(
            f'<tr><th>{escape(row.question)}</th>'
            f'<td class="s-state"><span class="s-chip s-{STATUS_CLASS[row.status]}">{escape(row.status)}</span></td>'
            f'<td><div class="s-answer">{escape(row.answer)}</div><div class="s-sub">{note}{link}</div></td></tr>')
    st.markdown(f'<table class="s-table">{"".join(rows)}</table>', unsafe_allow_html=True)
    st.caption("변경 기록으로 규칙에 따라 만든 요약이에요. 정확한 문구는 아래 원문 대조에서 확인하세요.")


def _schedule(report: Mapping[str, Any]) -> None:
    """구역 3. 올해 일정: 한 줄 표 (지금 단계는 연한 파랑)"""
    _section("올해 일정", anchor="schedule")
    cells = schedule(report, date.today())
    if not cells:
        st.markdown('<div class="m-empty">공고에서 일정 줄을 찾지 못했어요. 공고문 원문을 확인하세요.</div>', unsafe_allow_html=True)
        return
    html = "".join(f'<td class="{"now" if cell["current"] else ""}"><div class="t-name">{escape(cell["name"])}</div>'
                   f'<div class="t-date">{escape(cell["text"])}</div></td>' for cell in cells)
    st.markdown(f'<table class="t-table"><tr>{html}</tr></table>', unsafe_allow_html=True)


def _group(unit: Mapping[str, Any]) -> str:
    categories = {str(change.get("category")) for change in unit["changes"]}
    for name, members in RAW_GROUPS:
        if members is None or categories & members:
            return name
    return "기타"


def _raw(report: Mapping[str, Any], track: str) -> None:
    """구역 5. 원문 대조 (접힘): 분류별 카드. 정리하면 같은 문장·날짜만 바뀐 것은 뺌 (일정은 구역 3)"""
    st.markdown('<a id="raw"></a>', unsafe_allow_html=True)
    units = []
    for unit in _units(report):
        members = [change for change in unit["changes"] if not date_only_change(change)
                   and not (change.get("change_type") == "text"
                            and normalize(change.get("prev_value")) == normalize(change.get("curr_value")))]
        if members:
            units.append({**unit, "changes": members})
    if not st.toggle(f"원문 대조: 작년·올해 문구 차이 {len(units)}건 보기", key=f"raw-{report['pair_id']}"):
        st.caption("인원·전형·자격·가점으로 묶어서 보여 줘요. 줄 단위 비교는 여기에만 있어요.")
        return
    titles = {"prev": report["prev"]["title"], "curr": report["curr"]["title"]}
    pair_id, info = str(report["pair_id"]), report.get("notice_info")
    for name, _ in RAW_GROUPS:
        members = [unit for unit in units if _group(unit) == name]
        if not members:
            continue
        members.sort(key=lambda unit: (not _mentions_track(unit, track), _is_minor(unit), unit["importance"]))
        st.markdown(f'<div class="d-units-head">{escape(name)} {len(members)}건</div>', unsafe_allow_html=True)
        for index, unit in enumerate(members):
            change_row(unit, titles, pair_id, info, track if _mentions_track(unit, track) else None, first=index == 0)
    st.markdown(DIFF_LEGEND, unsafe_allow_html=True)
    _render_sources(report)


def render_detail_page() -> None:
    apply_styles()
    reports, _ = load_reports()
    by_id = {report["pair_id"]: report for report in reports}
    condition = current_condition()
    top_bar(condition)
    pair_id = str(st.query_params.get("p") or st.session_state.get("selected_pair_id") or "")
    if pair_id not in by_id:
        pair_id = next(iter(by_id), "")
    back, pick = st.columns([3, 2], vertical_alignment="center")
    back.markdown(f'<div class="d-back"><a href="{escape(search_href(condition))}" target="_self">‹ 공고 목록</a>'
                  f'<span>{escape(condition_line(condition))}</span></div>', unsafe_allow_html=True)
    ids = list(by_id)
    chosen = pick.selectbox("다른 기관 보기", ids, index=ids.index(pair_id) if pair_id in ids else 0,
                            format_func=lambda value: by_id[value]["institution"], label_visibility="collapsed")
    if chosen != pair_id:
        st.query_params["p"] = chosen
        pair_id = chosen
    st.session_state["selected_pair_id"] = pair_id
    report = by_id[pair_id]

    _header(report)
    track = _verdict(report, condition) or (condition or {}).get("track", "")
    _changes(report, track)
    _schedule(report)
    _section("공고문에 물어보기", anchor="ask")
    st.caption("이 공고의 공고문 원문 안에서만 답해요. 이름·연락처 같은 개인정보는 입력하지 마세요.")
    examples = ["토익 몇 점 필요해?", "자기소개서는 언제 내?", "나이 제한 있어?"]
    if condition and condition.get("certificates"):
        examples.insert(1, f"{condition['certificates'][0]} 가점 몇 점이야?")
    render_qa_box(report, examples)
    _raw(report, track)
    st.caption(DATA_NOTICE)


if __name__ == "__main__":
    render_detail_page()
