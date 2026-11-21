"""화면 1. 공고 목록: 조건 입력 + 결과를 한 화면에 (11-21 구조 개편 명세 2번).

예전 '내 조건 입력'과 '맞춤 공고'를 합쳤다. 공고 줄을 누르면 화면 2(공고 상세)로 간다.
판정은 src/eligibility.py 그대로, '바뀐 점'은 src/change_summary.py 5줄 요약에서 '바뀜'·'새로'만.
"""

from __future__ import annotations

from html import escape
import re
from typing import Any, Mapping

import streamlit as st

from app.flow import best_results, current_condition, detail_href, query, top_bar
from app.pages.conditions import ANY_REGION, EXAMPLE, EXAMPLE_NO_CERT, TRACK_ORDER, available_tracks
from app.pages.matches import (PAST_LABELS, VERDICT_TEXT, _best_bonus, _d_day, _date_short, _pdf_button,
                               _reason_line, _short_title, collection_skipped, is_open)
from app.report_data import DATA_NOTICE, load_reports
from app.ui_components import apply_styles, md_text
from src.certificates import COMMON_CERTIFICATES
from src.change_summary import changed_points, prev_start_text
from src.eligibility import REGIONS, EligibilityResult, UserCondition


def _use_example(example: dict) -> None:
    st.session_state["condition_tracks"] = [example["track"]]
    st.session_state["condition_regions"] = list(example["regions"])
    st.session_state["condition_certificates"] = list(example["certificates"])
    st.session_state["run_search"] = True


def row_html(result: EligibilityResult, report: Mapping[str, Any], track: str, condition: Mapping[str, Any],
             first: bool = False) -> str:
    """공고 한 줄 = 링크 하나 (누르면 상세). 3줄: 기관명 / 공고명 · 마감 · 가점 / 모집단위 · 이유 · 바뀐 점.
    지난 공고만 4줄째: '다음 공고 참고: 작년엔 9월 9일 접수 시작' (예측하지 않고 작년 날짜만)"""
    status = result.status if result.status in {"eligible", "ambiguous", "ineligible"} else "ambiguous"
    open_now = is_open(result.deadline)
    label = VERDICT_TEXT[status] if open_now else PAST_LABELS.get(status, result.label or "")
    sub = [escape(_short_title(result)), f"{_date_short(result.deadline)} 마감"]
    best = _best_bonus(result)
    if best:
        sub.append(escape(best))
    points = changed_points(report, track)
    reason = _reason_line(result, status)
    if points and len(re.sub(r"<[^>]+>", "", reason)) > 34:  # 바뀐 점이 보이게 이유를 줄임 (전체는 상세 화면)
        plain = re.sub(r"<[^>]+>", "", reason)
        reason = escape(plain[:33].rstrip() + "…")
    if points:
        joined = ", ".join(points)
        joined = joined if len(joined) <= 40 else joined[:39].rstrip(" ,·") + "…"
        reason += ' <span class="m-bar">·</span> 바뀐 점: ' + escape(joined)
    hint = ""
    if not open_now and prev_start_text(report):
        hint = f'<div class="m-hint">다음 공고 참고: <b>작년엔 {escape(prev_start_text(report))} 접수 시작</b></div>'
    side = f'<span class="m-dday">{escape(_d_day(result.deadline))}</span>' if open_now else ""
    tone = status if open_now or status != "eligible" else "past"
    return (f'<a class="m-link" href="{escape(detail_href(condition, result.pair_id))}" target="_self">'
            f'<div class="m-row{" m-first" if first else ""}"><div class="m-main">'
            f'<div class="m-inst">{escape(result.institution)}</div>'
            f'<div class="m-sub">{"<span class=\'m-bar\'>·</span>".join(sub)}</div>'
            f'<div class="m-reason">{reason}</div>{hint}</div>'
            f'<div class="m-side">{side}<span class="m-verdict v-{tone}">{escape(label)}</span></div></div></a>')


def _head(title: str, count: int, hint: str) -> None:
    st.markdown(f'<div class="m-head"><div><span class="m-head-title">{escape(title)}</span> '
                f'<span class="m-head-count">{count}</span></div><span class="m-head-hint">{escape(hint)}</span></div>',
                unsafe_allow_html=True)


def _rows(items: list[tuple[EligibilityResult, str]], reports: Mapping[str, Any], condition: Mapping[str, Any],
          key: str, first: int | None = None, more_label: str = "") -> None:
    shown = items if first is None or st.session_state.get(f"more-{key}") else items[:first]
    if shown:
        st.markdown("".join(row_html(result, reports[result.pair_id], track, condition, index == 0)
                            for index, (result, track) in enumerate(shown)), unsafe_allow_html=True)
    rest = len(items) - len(shown)
    if rest > 0 and st.button(f"{more_label} {rest}건 더 보기 ▾", key=f"more-btn-{key}", type="tertiary"):
        st.session_state[f"more-{key}"] = True
        st.rerun()


def _inputs(tracks: list[str]) -> bool:
    saved = current_condition() or {}
    st.session_state.setdefault("condition_tracks", [track for track in saved.get("tracks", []) if track in tracks]
                                or ([tracks[0]] if tracks else []))
    st.session_state.setdefault("condition_regions", str(saved.get("region", "")).split("·") if saved.get("region") else [])
    st.session_state.setdefault("condition_certificates", list(saved.get("certificates") or []))
    columns = st.columns([1, 1.25, 1.25, 0.5], vertical_alignment="bottom")
    with columns[0]:
        st.multiselect("직렬 (여러 개 가능)", options=tracks, key="condition_tracks", placeholder="직렬 고르기")
    with columns[1]:
        st.multiselect("근무 지역", options=[ANY_REGION, *REGIONS], key="condition_regions", placeholder="지역 고르기")
    with columns[2]:
        st.multiselect("보유 자격증 (없으면 비워 두기)",
                       options=sorted(set(COMMON_CERTIFICATES) | set(st.session_state["condition_certificates"])),
                       key="condition_certificates", accept_new_options=True, placeholder="검색하거나 직접 입력")
    with columns[3]:
        clicked = st.button("찾기", type="primary", use_container_width=True)
    label, first, second, _ = st.columns([0.7, 1.35, 1.5, 2.2], vertical_alignment="center")
    label.markdown('<div class="ex-label">예시로 해 보기</div>', unsafe_allow_html=True)
    first.button("전기·부산·울산·전기기사", type="tertiary", on_click=_use_example, args=(EXAMPLE,))
    second.button("전기·부산·울산·자격증 없음", type="tertiary", on_click=_use_example, args=(EXAMPLE_NO_CERT,))
    return clicked or bool(st.session_state.pop("run_search", False))


def render_search_page() -> None:
    apply_styles()
    reports, _ = load_reports()
    tracks, _ = available_tracks(reports)
    condition = current_condition()
    top_bar(condition)
    names = sorted(str(report["institution"]) for report in reports)
    intro, more = st.columns([5, 1], vertical_alignment="center")
    intro.markdown(f'<div class="hero-kicker">공기업 신입 공채 <b>{len(reports)}곳</b> · 작년 공고와 비교 · '
                   "공고문 쪽수로 근거 확인</div>", unsafe_allow_html=True)
    with more.popover(f"{len(reports)}곳 보기 ›", use_container_width=True):
        st.markdown(" · ".join(names))
    st.markdown('<div class="radar-title s-title">내 조건으로 공고 찾기</div>', unsafe_allow_html=True)

    if _inputs(tracks):
        chosen = list(st.session_state.get("condition_tracks") or [])
        regions = list(st.session_state.get("condition_regions") or [])
        if not chosen or not regions:
            st.warning("직렬과 근무 지역을 하나 이상 골라 주세요.")
        else:
            if ANY_REGION in regions:
                regions = list(REGIONS)
            condition = {"tracks": chosen, "track": chosen[0], "region": "·".join(regions),
                         "certificates": list(st.session_state.get("condition_certificates") or [])}
            st.session_state["user_condition"] = condition
            st.query_params.from_dict(query(condition))
            for key in [key for key in st.session_state if str(key).startswith("more-")]:
                del st.session_state[key]
    if not condition:
        st.markdown(f'<div class="privacy-note">이름·연락처는 받지 않아요. 고른 조건은 이 창에서만 써요.</div>',
                    unsafe_allow_html=True)
        st.caption(DATA_NOTICE)
        return
    _render_results(condition, reports)


def _render_results(condition: Mapping[str, Any], reports: list[dict]) -> None:
    by_id = {report["pair_id"]: report for report in reports}
    results = best_results(condition, reports)
    matched = [pair for pair in results if pair[0].relevance == "match"]
    other_region = [pair for pair in results if pair[0].relevance == "region_mismatch"]
    no_track = [pair for pair in results if pair[0].relevance == "track_missing"]
    open_now = sorted((pair for pair in matched if is_open(pair[0].deadline)), key=lambda pair: pair[0].deadline)
    past = sorted((pair for pair in matched if not is_open(pair[0].deadline)), key=lambda pair: pair[0].deadline, reverse=True)
    counts = {key: sum(1 for result, _ in matched if result.status == key) for key in ("eligible", "ambiguous", "ineligible")}
    tracks = "·".join(condition.get("tracks") or [condition["track"]])
    st.markdown(
        f'<div class="m-summary">{escape(tracks)} 직렬 공고 <b>{len(matched)}</b>건 · 지금 접수 중 <b>{len(open_now)}</b>건 '
        f'<span>(조건 맞음 {counts["eligible"]} · 애매 {counts["ambiguous"]} · 안 맞음 {counts["ineligible"]})</span></div>',
        unsafe_allow_html=True,
    )
    _head("지금 접수 중", len(open_now), "마감 빠른 순")
    if not open_now:
        st.markdown('<div class="m-empty">지금 접수 중인 공고는 없어요. 아래 지난 공고로 다음 채용을 준비해 보세요.</div>',
                    unsafe_allow_html=True)
    _rows(open_now, by_id, condition, "open")
    if past:
        _head("지난 공고", len(past), "다음 채용 대비")
        _rows(past, by_id, condition, "past", first=3, more_label="지난 공고")
    if other_region:
        _head("희망 지역에 근무지가 없는 공고", len(other_region), "직렬은 맞지만 근무지역이 달라요")
        _rows(other_region, by_id, condition, "region", first=3, more_label="다른 지역 공고")
    if no_track:
        st.markdown(f'<div class="m-empty m-notrack">{escape(tracks)} 직렬을 뽑지 않는 공고: '
                    + escape(", ".join(result.institution for result, _ in no_track)) + "</div>", unsafe_allow_html=True)

    st.markdown('<div class="m-foot"></div>', unsafe_allow_html=True)
    note, pdf = st.columns([3, 1.2], vertical_alignment="center")
    note.caption("합격 가능성이 아니라 공고에 적힌 지원 조건과 내 조건을 비교한 결과예요. 확정할 수 없으면 '애매'로 표시해요. "
                 + DATA_NOTICE)
    with pdf:
        first = UserCondition(condition["track"], str(condition["region"]), tuple(condition.get("certificates") or ()))
        _pdf_button(first, by_id, [result for result, _ in matched], [result for result, _ in other_region],
                    [result for result, _ in no_track])
    skipped = collection_skipped()
    if skipped:
        with st.expander(f"공고를 모으지 못한 기관 {len(skipped)}곳"):
            for row in skipped:
                st.markdown(f"- {row['institution']}: {md_text(row.get('reason') or '사유 없음')}")


if __name__ == "__main__":
    render_search_page()
