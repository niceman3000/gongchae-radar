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
    st.markdown('<div class="radar-eyebrow">공채레이더 · 1단계</div>', unsafe_allow_html=True)
    st.markdown('<div class="radar-title">내 조건으로 공고 찾기</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="radar-subtitle">희망 직렬·지역·보유 자격증만 고르면, 공고에 적힌 지원 조건과 비교해 드립니다.</div>',
        unsafe_allow_html=True,
    )
    st.info("이름·연락처 같은 개인정보는 받지 않습니다. 입력한 조건은 이 브라우저 창에서만 쓰이고 저장되지 않습니다.")

    reports, _ = load_reports()
    tracks, reviewed = available_tracks(reports)
    st.caption(f"미리 모아 둔 공기업 공고 {len(reports)}곳 · {DATA_NOTICE}")
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
    if reviewed:
        st.caption(
            f"공고 원문으로 지원 자격을 정리한 직렬: {', '.join(reviewed)}. "
            "자동 비교 공고와 그 밖의 직렬은 자격 요건 확인 전이라 결과가 '애매'로 나옵니다."
        )
    regions = st.multiselect("희망 근무 지역 (여러 개 선택 가능)", options=REGIONS, key="condition_regions")
    certificates = st.multiselect(
        "보유 자격증 (없으면 비워 두세요 · 목록에 없으면 직접 입력)",
        options=sorted(set(COMMON_CERTIFICATES) | set(st.session_state["condition_certificates"])),
        key="condition_certificates",
        accept_new_options=True,
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


if __name__ == "__main__":
    render_conditions_page()
