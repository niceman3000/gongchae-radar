"""① 내 조건 입력: 직렬·지역·자격증만 받는다 (이름·연락처 등 개인 식별 정보 없음)."""

from __future__ import annotations

from html import escape

import streamlit as st

from app.ui_components import apply_styles
from src.certificates import COMMON_CERTIFICATES
from src.eligibility import REGIONS
from app.report_data import DATA_NOTICE, load_reports

TRACK_ORDER = ["전기", "기계", "사무", "ICT", "토목", "건축", "원자력", "화학", "수자원"]
EXAMPLE = {"track": "전기", "regions": ["부산", "울산"], "certificates": ["전기기사"]}
# 자격증 없음 예시: 가능·애매·불가가 섞여 나와 판정 기능이 잘 보인다 (11-21 팀원 점검 9번)
# 지역은 부산·울산: 부산만이면 '지금 접수 중 0건'이 먼저 보임 (동서발전 근무지 울산, 2차 점검 7번)
EXAMPLE_NO_CERT = {"track": "전기", "regions": ["부산", "울산"], "certificates": []}
ANY_REGION = "지역 상관없음"
MATCHES_PAGE = "app/pages/matches.py"


def available_tracks(reports: list[dict]) -> tuple[list[str], list[str]]:
    """(모집 중인 직렬, 지원자격을 원문으로 정리한 직렬)"""
    tracks, reviewed = set(), set()
    for report in reports:
        requirements = report.get("requirements") or {}
        tracks.update(requirements.get("tracks") or [])
        for item in (requirements.get("certificates") or []) + (requirements.get("majors") or []):
            if item.get("kind") in {"accepted", "required"} and item.get("track"):
                reviewed.add(item["track"])
    ordered = [track for track in TRACK_ORDER if track in tracks] + sorted(tracks - set(TRACK_ORDER) - {"기타"})
    return ordered, [track for track in ordered if track in reviewed]


def _use_example(example: dict) -> None:
    """예시 링크: 위젯이 그려지기 전에 값을 넣어야 해서 on_click으로"""
    st.session_state["condition_track"] = example["track"]
    st.session_state["condition_regions"] = list(example["regions"])
    st.session_state["condition_certificates"] = list(example["certificates"])


def _preview(reports: list[dict]) -> None:
    """'이렇게 보여 드려요': 예시 조건의 실제 결과 한 줄 + 한전 변경점 한 줄 (2차 점검 8번: 누르기 전에 무슨 서비스인지)"""
    from app.pages.matches import is_open, match_row_html
    from app.ui_components import concise_change_title
    from src.eligibility import UserCondition, evaluate_all

    condition = UserCondition(EXAMPLE["track"], "·".join(EXAMPLE["regions"]), tuple(EXAMPLE["certificates"]))
    results = [item for item in evaluate_all(condition, reports) if item.relevance == "match"]
    row = next((item for item in results if is_open(item.deadline)), results[0] if results else None)
    change = None
    for report in reports:
        if report.get("pair_id") != "kepco-2025-2026-h2":
            continue
        for item in report.get("changes") or []:
            title, meaning = concise_change_title(item, str(report["pair_id"]), report.get("notice_info"))
            if "신설" in title and meaning:
                change = (str(report["institution"]), title, meaning)
                break
    if not row and not change:
        return
    st.markdown('<div class="c-head">이렇게 보여 드려요</div>', unsafe_allow_html=True)
    html = ""
    if row:
        html += ('<div class="p-label">맞춤 공고 (예시 조건으로 찾은 실제 결과)</div><div class="p-box">'
                 + match_row_html(row, first=True) + "</div>")
    if change:
        html += (f'<div class="p-label">작년과 달라진 점 ({escape(change[0])})</div><div class="p-box">'
                 f'<div class="c-title">{escape(change[1])}</div><div class="c-meaning">{escape(change[2])}</div></div>')
    st.markdown(html, unsafe_allow_html=True)


def render_conditions_page() -> None:
    """첫 화면 (11-21 팀원 2차 점검 8번·예시 1): 숫자 줄·둥근 상자 걷어 내고, 입력 3칸 한 줄, '공고 찾기'를 첫 화면 안으로"""
    apply_styles()
    reports, _ = load_reports()
    tracks, _ = available_tracks(reports)
    st.markdown(
        f"""<div class="hero">
        <div class="hero-kicker">공기업 신입 공채 <b>{len(reports)}곳</b> · 작년 공고와 비교</div>
        <div class="hero-title">작년 공고와 뭐가 달라졌는지,<br>나는 지원할 수 있는지.</div>
        <div class="hero-lead">직렬·지역·자격증만 고르면 지원 조건과 작년 대비 바뀐 점을<br>공고문 쪽수와 함께 보여 드려요.</div>
        </div><div class="c-head">내 조건</div>""",
        unsafe_allow_html=True,
    )
    saved = st.session_state.get("user_condition") or {}
    track_default = saved.get("track") if saved.get("track") in tracks else (tracks[0] if tracks else None)
    st.session_state.setdefault("condition_track", track_default)
    st.session_state.setdefault("condition_regions", saved.get("region", "").split("·") if saved.get("region") else [])
    st.session_state.setdefault("condition_certificates", list(saved.get("certificates") or []))

    left, middle, right = st.columns([1, 1.25, 1.25])
    with left:
        track = st.selectbox("희망 직렬", options=tracks, key="condition_track")
    with middle:
        regions = st.multiselect("근무 지역 (여러 개)", options=[ANY_REGION, *REGIONS], key="condition_regions",
                                 placeholder="지역을 골라 주세요")
    with right:
        certificates = st.multiselect(
            "보유 자격증 (없으면 비워 두기)",
            options=sorted(set(COMMON_CERTIFICATES) | set(st.session_state["condition_certificates"])),
            key="condition_certificates",
            accept_new_options=True,
            placeholder="검색하거나 직접 입력",
        )

    label, first, second, find = st.columns([0.8, 1.45, 1.6, 1.25], vertical_alignment="center")
    label.markdown('<div class="ex-label">예시로 해 보기</div>', unsafe_allow_html=True)
    first.button("전기·부산·울산·전기기사", type="tertiary", on_click=_use_example, args=(EXAMPLE,))
    second.button("전기·부산·울산·자격증 없음", type="tertiary", on_click=_use_example, args=(EXAMPLE_NO_CERT,))
    clicked = find.button("공고 찾기", type="primary", use_container_width=True)
    st.markdown('<div class="privacy-note">이름·연락처는 받지 않아요. 고른 조건은 이 창에서만 쓰고 저장하지 않아요.</div>',
                unsafe_allow_html=True)
    if clicked:
        if not track or not regions:
            st.warning("희망 직렬과 근무 지역을 하나 이상 골라 주세요.")
        else:
            if ANY_REGION in regions:
                regions = list(REGIONS)
            st.session_state["user_condition"] = {"track": track, "region": "·".join(regions),
                                                  "certificates": list(certificates)}
            st.switch_page(MATCHES_PAGE)

    _preview(reports)
    st.caption(DATA_NOTICE)


if __name__ == "__main__":
    render_conditions_page()
