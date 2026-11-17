"""공채레이더 Streamlit 화면의 공통 표시 요소."""

from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping

import streamlit as st


STATUS_LABELS = {
    "confirmed": "원문 확인",
    "review_required": "확인 필요",
    "not_published": "기관 미공시",
}


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #f5f7fb; }
        [data-testid="stHeader"] { background: rgba(245, 247, 251, 0.88); }
        .radar-eyebrow {
            color: #3157d5; font-size: .78rem; font-weight: 800;
            letter-spacing: .08em; margin-bottom: .35rem;
        }
        .radar-title { color: #172033; font-size: 2rem; font-weight: 850; line-height: 1.2; }
        .radar-subtitle { color: #5f6b7d; margin: .45rem 0 1.35rem 0; }
        .status-badge {
            display: inline-block; border-radius: 999px; padding: .2rem .58rem;
            font-size: .76rem; font-weight: 750; margin-bottom: .35rem;
        }
        .status-confirmed { color: #176b45; background: #ddf5e9; }
        .status-review_required { color: #875800; background: #fff0c7; }
        .status-not_published { color: #5f6b7d; background: #e8ebf1; }
        .change-title { color: #172033; font-weight: 780; font-size: 1.02rem; }
        .value-label { color: #727e90; font-size: .76rem; font-weight: 700; }
        .value-box {
            background: #f8f9fc; border: 1px solid #e3e7ef; border-radius: .7rem;
            min-height: 4.2rem; padding: .65rem .75rem; margin-top: .25rem;
            color: #273247; overflow-wrap: anywhere;
        }
        .evidence-quote {
            border-left: 3px solid #6b86e8; padding: .3rem .7rem; color: #39465c;
            background: #f7f9ff; border-radius: 0 .45rem .45rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def status_badge(status: str) -> None:
    label = STATUS_LABELS.get(status, status)
    safe_status = status if status in STATUS_LABELS else "not_published"
    st.markdown(
        f'<span class="status-badge status-{safe_status}">{escape(label)}</span>',
        unsafe_allow_html=True,
    )


def display_value(value: Any) -> str:
    if value is None:
        return "명시 없음"
    if value == []:
        return "없음"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if isinstance(value, (dict, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _value_box(label: str, value: Any) -> None:
    st.markdown(f'<div class="value-label">{label}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="value-box">{escape(display_value(value))}</div>',
        unsafe_allow_html=True,
    )


def evidence_card(item: Mapping[str, Any], titles: Mapping[str, str]) -> None:
    side = str(item["side"])
    year_label = "전년도" if side == "prev" else "당해 연도"
    st.caption(f"{year_label} · {titles[side]} · PDF {item['page']}쪽")
    st.markdown(
        f'<div class="evidence-quote">{escape(str(item["quote"]))}</div>',
        unsafe_allow_html=True,
    )


def change_card(change: Mapping[str, Any], titles: Mapping[str, str]) -> None:
    with st.container(border=True):
        left, right = st.columns([4, 1])
        with left:
            st.markdown(
                f'<div class="change-title">{escape(str(change["title"]))}</div>',
                unsafe_allow_html=True,
            )
            st.caption(f'{change["category"]} · 중요도 {change["importance"]}')
        with right:
            status_badge(str(change["status"]))

        before, after = st.columns(2)
        with before:
            _value_box("2025", change.get("prev_value"))
        with after:
            _value_box("2026", change.get("curr_value"))

        evidence = list(change.get("evidence") or [])
        if evidence:
            with st.expander(f"공식 공고 근거 {len(evidence)}개"):
                for index, item in enumerate(evidence):
                    evidence_card(item, titles)
                    if index < len(evidence) - 1:
                        st.divider()
        else:
            st.caption("원문 근거를 대조 중인 후보입니다.")
