"""전년도 대비 변경점 상세 화면."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Mapping

import streamlit as st

from app.ui_components import apply_styles, change_card
from src.report_repository import ReportContractError, ReportRepository


ROOT = Path(__file__).resolve().parents[2]


def _render_header(report: Mapping[str, Any]) -> None:
    institution = escape(str(report["institution"]))
    st.markdown('<div class="radar-eyebrow">공채레이더 · 전년도 공고 비교</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="radar-title">{institution} 채용공고 비교</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="radar-subtitle">현재 지원할 공고와 전년도 공고에서 달라진 내용을 확인합니다.</div>',
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown(f"### 지원 대상 기업: {report['institution']}")
        current, previous = st.columns(2)
        with current:
            st.markdown("**현재 지원 공고 (2026)**")
            st.write(report["curr"]["title"])
            st.caption(
                f"공고번호 {report['curr']['sn']} · 접수 {report['curr']['period']['start']} ~ {report['curr']['period']['end']}"
            )
        with previous:
            st.markdown("**비교 기준 공고 (2025)**")
            st.write(report["prev"]["title"])
            st.caption(
                f"공고번호 {report['prev']['sn']} · 접수 {report['prev']['period']['start']} ~ {report['prev']['period']['end']}"
            )

    confirmed = sum(item["status"] == "confirmed" for item in report["changes"])
    review = sum(item["status"] == "review_required" for item in report["changes"])
    first, second, third = st.columns(3)
    first.metric("확인된 변경사항", f"{confirmed}건")
    second.metric("추가 확인 필요", f"{review}건")
    third.metric("데이터 확인일", report["checked_at"])


def _render_sources(report: Mapping[str, Any]) -> None:
    st.subheader("공식 공고 원문")
    st.caption("잡알리오 외부 링크 대신 수집 당시 저장한 공식 PDF를 직접 확인합니다.")

    columns = st.columns(2)
    for column, (label, key) in zip(columns, (("현재 공고 (2026)", "curr"), ("비교 공고 (2025)", "prev"))):
        notice = report[key]
        pdf_path = ROOT / str(notice["pdf_path"])
        with column:
            st.markdown(f"**{label}**")
            if pdf_path.exists():
                st.download_button(
                    "원문 PDF 내려받기",
                    data=pdf_path.read_bytes(),
                    file_name=f"{notice['sn']}.pdf",
                    mime="application/pdf",
                    key=f"download-{notice['sn']}",
                    use_container_width=True,
                )
            else:
                st.warning("저장된 원문 PDF를 찾을 수 없습니다.")

    selection = st.selectbox(
        "화면에서 바로 볼 공고",
        options=["선택 안 함", "현재 공고 (2026)", "비교 공고 (2025)"],
        index=0,
    )
    selected_key = {
        "현재 공고 (2026)": "curr",
        "비교 공고 (2025)": "prev",
    }.get(selection)
    if selected_key:
        notice = report[selected_key]
        pdf_path = ROOT / str(notice["pdf_path"])
        if pdf_path.exists():
            st.pdf(
                pdf_path,
                height=720,
                key=f"viewer-{notice['sn']}",
                alt=f"{notice['title']} 공식 공고문",
            )
        else:
            st.warning("저장된 원문 PDF를 찾을 수 없습니다.")


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
