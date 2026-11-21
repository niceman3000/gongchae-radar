"""③ 공고 비교: 기관 선택 → 공고 띠 → 판정 3줄 → 작년과 달라진 점(질문 5개) → 올해 일정 → 원문 대조(접힘).

11-21 구조 개편(명세 3번)에서 만든 상세 화면을, 저녁 절충안(4번)대로 '공고 비교' 메뉴로 씀:
기관 선택 상자 복원, 판정은 3줄, 질문은 버튼으로 ④ 메뉴 이동(이 공고가 선택된 채로).
"""

from __future__ import annotations

from datetime import date
from html import escape
import re
from typing import Any, Mapping

import streamlit as st

from app.flow import current_condition, query, user_conditions
from app.pages.matches import (relevant_bonus, LANGUAGE, PAST_LABELS, VERDICT_TEXT, _bonus_lines, _d_day, _short_title,
                               _unique_evidence, is_open)
from app.pages.report import _is_minor, _mentions_track, _render_sources, _units
from app.report_data import DATA_NOTICE, load_reports
from app.ui_components import DIFF_LEGEND, apply_styles, change_row
from src.change_summary import application_period, date_only_change, is_schedule_line, normalize, schedule, summarize
from src.eligibility import evaluate, expand_regions, readable_unit_name
from src.result_pdf import notice_url
from src.clock import today_kst

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


def _go_qa(pair_id: str) -> None:
    st.session_state["selected_pair_id"] = pair_id
    st.session_state["go_qa"] = True


def work_places(report: Mapping[str, Any], mine: list[str]) -> str:
    """근무지: 내 희망 지역을 먼저, 그다음 나머지 (새벽 점검 3번: 가나다순 앞 3개라 부산 준비생에게 고리가 안 보임)"""
    regions = expand_regions((report.get("requirements") or {}).get("regions") or [])
    if not regions:
        return ""
    if len(regions) >= 17:
        return " · 근무지 전국"
    ordered = [region for region in regions if region in mine] + [region for region in regions if region not in mine]
    shown = ordered[:5]
    return f" · 근무지 {'·'.join(shown)}{f' 외 {len(ordered) - 5}곳' if len(ordered) > 5 else ''}"


def _header(report: Mapping[str, Any], mine: list[str] | None = None) -> None:
    """공고 띠 (남색): 기관·유형 / 공고명 / 접수·D-day·근무지 / PDF 열기 · 이 공고에 물어보기 ›"""
    mine = mine or []
    curr = report["curr"]
    period = curr.get("period") or {}
    end = str(period.get("end") or "")
    category = f" · {report['category']} 공기업" if report.get("category") else ""
    where = work_places(report, mine)
    first, last, hour = application_period(report)  # 공고 게시일이 아니라 실제 지원서 접수 기간 (새벽 점검 2번)
    status = (f'<span class="m-dday">{escape(_d_day(end))}</span>' if is_open(end)
              else '<span class="d-closed">접수 마감</span>')
    title = re.sub(r"^[\[(]?" + re.escape(str(report["institution"])) + r"(\(주\))?[\])]?\s*", "", str(curr["title"]))
    with st.container(key="hero-band"):
        st.markdown(
            f'<div class="d-org">{escape(str(report["institution"]))}{escape(category)}</div>'
            f'<div class="d-title">{escape(title)}</div>'
            f'<div class="d-meta">접수 {f"{first:%Y.%m.%d} ~ {last:%m.%d}" if first else _ymd(end)}'
            f'{" " + hour if hour else ""} {status}{escape(where)}</div>',
            unsafe_allow_html=True,
        )
        left, right, _ = st.columns([1.1, 1.35, 3])
        url = notice_url(report)
        if url:
            left.link_button("공고문 PDF 열기", url, use_container_width=True)
        right.button("이 공고에 물어보기 ›", key="ask-this", on_click=_go_qa, args=(str(report["pair_id"]),),
                     use_container_width=True)


def _section(title: str, side: str = "", anchor: str = "") -> None:
    anchor_html = f'<a id="{anchor}"></a>' if anchor else ""
    side_html = f'<span class="d-side">{escape(side)}</span>' if side else ""
    st.markdown(f'{anchor_html}<div class="d-sec">{escape(title)}{side_html}</div>', unsafe_allow_html=True)


def bonus_text(result: Any) -> str:
    """'자격증 반영 전기기사 10점 · 전기공사기사 10점 (17쪽) · 기술 최대 20점' — 질문 화면과 같은 숫자에 근거 쪽을 붙임
    (11-21 팀원 질문 테스트 5번). 동서발전처럼 가점이 아니라 서류 점수인 곳이 있어 '가점' 대신 '자격증 반영'"""
    rows = relevant_bonus(result)
    if not rows:
        return ""
    held = " · ".join(dict.fromkeys(f"{row['certificate']} {row['points']:g}{row.get('unit') or '점'}" for row in rows))
    pages = sorted({item["page"] for row in rows for item in row.get("evidence") or []
                    if item.get("side") == "curr" and item.get("page")})
    text = f"자격증 반영 {held}" + (f" ({', '.join(f'{page}쪽' for page in pages[:2])})" if pages else "")
    rule = str(result.bonus_rule or "")
    limit = re.search(r"기술[^.]*?최대\s*(\d+)\s*점\)?", rule) or re.search(r"기술\s*(\d+)\s*점\s*한도", rule)
    return text + (f" · 기술 최대 {limit.group(1)}점" if limit else "")


def _verdict(report: Mapping[str, Any], condition: Mapping[str, Any] | None) -> str:
    """구역 1. 나는 지원할 수 있나 — 3줄 (절충안 4번): 판정+모집단위 / 이유(쪽)·토익 기준·내 가점 / 자세히 ▾"""
    _section("나는 지원할 수 있나")
    if not condition:
        st.markdown('<div class="m-empty">‘내 조건 입력’에서 조건을 넣으면 이 공고에 지원할 수 있는지 알려 드려요.</div>',
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
    tone = status if open_now or status != "eligible" else "past"
    unit = next((item for item in result.units if item.get("status") == status), None)
    unit_text = f' · <span class="d-unit-name">{escape(readable_unit_name(str(unit["name"])))}</span>' if unit else ""
    if status == "ambiguous" and result.review_items:
        reason = result.review_items[0]
    elif unit:
        reason = unit.get("reason") or ""
    else:
        reason = result.reasons[-1] if result.reasons else ""
    page = next((item for item in result.evidence if item.get("side") == "curr" and item.get("page")), None)
    parts = [escape(str(reason)) + (f' <span class="d-page-ref">(올해 {page["page"]}쪽)</span>' if page else "")]
    language = next((item for item in list(result.review_items) + list(result.common_checks) if LANGUAGE.search(item)), None)
    if language:
        match = re.search(r"(TOEIC|토익)\s*\d{3}\s*점\s*이상", language)
        parts.append(escape(match.group(0).replace("TOEIC", "토익") if match else language.partition("(")[0].strip()[:30]))
    bonus = bonus_text(result)
    if bonus and status != "ineligible":
        parts.append(escape(bonus))
    if result.relevance != "match":
        parts.append("희망 지역에 근무지가 없어요")
    mark = {"eligible": "✓", "ambiguous": "?", "ineligible": "✕"}.get(status, "?") if tone != "past" else "✓"
    evidence = _unique_evidence(result.evidence)
    with st.container(key=f"verdict-{tone}"):
        st.markdown(f'<div class="v-box"><div class="v-mark v-mark-{tone}">{mark}</div><div>'
                    f'<div class="d-verdict v-{tone}">{escape(label.replace("✓ ", ""))}{unit_text}</div>'
                    f'<div class="d-reason">{" · ".join(parts)}</div></div></div>', unsafe_allow_html=True)
        with st.expander(f"자세히: 공통 조건 · 모집단위별 판정 · 근거 {len(evidence)}개"):
            special = [item for item in result.review_items if item != reason]
            if special:
                st.markdown('<div class="d-units-head">직접 확인할 것</div><ul class="d-list">'
                            + "".join(f"<li>{escape(item)}</li>" for item in special) + "</ul>", unsafe_allow_html=True)
            if result.common_checks:
                st.markdown('<div class="d-units-head">모든 지원자 공통 조건</div><ul class="d-list">'
                            + "".join(f"<li>{escape(item)}</li>" for item in result.common_checks) + "</ul>",
                            unsafe_allow_html=True)
            if result.units:
                lines = "".join(
                    f'<li><b>{escape(readable_unit_name(str(item["name"])))}</b> · '
                    f'<span class="v-{item.get("status", "ambiguous")}">'
                    f'{escape(item["label"] if open_now else PAST_LABELS.get(item.get("status"), item["label"]))}</span>'
                    f' · {escape(str(item["reason"]))}</li>' for item in result.units)
                st.markdown(f'<div class="d-units-head">모집단위별 판정 {len(result.units)}개</div>'
                            f'<ul class="d-list d-units">{lines}</ul>', unsafe_allow_html=True)
            if evidence:
                rows = "".join(
                    f'<tr><td class="d-page">{"올해" if item.get("side") == "curr" else "작년"} {escape(str(item.get("page")))}쪽</td>'
                    f'<td>“{escape(str(item.get("quote")))}”</td></tr>' for item in evidence)
                st.markdown(f'<div class="d-units-head">판정에 쓴 공고 근거 {len(evidence)}개</div>'
                            f'<table class="d-table d-evidence"><thead><tr><th>쪽</th><th>공고문 원문</th></tr></thead>'
                            f"<tbody>{rows}</tbody></table>", unsafe_allow_html=True)
    return track


def _changes(report: Mapping[str, Any], track: str) -> None:
    """구역 2. 작년과 달라진 점: 고정 5줄 (질문 | 상태 | 답 | 원문 대조 ›)"""
    _section("작년과 달라진 점", _prev_label(report))
    rows = []
    for row in summarize(report, track):
        link = ('<a href="#schedule" target="_self">전체 일정 ›</a>' if row.key == "schedule"
                else '<a href="#raw" target="_self">원문 대조 ›</a>')
        note = f'<span class="s-note">{escape(row.note)}</span>' if row.note else ""
        rows.append(  # '원문 대조 ›'는 줄마다 맨 오른쪽 칸에 고정 (화면 정리 메모 3번)
            f'<tr><th>{escape(row.question)}</th>'
            f'<td class="s-state"><span class="s-chip s-{STATUS_CLASS[row.status]}">{escape(row.status)}</span></td>'
            f'<td><div class="s-answer">{escape(row.answer)}</div>'
            + (f'<div class="s-sub">{note}</div>' if note else "") + f'</td><td class="s-link">{link}</td></tr>')
    st.markdown(f'<table class="s-table">{"".join(rows)}</table>', unsafe_allow_html=True)
    st.caption("변경 기록으로 규칙에 따라 만든 요약이에요. 정확한 문구는 아래 원문 대조에서 확인하세요.")


def _schedule(report: Mapping[str, Any]) -> None:
    """구역 3. 올해 일정: 타임라인, 지금 단계만 파랑 + '지금' (절충안 5번)"""
    _section("올해 일정", anchor="schedule")
    cells = schedule(report, today_kst())
    if not cells:
        st.markdown('<div class="m-empty">공고에서 일정 줄을 찾지 못했어요. 공고문 원문을 확인하세요.</div>', unsafe_allow_html=True)
        return
    html = "".join(
        f'<div class="tl-step{" tl-now" if cell["current"] else ""}">'
        f'<div class="tl-flag">{"지금" if cell["current"] else "&nbsp;"}</div><div class="tl-dot"></div>'
        f'<div class="t-name">{escape(cell["name"])}</div><div class="t-date">{escape(cell["text"])}</div></div>'
        for cell in cells)
    st.markdown(f'<div class="timeline">{html}</div>', unsafe_allow_html=True)


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
        # 날짜가 든 일정 줄끼리의 짝은 뺌: 채용정보 API 번호로 짝지어져 '2차 면접'↔'신체검사'처럼 어긋나고,
        # API 오타('입사일 2026.03.15', 공고문은 2027.3.15)도 그대로라 일정은 '올해 일정'(공고문 기준)에서만 (새벽 점검 16·17번)
        members = [change for change in unit["changes"] if not date_only_change(change)
                   and not (is_schedule_line(change.get("prev_value")) and is_schedule_line(change.get("curr_value")))
                   and not (change.get("change_type") == "text"
                            and normalize(change.get("prev_value")) == normalize(change.get("curr_value")))]
        if members:
            units.append({**unit, "changes": members})
    if not st.toggle(f"원문 대조: 작년·올해 문구 차이 {len(units)}건 보기", key=f"raw-{report['pair_id']}"):
        st.caption("인원·전형·자격·가점으로 묶어서 보여 줘요. 줄 단위 비교는 여기에만 있어요.")
        return
    titles = {"prev": report["prev"]["title"], "curr": report["curr"]["title"]}
    pair_id, info = str(report["pair_id"]), report.get("notice_info")
    count = summarize(report, track)[0]  # 위 5줄과 같은 판단 (새벽 점검 18번: 5줄 '비교 어려움', 아래 '늘었어요')
    count_note = count.answer if count.status == "비교 어려움" else None
    for name, _ in RAW_GROUPS:
        members = [unit for unit in units if _group(unit) == name]
        if not members:
            continue
        members.sort(key=lambda unit: (not _mentions_track(unit, track), _is_minor(unit), unit["importance"]))
        st.markdown(f'<div class="d-units-head">{escape(name)} {len(members)}건</div>', unsafe_allow_html=True)
        for index, unit in enumerate(members):
            meaning = count_note if name == "인원" else None
            change_row(unit, titles, pair_id, info, track if _mentions_track(unit, track) else None, first=index == 0,
                       meaning=meaning)
    st.markdown(DIFF_LEGEND, unsafe_allow_html=True)
    _render_sources(report)


def _option(report: Mapping[str, Any]) -> str:
    title = re.sub(r"^[\[(]?" + re.escape(str(report["institution"])) + r"(\(주\))?[\])]?\s*", "", str(report["curr"]["title"]))
    return f'{report["institution"]} · {title}'


def render_detail_page() -> None:
    apply_styles()
    if st.session_state.pop("go_qa", False):
        st.switch_page("app/pages/qa.py")
    reports, _ = load_reports()
    by_id = {report["pair_id"]: report for report in reports}
    condition = current_condition()
    pair_id = str(st.session_state.get("selected_pair_id") or st.query_params.get("p") or "")
    ids = sorted(by_id, key=lambda value: by_id[value]["institution"])
    if pair_id not in by_id:
        pair_id = "kepco-2025-2026-h2" if "kepco-2025-2026-h2" in by_id else ids[0]
    chosen = st.selectbox("비교할 공고 · 아무 기관이나 고를 수 있어요", ids, index=ids.index(pair_id),
                          format_func=lambda value: _option(by_id[value]), key=None)
    st.session_state["selected_pair_id"] = chosen  # ④ 질문 화면이 같은 공고를 연다
    st.query_params.from_dict(query(condition, chosen))  # 주소를 복사해 새 창에서 열어도 같은 공고 (새벽 점검 15번)
    report = by_id[chosen]

    _header(report, str((condition or {}).get("region") or "").split("·"))
    track = _verdict(report, condition) or (condition or {}).get("track", "")
    _changes(report, track)
    _schedule(report)
    _raw(report, track)
    st.caption(DATA_NOTICE)


if __name__ == "__main__":
    render_detail_page()
