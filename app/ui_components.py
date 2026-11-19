"""공채레이더 Streamlit 화면의 공통 표시 요소."""

from __future__ import annotations

from difflib import SequenceMatcher
import json
from html import escape
import re
from typing import Any, Mapping

import streamlit as st

from src.notice_text import describe_change, is_list_like, item_diff, list_section


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
    ("khnp-2025-2026-round3", "stage1-001"): (
        "공고 전체 선발인원 증가: 139명 → 229명",
        "일반전형·보훈특별전형·사회형평전형을 모두 합친 공고 전체 기준입니다. 위 구성표에서 전형별 증감을 확인할 수 있습니다.",
    ),
}

# 여러 후보를 묶은 카드의 제목·설명. 키는 (pair_id, change_groups의 id).
GROUP_COPY = {
    ("kepco-2025-2026-h2", "group-stage1-017"): (
        "청년청렴 Auditor 우수활동자 가점 신설",
        "2025년도에 선정된 우수활동자부터 1차(서류)전형에서 10% 가점을 받을 수 있습니다.",
    ),
    ("khnp-2025-2026-round3", "group-stage1-004"): (
        "자기소개서 제출 시점 변경: 입사지원 시 → 면접 대상자만",
        "2025년에는 모든 지원자가 입사지원 때 자기소개서를 내고, 사전평가 적부 판정을 통과해야 필기시험을 볼 수 있었습니다. "
        "2026년에는 입사지원 때 자기소개서를 쓰지 않고, 인재상·조직적합도 검사 후 면접 대상자만 제출합니다. "
        "지역모집·장애인·취업지원대상자 등은 응시자격만 맞으면 사전평가가 면제됩니다. "
        "(PDF 6·12쪽 내용과 일치하지만 쪽수·인용 기록 전이라 확정하지 않았습니다.)",
    ),
    ("khnp-2025-2026-round3", "group-stage1-010"): (
        "우대 대상 추가: 체험형인턴 우수인턴 (필기 가점 5점)",
        "우대사항 칸은 가점을 받는 사람 목록입니다(일반전형·사회형평/보훈특별전형 두 목록). "
        "두 목록 모두에 ‘체험형인턴 우수인턴’이 새로 들어갔습니다.\n\n"
        "- **누구:** 한수원 체험형 청년인턴(2025년도 제2차 이후)을 마치고 우수인턴으로 뽑힌 사람\n"
        "- **혜택:** 1차 전형(필기) 가점 5점, 우수인턴 확정일(수료일)부터 3년간 1회\n"
        "- **기존 가점과 차이:** ‘경진대회 성적우수자’ 가점은 이제 2025년도 제1차 이전 인턴에게만 적용\n\n"
        "PDF 7·8쪽 내용과 일치하지만 쪽수·인용 기록 전이라 확정하지 않았습니다.",
    ),
}

MEMBER_LABELS = {
    "text": "바뀐 문구",
    "added": "새로 생긴 문구",
    "removed": "사라진 문구",
    "number": "바뀐 숫자",
    "date": "바뀐 날짜",
    "rename": "바뀐 명칭",
    "list": "바뀐 목록",
}

LONG_TEXT_THRESHOLD = 90


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
        .diff-panel {
            border: 1px solid #e3e7ef; border-radius: .75rem; padding: .75rem .85rem;
            min-height: 7.5rem; background: #ffffff;
        }
        .diff-panel-prev { border-top: 3px solid #d56a6a; }
        .diff-panel-curr { border-top: 3px solid #3a9a6b; }
        .diff-label { color: #5f6b7d; font-size: .78rem; font-weight: 800; margin-bottom: .5rem; }
        .diff-text { color: #273247; line-height: 1.65; overflow-wrap: anywhere; }
        .diff-removed {
            color: #9f2f2f; background: #ffe3e3; border-radius: .25rem;
            padding: .08rem .2rem; text-decoration: line-through; font-weight: 750;
        }
        .diff-added {
            color: #11673f; background: #dcf7e9; border-radius: .25rem;
            padding: .08rem .2rem; font-weight: 750;
        }
        .diff-ellipsis { color: #8791a2; padding: 0 .15rem; }
        .status-eligible { color: #176b45; background: #ddf5e9; }
        .status-ambiguous { color: #875800; background: #fff0c7; }
        .status-ineligible { color: #9f2f2f; background: #ffe3e3; }
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


def md_text(value: Any) -> str:
    """공고 문구를 마크다운에 넣을 때 '1~10점 … 28~29쪽'이 취소선이 되지 않게 물결표를 이스케이프한다."""
    return str(value).replace("~", "\\~")


ELIGIBILITY_LABELS = {"eligible": "지원 가능", "ambiguous": "애매", "ineligible": "지원 불가"}


def eligibility_badge(status: str | None) -> None:
    label = ELIGIBILITY_LABELS.get(status or "", "판정 없음")
    safe = status if status in ELIGIBILITY_LABELS else "ambiguous"
    st.markdown(f'<span class="status-badge status-{safe}">{escape(label)}</span>', unsafe_allow_html=True)


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


def _shorten_equal_text(value: str, context: int = 24) -> str:
    if len(value) <= context * 2 + 10:
        return escape(value)
    return (
        escape(value[:context])
        + '<span class="diff-ellipsis"> … </span>'
        + escape(value[-context:])
    )


def diff_side_html(previous: str, current: str, side: str) -> str:
    """긴 문장에서 공통 부분은 접고 삭제·추가 구절만 강조한다."""
    previous_tokens = re.findall(r"\s+|[\w]+|[^\w\s]", previous)
    current_tokens = re.findall(r"\s+|[\w]+|[^\w\s]", current)
    matcher = SequenceMatcher(None, previous_tokens, current_tokens, autojunk=False)
    output: list[str] = []
    for tag, prev_start, prev_end, curr_start, curr_end in matcher.get_opcodes():
        if tag == "equal":
            output.append(_shorten_equal_text("".join(previous_tokens[prev_start:prev_end])))
        elif side == "prev" and tag in {"delete", "replace"}:
            removed = escape("".join(previous_tokens[prev_start:prev_end]))
            if removed:
                output.append(f'<span class="diff-removed">{removed}</span>')
        elif side == "curr" and tag in {"insert", "replace"}:
            added = escape("".join(current_tokens[curr_start:curr_end]))
            if added:
                output.append(f'<span class="diff-added">{added}</span>')
    return "".join(output)


def concise_change_title(
    change: Mapping[str, Any], pair_id: str, notice_info: Mapping[str, Any] | None = None
) -> tuple[str, str]:
    curated = CHANGE_COPY.get((pair_id, str(change.get("id"))))
    if curated:
        return curated

    described = describe_change(change, notice_info)
    if described:
        return described

    raw_title = str(change["title"])
    if len(raw_title) <= 80:
        return raw_title, "지원자에게 미치는 영향을 추가 확인 중입니다."

    prefix = raw_title.split(":", 1)[0].strip()
    subject = prefix if 1 <= len(prefix) <= 16 else str(change.get("category") or "공고")
    return (
        f"{subject} 세부 기준 변경",
        "빨간색은 이전 공고에서 빠진 내용, 초록색은 새 공고에 추가된 내용입니다. 정확한 적용 범위는 원문 확인이 필요합니다.",
    )


def _render_long_text_diff(previous: str, current: str) -> None:
    before, after = st.columns(2)
    with before:
        st.markdown(
            '<div class="diff-panel diff-panel-prev">'
            '<div class="diff-label">2025 · 삭제되거나 바뀐 부분</div>'
            f'<div class="diff-text">{diff_side_html(previous, current, "prev")}</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with after:
        st.markdown(
            '<div class="diff-panel diff-panel-curr">'
            '<div class="diff-label">2026 · 추가되거나 바뀐 부분</div>'
            f'<div class="diff-text">{diff_side_html(previous, current, "curr")}</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    with st.expander("원문 전체 비교"):
        old, new = st.columns(2)
        with old:
            _value_box("2025 전체 문구", previous)
        with new:
            _value_box("2026 전체 문구", current)


def evidence_card(item: Mapping[str, Any], titles: Mapping[str, str]) -> None:
    side = str(item["side"])
    year_label = "전년도" if side == "prev" else "당해 연도"
    st.caption(f"{year_label} · {titles[side]} · PDF {item['page']}쪽")
    st.markdown(
        f'<div class="evidence-quote">{escape(str(item["quote"]))}</div>',
        unsafe_allow_html=True,
    )


def _chips(items: list[str], kind: str) -> str:
    css = "diff-added" if kind == "added" else "diff-removed"
    return " ".join(f'<span class="{css}">{escape(item)}</span>' for item in items)


def _render_list_diff(previous: str, current: str) -> None:
    """쉼표로 늘어놓은 목록은 긴 문장 대신 생긴 항목·빠진 항목만 보여준다."""
    removed, added, same = item_diff(previous, current)
    if added:
        st.markdown(f"**새로 들어감:** {_chips(added, 'added')}", unsafe_allow_html=True)
    if removed:
        st.markdown(f"**목록에서 빠짐:** {_chips(removed, 'removed')}", unsafe_allow_html=True)
    with st.expander(f"그대로인 항목 {same}개와 원문 전체"):
        old, new = st.columns(2)
        with old:
            _value_box("2025 전체 문구", previous)
        with new:
            _value_box("2026 전체 문구", current)


def _render_values(change: Mapping[str, Any]) -> None:
    previous = change.get("prev_value")
    current = change.get("curr_value")
    if change.get("change_type") == "text" and is_list_like(previous) and is_list_like(current):
        _render_list_diff(previous, current)
        return
    if (
        isinstance(previous, str)
        and isinstance(current, str)
        and max(len(previous), len(current)) >= LONG_TEXT_THRESHOLD
    ):
        _render_long_text_diff(previous, current)
    else:
        before, after = st.columns(2)
        with before:
            _value_box("2025", previous)
        with after:
            _value_box("2026", current)


def _render_evidence(evidence: list[Mapping[str, Any]], titles: Mapping[str, str]) -> None:
    if evidence:
        with st.expander(f"공식 공고 근거 {len(evidence)}개"):
            for index, item in enumerate(evidence):
                evidence_card(item, titles)
                if index < len(evidence) - 1:
                    st.divider()
    else:
        st.caption("원문 근거를 대조 중인 후보입니다.")


def change_card(
    change: Mapping[str, Any],
    titles: Mapping[str, str],
    pair_id: str,
    notice_info: Mapping[str, Any] | None = None,
) -> None:
    plain_title, impact = concise_change_title(change, pair_id, notice_info)
    with st.container(border=True):
        left, right = st.columns([4, 1])
        with left:
            st.markdown(
                f'<div class="change-title">{escape(plain_title)}</div>',
                unsafe_allow_html=True,
            )
            st.caption(f'{change["category"]} · 중요도 {change["importance"]}')
            st.markdown(f"**지원자에게 의미:** {md_text(impact)}")
        with right:
            status_badge(str(change["status"]))

        _render_values(change)
        _render_evidence(list(change.get("evidence") or []), titles)


def group_title(
    unit: Mapping[str, Any], pair_id: str, notice_info: Mapping[str, Any] | None = None
) -> tuple[str, str]:
    group = unit["group"]
    curated = GROUP_COPY.get((pair_id, str(group["id"])))
    if curated:
        return curated
    described = [describe_change(change, notice_info) for change in unit["changes"]]
    first = next((item[0] for item in described if item), None)
    if first:
        return (
            f'{first} 외 {len(unit["changes"]) - 1}건',
            "같은 변경이 공고 여러 곳에 나뉘어 잡혀 한 장으로 묶었습니다. 아래 문구별 차이를 함께 확인하세요.",
        )
    terms = ", ".join(group.get("shared_terms") or [])
    return (
        f'{unit["category"]} 관련 변경 {len(unit["changes"])}건' + (f" · {terms}" if terms else ""),
        "같은 변경이 공고 여러 곳에 나뉘어 잡혀 한 장으로 묶었습니다. 아래 문구별 차이를 함께 확인하세요.",
    )


def _member_label(change: Mapping[str, Any], notice_info: Mapping[str, Any] | None) -> str:
    section = list_section(change.get("curr_value"), notice_info)
    if section and str(change.get("category")) == "가점":
        where = section if "전형" in section else f"{section} 전형"
        return f"{where} 가점 대상 목록"
    return MEMBER_LABELS.get(str(change.get("change_type")), "바뀐 내용")


def group_card(
    unit: Mapping[str, Any],
    titles: Mapping[str, str],
    pair_id: str,
    notice_info: Mapping[str, Any] | None = None,
) -> None:
    """여러 문장에 나뉘어 잡힌 같은 변경을 카드 한 장으로 보여준다."""
    plain_title, impact = group_title(unit, pair_id, notice_info)
    members = list(unit["changes"])
    with st.container(border=True):
        left, right = st.columns([4, 1])
        with left:
            st.markdown(
                f'<div class="change-title">{escape(plain_title)}</div>',
                unsafe_allow_html=True,
            )
            st.caption(
                f'{unit["category"]} · 중요도 {unit["importance"]} · 관련 문구 {len(members)}개를 묶음'
            )
            st.markdown(f"**지원자에게 의미:** {md_text(impact)}")
        with right:
            status_badge(str(unit["status"]))

        for index, change in enumerate(members, 1):
            label = _member_label(change, notice_info)
            st.markdown(f"**{index}. {label}**")
            _render_values(change)

        evidence = [item for change in members for item in change.get("evidence") or []]
        _render_evidence(evidence, titles)


def unit_card(
    unit: Mapping[str, Any],
    titles: Mapping[str, str],
    pair_id: str,
    notice_info: Mapping[str, Any] | None = None,
) -> None:
    if unit["kind"] == "group":
        group_card(unit, titles, pair_id, notice_info)
    else:
        change_card(unit["changes"][0], titles, pair_id, notice_info)
