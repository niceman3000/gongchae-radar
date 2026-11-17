"""전년도 대비 변경점 상세 화면."""

from __future__ import annotations

from html import escape
from typing import Mapping

import streamlit as st

from app.ui_components import apply_styles, change_card
from src.report_repository import ReportContractError, ReportRepository


def _render_header(report: Mapping[str, Any]) -> None:
    st.markdown('<div class="radar-eyebrow">PUBLIC RECRUITMENT CHANGE RADAR</div>', unsafe_allow_html=True)
    st.markdown('<div class="radar-title">공채레이더</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="radar-subtitle">{escape(str(report["institution"]))} 공고를 전년도와 직접 대조한 결과입니다.</div>',
        unsafe_allow_html=True,
    )

    confirmed = sum(item["status"] == "confirmed" for item in report["changes"])
    review = sum(item["status"] == "review_required" for item in report["changes"])
    first, second, third = st.columns(3)
    first.metric("확인된 변경사항", f"{confirmed}건")
    second.metric("추가 확인 필요", f"{review}건")
    third.metric("데이터 확인일", report["checked_at"])


def _render_sources(report: Mapping[str, Any]) -> None:
    with st.expander("비교한 공식 공고"):
        for label, key in (("전년도", "prev"), ("당해 연도", "curr")):
            notice = report[key]
            st.markdown(f"**{label} · {notice['title']}**")
            st.caption(
                f"공고번호 {notice['sn']} · 접수 {notice['period']['start']} ~ {notice['period']['end']}"
            )
            if notice.get("source_url"):
                st.link_button(f"{label} 원문 PDF 열기", notice["source_url"])


def render_report(report: Mapping[str, Any]) -> None:
    apply_styles()
    _render_header(report)
    st.info("확정 결과에는 PDF 쪽수와 원문 인용이 반드시 붙습니다. 확인되지 않은 후보는 따로 표시합니다.")
    _render_sources(report)

    st.subheader("무엇이 바뀌었나")
    show_review = st.toggle("확인 필요한 후보도 함께 보기", value=False)
    visible = [
        item
        for item in report["changes"]
        if item["status"] == "confirmed" or show_review
    ]
    st.caption(f"현재 {len(visible)}건 표시 · 중요도 높은 순")

    titles = {"prev": report["prev"]["title"], "curr": report["curr"]["title"]}
    for change in visible:
        change_card(change, titles)

    if not visible:
        st.warning("표시할 확정 변경점이 없습니다.")


def render_report_page(pair_id: str = "kepco-2025-2026-h2") -> None:
    repository = ReportRepository()
    try:
        report = repository.load(pair_id)
    except (KeyError, ReportContractError) as exc:
        apply_styles()
        st.error(f"리포트를 열 수 없습니다: {exc}")
        return
    render_report(report)
