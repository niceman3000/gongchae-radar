"""① 내 조건 입력: 직렬·지역·자격증만 받는다 (이름·연락처 등 개인 식별 정보 없음)."""

from __future__ import annotations

import streamlit as st

from app.ui_components import apply_styles
from src.certificates import COMMON_CERTIFICATES
from src.eligibility import REGIONS
from app.report_data import DATA_NOTICE, load_reports

TRACK_ORDER = ["전기", "기계", "사무", "ICT", "토목", "건축", "원자력", "화학", "수자원"]
EXAMPLE = {"track": "전기", "regions": ["부산", "울산"], "certificates": ["전기기사"]}
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


def render_conditions_page() -> None:
    apply_styles()
    reports, _ = load_reports()
    tracks, _ = available_tracks(reports)
    st.markdown(
        f"""<div class="hero">
        <div class="hero-title">작년 공고와 뭐가 달라졌는지,<br>나는 지원할 수 있는지.</div>
        <div class="hero-lead">공기업 신입 공채 공고를 작년 공고와 나란히 비교하고, 내 직렬·지역·자격증으로
        지원 가능 여부와 자격증 가점을 알려 드려요. 모든 판단에는 공고문 쪽수와 원문 문장이 붙어요.</div>
        <div class="hero-facts">
          <div><b>{len(reports)}곳</b>공기업 신입 공채</div>
          <div><b>작년 공고</b>와 나란히 비교</div>
          <div><b>쪽수·원문</b>으로 근거 확인</div>
        </div></div>""",
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown('<div class="form-head">내 조건으로 공고 찾기</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="privacy-note">이름·연락처 같은 개인정보는 받지 않아요. 고른 조건은 이 창에서만 쓰고 저장하지 않아요.</div>',
            unsafe_allow_html=True,
        )
        saved = st.session_state.get("user_condition") or {}

        if st.button("예시 조건으로 채우기 (전기 · 부산·울산 · 전기기사)"):
            st.session_state["condition_track"] = EXAMPLE["track"]
            st.session_state["condition_regions"] = EXAMPLE["regions"]
            st.session_state["condition_certificates"] = EXAMPLE["certificates"]

        track_default = saved.get("track") if saved.get("track") in tracks else (tracks[0] if tracks else None)
        st.session_state.setdefault("condition_track", track_default)
        st.session_state.setdefault("condition_regions", saved.get("region", "").split("·") if saved.get("region") else [])
        st.session_state.setdefault("condition_certificates", list(saved.get("certificates") or []))

        track = st.selectbox("희망 직렬", options=tracks, key="condition_track")
        regions = st.multiselect("희망 근무 지역 (여러 개 선택 가능)", options=REGIONS, key="condition_regions",
                                 placeholder="지역을 골라 주세요")
        certificates = st.multiselect(
            "보유 자격증 (없으면 비워 두세요 · 목록에 없으면 직접 입력)",
            options=sorted(set(COMMON_CERTIFICATES) | set(st.session_state["condition_certificates"])),
            key="condition_certificates",
            accept_new_options=True,
            placeholder="자격증 이름을 검색하거나 입력하세요",
        )

        if st.button("공고 찾기", type="primary", use_container_width=True):
            if not track or not regions:
                st.warning("희망 직렬과 근무 지역을 하나 이상 골라 주세요.")
                return
            st.session_state["user_condition"] = {
                "track": track,
                "region": "·".join(regions),
                "certificates": list(certificates),
            }
            st.switch_page(MATCHES_PAGE)
    st.caption(DATA_NOTICE)


if __name__ == "__main__":
    render_conditions_page()
