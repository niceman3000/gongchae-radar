"""② 맞춤 공고: 내 조건과 관련된 공고, 지원 상태(지원 가능·지원 불가·애매)와 판단 근거."""

from __future__ import annotations

from datetime import date
from html import escape
from typing import Any, Mapping

import streamlit as st

from app.pages.report import _units, _is_minor
from app.ui_components import apply_styles, concise_change_title, eligibility_badge, evidence_card, md_text
from src.eligibility import EligibilityResult, UserCondition, evaluate_all
from src.result_pdf import build_result_pdf
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
    # 이름·표기만 바뀐 사소한 변경은 대표로 고르지 않는다 (11-21)
    units = [item for item in units if not all(_is_minor(change) for change in item["changes"])] or units
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


def _short(text: str, limit: int = 90) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def region_text(regions: Any) -> str:
    from src.eligibility import REGIONS

    return "지역 상관없음" if set(regions) >= set(REGIONS) else ", ".join(regions)


def is_open(value: str, today: date | None = None) -> bool:
    """접수 마감일이 오늘 이후(오늘 포함)면 접수 중"""
    if len(value) == 8 and value.isdigit():
        return date(int(value[:4]), int(value[4:6]), int(value[6:])) >= (today or date.today())
    return False


def _deadline_chip(value: str) -> tuple[str, str]:
    """(칩 글자, css 클래스). 접수 중은 파랑·굵게, 지난 공고는 회색 (11-21 팀원 점검 12번)"""
    text = format_deadline(value)
    if "마감됨" in text:
        return f"마감 {text.split(' ')[0]} · 지난 공고", "chip"
    if len(value) == 8 and value.isdigit():
        return f"접수 중 · {text.split(' ')[0]}까지 {text.split(' ')[-1].strip('()')}", "chip chip-open"
    return f"마감 {text}", "chip"


PAST_LABELS = {"eligible": "조건 맞음", "ambiguous": "애매", "ineligible": "조건 안 맞음"}


def _best_bonus(result: EligibilityResult) -> str | None:
    best = None
    for row in result.bonus:
        try:
            points = float(row["points"])
        except (TypeError, ValueError):
            continue
        key = (row.get("unit") or "점", points)
        if best is None or (key[0] == best[0] and points > best[1]) or (best[0] == "%" and key[0] == "점"):
            best = key
    if not best:
        return None
    unit, points = best
    return f"내 가점 최대 {points:g}{unit}"


def _headline_reason(result: EligibilityResult) -> str:
    """한 줄 요약: 판정을 가른 이유 하나"""
    if result.status == "ambiguous" and result.review_items:
        return result.review_items[0]  # 모집단위 판정 이유가 먼저, 근무지 배치 안내는 맨 뒤 (eligibility.evaluate)
    return result.reasons[-1] if result.reasons else ""


def match_card(result: EligibilityResult, report: Mapping[str, Any], track: str) -> None:
    """공고 한 건 = 한 줄 요약(기관·판정·마감·가점·이유) + '자세히 보기'에 나머지 (11-20 디자인 정리)"""
    titles = {"prev": report["prev"]["title"], "curr": report["curr"]["title"]}
    status = result.status if result.status in {"eligible", "ambiguous", "ineligible"} else "ambiguous"
    chip_text, chip_class = _deadline_chip(result.deadline)
    chips = [f'<span class="{chip_class}">{escape(chip_text)}</span>']
    # 마감된 공고에는 '지원 가능' 대신 '조건 맞음' (지금 지원할 수 있다는 뜻으로 읽히지 않게)
    label = result.label if is_open(result.deadline) else PAST_LABELS.get(status, result.label)
    best = _best_bonus(result)
    if best:
        chips.append(f'<span class="chip chip-bonus">{escape(best)}</span>')
    if report.get("category"):
        chips.append(f'<span class="chip">{escape(str(report["category"]))} 공기업</span>')
    with st.container(border=True):
        st.markdown(
            f"""<div class="row-top"><div><div class="row-inst">{escape(result.institution)}</div>
            <div class="row-title">{escape(result.title)}</div></div>
            <span class="status-badge row-status status-{status}">{escape(label or '판정 없음')}</span></div>
            <div class="row-meta">{''.join(chips)}</div>
            <div class="row-reason">{escape(_short(_headline_reason(result)))}</div>""",
            unsafe_allow_html=True,
        )
        with st.expander("자세히 보기"):
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
                st.markdown("**모든 지원자 공통 확인**")
                for item in result.common_checks:
                    st.markdown(f"- {md_text(item)}")
            change = representative_change(report)
            if change:
                st.markdown(f"**작년 대비 대표 변경:** {md_text(change)}")
            if result.units:
                st.markdown(f"**모집단위별 판정 {len(result.units)}개**")
                for unit in result.units:
                    st.markdown(f"- **{md_text(unit['name'])}** · {unit['label']} — {md_text(unit['reason'])}")
            evidence = _unique_evidence(result.evidence)
            if evidence:
                st.markdown(f"**판정에 쓴 공고 근거 {len(evidence)}개**")
                for item in evidence:
                    evidence_card(item, titles)
            if st.button("이 공고의 작년 대비 변경점 보기", key=f"open-{result.pair_id}"):
                st.session_state["selected_pair_id"] = result.pair_id
                st.switch_page(REPORT_PAGE)


def verdict_bar(results: list[EligibilityResult]) -> None:
    """맞춤 공고 맨 위: 판정 3가지가 몇 건인지 한 줄 색 막대로"""
    counts = {key: sum(1 for item in results if item.status == key) for key in ("eligible", "ambiguous", "ineligible")}
    total = sum(counts.values()) or 1
    names = {"eligible": "조건 맞음", "ambiguous": "애매", "ineligible": "조건 안 맞음"}
    colors = {"eligible": "#12A574", "ambiguous": "#F2B035", "ineligible": "#E5534B"}
    bar = "".join(f'<span class="vb-{key}" style="width:{counts[key] / total * 100:.1f}%"></span>'
                  for key in counts if counts[key])
    legend = "".join(f'<span><i style="background:{colors[key]}"></i>{names[key]}<b>{counts[key]}</b></span>' for key in counts)
    st.markdown(f'<div class="verdict"><div class="verdict-bar">{bar}</div>'
                f'<div class="verdict-legend">{legend}</div></div>', unsafe_allow_html=True)


def _unique_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen, output = set(), []
    for item in items:
        key = (item.get("side"), item.get("page"), item.get("quote"))
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output


def _pdf_button(condition: UserCondition, reports: Mapping[str, Any], matched: list[EligibilityResult],
                other_region: list[EligibilityResult], no_track: list[EligibilityResult]) -> None:
    """결과를 PDF로 받기 (T047). 같은 조건·같은 리포트면 다시 만들지 않는다."""
    key = (condition.track, condition.region, condition.certificates,
           tuple(sorted((pair_id, str(report.get("checked_at"))) for pair_id, report in reports.items())))
    cache = st.session_state.get("result_pdf")
    if not cache or cache[0] != key:
        try:
            data = build_result_pdf(
                condition,
                [(result, reports[result.pair_id], representative_change(reports[result.pair_id])) for result in matched],
                [(result, reports[result.pair_id], representative_change(reports[result.pair_id])) for result in other_region],
                [result.institution for result in no_track],
            )
        except Exception as exc:  # noqa: BLE001 - PDF가 안 만들어져도 화면은 그대로 보여준다
            st.caption(f"PDF를 만들지 못했어요: {exc}")
            return
        cache = (key, data)
        st.session_state["result_pdf"] = cache
    st.download_button(
        "결과를 PDF로 받기",
        data=cache[1],
        file_name=f"공채레이더_{condition.track}_{date.today():%Y%m%d}.pdf",
        mime="application/pdf",
        icon="📄",
        type="secondary",
    )


def render_matches_page() -> None:
    apply_styles()
    st.markdown('<div class="radar-title">내 조건에 맞는 공고</div>', unsafe_allow_html=True)

    saved = st.session_state.get("user_condition")
    if not saved:
        st.warning("먼저 희망 직렬·지역·자격증을 입력해 주세요.")
        st.page_link(CONDITIONS_PAGE, label="내 조건 입력하러 가기", icon=":material/tune:")
        return

    condition = UserCondition.from_mapping(saved)
    certificates = ", ".join(condition.certificates) or "없음"
    st.markdown(
        f'<div class="radar-subtitle">{escape(condition.track)} 직렬 · {escape(region_text(condition.regions))} · '
        f'자격증 {escape(certificates)}</div>',
        unsafe_allow_html=True,
    )

    loaded, _ = load_reports()
    reports = {report["pair_id"]: report for report in loaded}
    results = evaluate_all(condition, reports.values())
    matched = [item for item in results if item.relevance == "match"]
    other_region = [item for item in results if item.relevance == "region_mismatch"]
    no_track = [item for item in results if item.relevance == "track_missing"]

    if st.button("조건 바꾸기", icon=":material/edit:"):
        st.switch_page(CONDITIONS_PAGE)

    open_now = [item for item in matched if is_open(item.deadline)]
    past = [item for item in matched if not is_open(item.deadline)]
    st.subheader(f"조건에 맞는 공고 {len(matched)}건")
    if matched:
        verdict_bar(matched)
    st.caption("합격 가능성이 아니라 공고에 적힌 지원 조건과 내 조건을 비교한 결과예요. 확정할 수 없으면 '애매'로 표시해요. "
               "기관마다 가장 최근 신입 공채 기준이라, 접수가 끝난 공고는 다음 채용 준비용으로 보세요.")
    if not matched:
        st.info("희망 직렬과 지역이 모두 맞는 공고가 없어요. 아래 다른 지역 공고를 확인해 보세요.")
    if matched:
        st.markdown(f'<div class="section-head">지금 접수 중 {len(open_now)}건</div>', unsafe_allow_html=True)
        if not open_now:
            st.caption("지금 접수 중인 공고는 없어요.")
        for result in open_now:
            match_card(result, reports[result.pair_id], condition.track)
        if past:
            st.markdown(f'<div class="section-head">접수 끝난 공고 {len(past)}건 · 다음 채용 대비</div>',
                        unsafe_allow_html=True)
            for result in past:
                match_card(result, reports[result.pair_id], condition.track)

    if other_region:
        st.subheader(f"희망 지역에 근무지가 없는 공고 {len(other_region)}건")
        st.caption("직렬은 맞지만 공고의 근무지역에 희망 지역이 없어요.")
        for result in other_region:
            match_card(result, reports[result.pair_id], condition.track)

    if no_track:
        st.caption(
            f"{condition.track} 직렬을 뽑지 않는 공고: " + ", ".join(item.institution for item in no_track)
        )

    st.divider()
    _pdf_button(condition, reports, matched, other_region, no_track)
    st.caption(DATA_NOTICE)

    skipped = collection_skipped()
    if skipped:
        with st.expander(f"공고를 모으지 못한 기관 {len(skipped)}곳"):
            for row in skipped:
                st.markdown(f"- {row['institution']}: {md_text(row.get('reason') or '사유 없음')}")


if __name__ == "__main__":
    render_matches_page()
