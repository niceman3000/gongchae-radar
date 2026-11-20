"""② 맞춤 공고: 내 조건과 관련된 공고, 지원 상태(지원 가능·지원 불가·애매)와 판단 근거."""

from __future__ import annotations

from datetime import date
from html import escape
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from app.pages.report import _units
from app.ui_components import apply_styles, concise_change_title, eligibility_badge, evidence_card, md_text
from src.eligibility import EligibilityResult, UserCondition, evaluate_all
from app.report_data import DATA_NOTICE, collection_skipped, load_reports

CONDITIONS_PAGE = "app/pages/conditions.py"
REPORT_PAGE = "app/pages/report.py"


def format_deadline(value: str, today: date | None = None) -> str:
    if len(value) == 8 and value.isdigit():
        deadline = date(int(value[:4]), int(value[4:6]), int(value[6:]))
        text = f"{deadline:%Y.%m.%d}"
        today = today or date.today()
        if deadline < today:
            return f"{text} (접수 마감됨 · 지난 공고 시연 데이터)"
        return f"{text} (D-{(deadline - today).days})"
    return value


def representative_change(report: Mapping[str, Any]) -> str | None:
    """대표 변경 1건: 원문 확인된 카드 중 첫 번째, 없으면 후보 첫 번째."""
    units = _units(report)
    if not units:
        return None
    unit = next((item for item in units if item["status"] == "confirmed"), units[0])
    change = unit["changes"][0]
    title, _ = concise_change_title(change, str(report["pair_id"]), report.get("notice_info"))
    return f"{title} (원문 확인)" if unit["status"] == "confirmed" else title


def _bonus_lines(result: EligibilityResult, track: str) -> list[str]:
    by_cert: dict[str, list[str]] = {}
    for row in result.bonus:
        where = "·".join(row["units"]) if row["units"] else f"{track} 직렬"
        by_cert.setdefault(row["certificate"], []).append(f"{where} {row['points']}{row.get('unit') or '점'}")
    return [f"{cert}: {', '.join(parts)}" for cert, parts in by_cert.items()]


def match_card(result: EligibilityResult, report: Mapping[str, Any], track: str) -> None:
    titles = {"prev": report["prev"]["title"], "curr": report["curr"]["title"]}
    with st.container(border=True):
        left, right = st.columns([4, 1])
        with left:
            st.markdown(f'<div class="change-title">{escape(result.institution)}</div>', unsafe_allow_html=True)
            st.write(result.title)
            category = f"{report['category']} 공기업 · " if report.get("category") else ""
            st.caption(f"{category}접수 마감 {format_deadline(result.deadline)}")
        with right:
            eligibility_badge(result.status)

        st.markdown("**판단 이유**")
        for reason in result.reasons:
            st.markdown(f"- {md_text(reason)}")
        if result.review_items:
            st.markdown("**직접 확인할 것**")
            for item in result.review_items:
                st.markdown(f"- {md_text(item)}")

        bonus = _bonus_lines(result, track)
        if bonus:
            st.markdown("**내 자격증 가점:** " + md_text(" / ".join(bonus)))
            if result.bonus_rule:
                st.caption(md_text(result.bonus_rule))
        if result.common_checks:
            st.caption("모든 지원자 공통 확인: " + md_text(" · ".join(result.common_checks)))

        change = representative_change(report)
        if change:
            st.markdown(f"**작년 대비 대표 변경:** {md_text(change)}")

        if result.units:
            with st.expander(f"모집단위별 판정 {len(result.units)}개"):
                st.dataframe(
                    pd.DataFrame(
                        [{"모집단위": unit["name"], "판정": unit["label"], "이유": unit["reason"]} for unit in result.units]
                    ),
                    hide_index=True,
                    use_container_width=True,
                )
        evidence = _unique_evidence(result.evidence)
        if evidence:
            with st.expander(f"판정에 쓴 공고 근거 {len(evidence)}개"):
                for index, item in enumerate(evidence):
                    evidence_card(item, titles)
                    if index < len(evidence) - 1:
                        st.divider()

        if st.button("이 공고의 작년 대비 변경점 보기", key=f"open-{result.pair_id}"):
            st.session_state["selected_pair_id"] = result.pair_id
            st.switch_page(REPORT_PAGE)


def _unique_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen, output = set(), []
    for item in items:
        key = (item.get("side"), item.get("page"), item.get("quote"))
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output


def render_matches_page() -> None:
    apply_styles()
    st.markdown('<div class="radar-eyebrow">공채레이더 · 2단계</div>', unsafe_allow_html=True)
    st.markdown('<div class="radar-title">내 조건에 맞는 공고</div>', unsafe_allow_html=True)

    saved = st.session_state.get("user_condition")
    if not saved:
        st.warning("먼저 희망 직렬·지역·자격증을 입력해 주세요.")
        st.page_link(CONDITIONS_PAGE, label="내 조건 입력하러 가기", icon="📝")
        return

    condition = UserCondition.from_mapping(saved)
    certificates = ", ".join(condition.certificates) or "없음"
    st.markdown(
        f"**내 조건:** {condition.track} 직렬 · {', '.join(condition.regions)} · 자격증 {certificates}"
    )
    st.page_link(CONDITIONS_PAGE, label="조건 바꾸기", icon="📝")
    st.caption(
        "합격 가능성이나 순위가 아니라, 공고에 적힌 지원 조건과 내 조건을 비교한 결과입니다. "
        "확정할 수 없는 조건이 있으면 '애매'로 표시합니다. " + DATA_NOTICE
    )

    loaded, _ = load_reports()
    reports = {report["pair_id"]: report for report in loaded}
    results = evaluate_all(condition, reports.values())
    matched = [item for item in results if item.relevance == "match"]
    other_region = [item for item in results if item.relevance == "region_mismatch"]
    no_track = [item for item in results if item.relevance == "track_missing"]

    st.subheader(f"조건에 맞는 공고 {len(matched)}건")
    if not matched:
        st.info("희망 직렬과 지역이 모두 맞는 공고가 없습니다. 아래 다른 지역 공고를 확인해 보세요.")
    for result in matched:
        match_card(result, reports[result.pair_id], condition.track)

    if other_region:
        st.subheader(f"희망 지역에 근무지가 없는 공고 {len(other_region)}건")
        st.caption("직렬은 맞지만 공고의 근무지역에 희망 지역이 없습니다.")
        for result in other_region:
            match_card(result, reports[result.pair_id], condition.track)

    if no_track:
        st.caption(
            f"{condition.track} 직렬을 뽑지 않는 공고: " + ", ".join(item.institution for item in no_track)
        )

    skipped = collection_skipped()
    if skipped:
        with st.expander(f"공고를 모으지 못한 기관 {len(skipped)}곳"):
            for row in skipped:
                st.markdown(f"- {row['institution']}: {md_text(row.get('reason') or '사유 없음')}")


if __name__ == "__main__":
    render_matches_page()
