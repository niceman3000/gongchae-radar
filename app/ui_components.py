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

CHANGE_COPY = {
    ("kepco-2025-2026-h2", "stage1-001"): ("전체 채용인원 증가: 421명 → 490명", "전체 선발 규모가 69명 늘었습니다."),
    ("kepco-2025-2026-h2", "stage1-002"): ("광주·전남 지역 표기 변경 여부 확인 중", "API 표기는 달라졌지만 실제 지원 지역이 바뀐 것으로 아직 확정하지 않았습니다."),
    ("kepco-2025-2026-h2", "stage1-003"): ("API 직무 목록에서 ‘기계’ 항목이 빠짐", "NCS는 직무 분류표입니다. PDF 확인 전이라 기계직 채용이 없어졌다고 단정할 수 없습니다."),
    ("kepco-2025-2026-h2", "stage1-004"): ("발전(전기)·건축 모집이 없어짐", "2026년 공고에서는 두 모집 직렬에 지원할 수 없습니다."),
    ("kepco-2025-2026-h2", "stage1-005"): ("보훈 전형 10명 신설", "사무 4명, 배전 3명, 송변전 3명을 별도 선발합니다."),
    ("kepco-2025-2026-h2", "stage1-006"): ("전기직 서류 선발 범위 축소: 15배수 → 10배수", "배전·송변전 지원자는 필기시험에 진출하는 서류 합격 인원이 상대적으로 줄었습니다."),
    ("kepco-2025-2026-h2", "stage1-007"): ("보훈 전형도 서류전형 전원 합격", "2026년에는 장애인 전형뿐 아니라 보훈 전형도 지원자격을 충족하면 서류전형을 통과합니다."),
    ("kepco-2025-2026-h2", "stage1-008"): ("일반직 면접 배점 변경: 직무 60·경험 40 → 50·50", "직무면접 비중은 줄고 경험면접 비중은 늘었습니다."),
    ("kepco-2025-2026-h2", "stage1-009"): ("인정되는 어학성적 응시일 기준 변경", "지원할 때 본인의 시험 응시일이 새 인정기간 안에 들어가는지 확인해야 합니다."),
    ("kepco-2025-2026-h2", "stage1-010"): ("어학성적 등록 시스템 변경", "장기 인정 어학성적은 국가공무원 채용시스템 등록 여부를 확인해야 합니다."),
    ("kepco-2025-2026-h2", "stage1-011"): ("이전지역인재 지역 문구 변경 여부 확인 중", "원문은 계속 광주·전남을 뜻하므로 실제 지원자격 변경인지 추가 확인이 필요합니다."),
    ("kepco-2025-2026-h2", "stage1-012"): ("보훈 전형 지원대상 명시", "국가유공자법상 취업지원대상자만 보훈 전형에 지원할 수 있습니다."),
    ("kepco-2025-2026-h2", "stage1-013"): ("이전지역인재 결격 문구 변경 여부 확인 중", "지역 표기 차이만으로 지원 불가 조건이 달라졌다고 판단하지 않습니다."),
    ("kepco-2025-2026-h2", "stage1-014"): ("보훈 전형 지원 불가 대상 추가", "취업지원대상자가 아니면 보훈 모집단위에 지원할 수 없습니다."),
    ("kepco-2025-2026-h2", "stage1-015"): ("데이터 경진대회 우대 명칭 변경", "해당 대회 수상자는 대회명과 수상 시점이 현재 기준에 맞는지 확인해야 합니다."),
    ("kepco-2025-2026-h2", "stage1-016"): ("발명대회 우대 명칭 변경", "기존 발명특허대전 수상 경력이 새 명칭의 우대 기준에 포함되는지 확인해야 합니다."),
    ("kepco-2025-2026-h2", "stage1-017"): ("청년청렴 Auditor 우수활동자 가점 신설", "해당 우수활동자는 서류전형에서 10% 가점을 받을 수 있습니다."),
    ("kepco-2025-2026-h2", "stage1-018"): ("청년청렴 가점 적용연도 명시", "2025년도 선정 우수활동자부터 새 가점이 적용됩니다."),
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


def change_card(change: Mapping[str, Any], titles: Mapping[str, str], pair_id: str) -> None:
    plain_title, impact = CHANGE_COPY.get(
        (pair_id, str(change.get("id"))),
        (str(change["title"]), "지원자에게 미치는 영향을 추가 확인 중입니다."),
    )
    with st.container(border=True):
        left, right = st.columns([4, 1])
        with left:
            st.markdown(
                f'<div class="change-title">{escape(plain_title)}</div>',
                unsafe_allow_html=True,
            )
            st.caption(f'{change["category"]} · 중요도 {change["importance"]}')
            st.markdown(f"**지원자에게 의미:** {impact}")
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
