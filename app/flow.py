"""화면 2개(공고 목록 → 공고 상세)가 같이 쓰는 것 (11-21 구조 개편).

조건은 주소창 쿼리(t=직렬, r=지역, c=자격증, p=공고)에도 넣는다. 공고 줄을 누르면 상세 화면이 새로 열리는데,
그때 화면 상태(session_state)가 비어도 조건과 공고를 그대로 이어 가기 위해서다. 개인정보는 넣지 않는다.
"""

from __future__ import annotations

from html import escape
from typing import Any, Iterable, Mapping
from urllib.parse import urlencode

import streamlit as st

from src.eligibility import EligibilityResult, UserCondition, evaluate

SEARCH_PAGE = "app/pages/search.py"
DETAIL_PAGE = "app/pages/detail.py"
SEP = "·"
RELEVANCE = {"match": 0, "region_mismatch": 1, "track_missing": 2}
STATUS = {"eligible": 0, "ambiguous": 1, "ineligible": 2}


def condition_from_query() -> dict[str, Any] | None:
    params = st.query_params
    tracks = [item for item in str(params.get("t") or "").split(SEP) if item]
    region = str(params.get("r") or "")
    if not tracks or not region:
        return None
    certificates = [item for item in str(params.get("c") or "").split(",") if item]
    return {"tracks": tracks, "track": tracks[0], "region": region, "certificates": certificates}


def current_condition() -> dict[str, Any] | None:
    """화면에 저장된 조건, 없으면 주소창 조건"""
    saved = st.session_state.get("user_condition")
    if saved:
        saved.setdefault("tracks", [saved["track"]])
        return saved
    restored = condition_from_query()
    if restored:
        st.session_state["user_condition"] = restored
    return restored


def query(condition: Mapping[str, Any] | None, pair_id: str | None = None) -> dict[str, str]:
    params: dict[str, str] = {}
    if condition:
        params["t"] = SEP.join(condition.get("tracks") or [condition["track"]])
        params["r"] = str(condition["region"])
        if condition.get("certificates"):
            params["c"] = ",".join(condition["certificates"])
    if pair_id:
        params["p"] = pair_id
    return params


def detail_href(condition: Mapping[str, Any] | None, pair_id: str) -> str:
    return "detail?" + urlencode(query(condition, pair_id))


def search_href(condition: Mapping[str, Any] | None) -> str:
    params = query(condition)
    return "./" + ("?" + urlencode(params) if params else "")


def user_conditions(condition: Mapping[str, Any]) -> list[UserCondition]:
    return [UserCondition(track, str(condition["region"]), tuple(condition.get("certificates") or ()))
            for track in condition.get("tracks") or [condition["track"]]]


def best_results(condition: Mapping[str, Any], reports: Iterable[Mapping[str, Any]]) -> list[tuple[EligibilityResult, str]]:
    """직렬을 여러 개 고르면 공고마다 가장 나은 직렬의 판정 하나 (판정 로직은 그대로, 직렬마다 evaluate)"""
    output = []
    for report in reports:
        candidates = [(evaluate(item, report), item.track) for item in user_conditions(condition)]
        candidates.sort(key=lambda pair: (RELEVANCE[pair[0].relevance], STATUS.get(pair[0].status or "", 3)))
        output.append(candidates[0])
    output.sort(key=lambda pair: (RELEVANCE[pair[0].relevance], STATUS.get(pair[0].status or "", 3), pair[0].deadline))
    return output


def condition_line(condition: Mapping[str, Any] | None) -> str:
    if not condition:
        return ""
    from app.pages.matches import region_text

    tracks = "·".join(condition.get("tracks") or [condition["track"]])
    certificates = ", ".join(condition.get("certificates") or []) or "자격증 없음"
    return f"{tracks} · {region_text(str(condition['region']).split(SEP))} · {certificates}"


def top_bar(condition: Mapping[str, Any] | None = None) -> None:
    """위쪽 메뉴: '공채레이더 / 공고 찾기' 두 개만 (질문은 상세 안으로)"""
    st.markdown(
        f'<div class="topbar"><span class="topbar-name">공채레이더</span>'
        f'<a href="{escape(search_href(condition))}" target="_self">공고 찾기</a></div>',
        unsafe_allow_html=True,
    )
