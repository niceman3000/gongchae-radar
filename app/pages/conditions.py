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


EXAMPLES = (  # (예시, 누구 이야기인지, 무엇을 볼 수 있는지)
    (EXAMPLE, "전기기사가 있는 전기 준비생", "지원 가능 공고와 내 자격증 가점을 볼 수 있어요"),
    (EXAMPLE_NO_CERT, "자격증이 아직 없는 전기 준비생", "자격증 없이 낼 수 있는 곳과 '애매'한 곳이 갈려요"),
)


def _condition(tracks: list[str], regions: list[str], certificates: list[str]) -> dict:
    if ANY_REGION in regions:
        regions = list(REGIONS)
    return {"tracks": list(tracks), "track": tracks[0], "region": "·".join(regions), "certificates": list(certificates)}


def _use_example(example: dict) -> None:
    """예시 카드: 조건을 채우고 바로 맞춤 공고로 (위젯이 그려지기 전에 값을 넣어야 해서 on_click)"""
    st.session_state["condition_tracks"] = [example["track"]]
    st.session_state["condition_regions"] = list(example["regions"])
    st.session_state["condition_certificates"] = list(example["certificates"])
    st.session_state["user_condition"] = _condition([example["track"]], list(example["regions"]), list(example["certificates"]))
    st.session_state["go_matches"] = True


def _guide() -> None:
    """'예시로 해 보기'를 안내 상자로 (11-21 사용자: 가이드처럼)"""
    st.markdown('<div class="g-head"><span class="g-step">처음이라면</span> 예시로 먼저 해 보세요'
                '<div class="g-sub">카드를 누르면 조건이 채워지고 바로 맞춤 공고로 넘어가요. 마음에 들면 아래에서 내 조건으로 바꾸면 돼요.</div></div>',
                unsafe_allow_html=True)
    for column, (index, (example, who, what)) in zip(st.columns(2), enumerate(EXAMPLES, 1)):
        with column.container(border=True, key=f"example-card-{index}"):
            chips = "".join(f'<span class="chip">{escape(text)}</span>' for text in
                            (example["track"], "·".join(example["regions"]), ", ".join(example["certificates"]) or "자격증 없음"))
            st.markdown(f'<div class="g-card-label">예시 {index}</div><div class="g-card-who">{escape(who)}</div>'
                        f'<div class="g-chips">{chips}</div><div class="g-card-what">{escape(what)}</div>',
                        unsafe_allow_html=True)
            st.button("이 조건으로 보기 ›", key=f"example-{index}", type="tertiary", on_click=_use_example, args=(example,))


def _preview(reports: list[dict]) -> None:
    """'이렇게 보여 드려요': 예시 조건의 실제 결과 한 줄 + 한전 변경점 한 줄 (2차 점검 8번: 누르기 전에 무슨 서비스인지)"""
    from app.pages.matches import is_open, match_row_html
    from app.ui_components import concise_change_title
    from src.eligibility import UserCondition, evaluate_all

    condition = UserCondition(EXAMPLE["track"], "·".join(EXAMPLE["regions"]), tuple(EXAMPLE["certificates"]))
    results = [item for item in evaluate_all(condition, reports) if item.relevance == "match"]
    row = next((item for item in results if is_open(item)), results[0] if results else None)
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


def example_preview(reports: list[dict]) -> dict | None:
    """첫 화면 오른쪽 미리보기 카드 (11-22 첫 화면 비율 메모 ③).
    숫자는 손으로 쓰지 않고, 예시 버튼 '전기기사 있는 전기 준비생'과 같은 조건으로 앱이 실제로 낸 결과를 쓴다."""
    from app.pages.matches import _short_notice, is_open, relevant_bonus
    from src.change_summary import application_period, summarize
    from src.eligibility import UserCondition, evaluate_all

    condition = UserCondition(EXAMPLE["track"], "·".join(EXAMPLE["regions"]), tuple(EXAMPLE["certificates"]))
    results = [item for item in evaluate_all(condition, reports) if item.relevance == "match" and item.status == "eligible"]
    if not results:
        return None
    from app.pages.matches import is_upcoming
    result = next((item for item in results if is_open(item)), None) or \
        next((item for item in results if is_upcoming(item)), results[0])
    report = next(item for item in reports if item.get("pair_id") == result.pair_id)
    rows = []
    bonus = max(relevant_bonus(result), key=lambda row: row["points"], default=None)
    if bonus:
        pages = sorted({item["page"] for item in bonus.get("evidence") or [] if item.get("page")})
        rows.append(("자격증 가점", f"{bonus['certificate']} {bonus['points']:g}{bonus.get('unit') or '점'}", pages[0] if pages else None))
    changed = next((row for row in summarize(report) if row.status == "바뀜"), None)
    if changed:
        rows.append(("작년과 달라진 점", changed.answer.split(" · ")[0], None))
    first, last, hour = application_period(report)
    if first and last:
        rows.append(("원서 접수", f"{first:%m.%d} ~ {last:%m.%d} {hour}".strip(), None))
    return {"institution": result.institution, "notice": _short_notice(result), "label": "지원 가능", "rows": rows}


def _preview_card(reports: list[dict]) -> None:
    preview = example_preview(reports)
    if not preview:
        return
    rows = "".join(
        f'<div class="pv-row"><span>{escape(name)}</span><b>{escape(value)}'
        + (f'<span class="pv-page">{page}쪽</span>' if page else "") + "</b></div>"
        for name, value, page in preview["rows"])
    st.markdown(
        f'<div class="pv"><div class="pv-top"><span>실제 결과 예시 · 전기 · 부산·울산 · 전기기사</span></div>'
        f'<div class="pv-title">{escape(preview["institution"])} {escape(preview["notice"])}'
        f'<span class="pv-badge">{escape(preview["label"])}</span></div>{rows}</div>',
        unsafe_allow_html=True)


FEATURES = (  # 이 앱이 하는 일 3가지 (화면 정리 메모 1번: 미리보기 대신)
    ("지원 가능 · 애매 · 안 맞음", "판정마다 공고문 쪽수를 붙여요"),
    ("작년과 달라진 점 5줄", "인원·전형·자격·가점·일정"),
    ("공고문에 물어보기", "공고문 원문 안에서만 답해요"),
)


def render_conditions_page() -> None:
    """① 내 조건 입력 (화면 정리 메모 1번): 소개 → 조건 입력 → 하는 일 3가지. 1440×900에서 스크롤 없이"""
    apply_styles()
    if st.session_state.pop("go_matches", False):
        st.switch_page(MATCHES_PAGE)
    reports, _ = load_reports()
    tracks, _ = available_tracks(reports)
    hero, side = st.columns([1.25, 1], vertical_alignment="center")
    hero.markdown(
        f"""<div class="hero">
        <div class="hero-kicker">공기업 신입 공채 <b>{len(reports)}곳</b> · 작년 공고와 비교 · 공고문 쪽수로 근거 확인</div>
        <div class="hero-title">작년 공고와 뭐가 달라졌는지,<br>나는 지원할 수 있는지.</div>
        <div class="hero-lead">직렬·지역·자격증만 고르면 지원 조건과 작년 대비 바뀐 점을 공고문 쪽수와 함께 보여 줘요.</div>
        </div>""",
        unsafe_allow_html=True,
    )
    with side:
        _preview_card(reports)
    saved = st.session_state.get("user_condition") or {}
    st.session_state.setdefault("condition_tracks", [track for track in saved.get("tracks", [saved.get("track")]) if track in tracks]
                                or ([tracks[0]] if tracks else []))
    st.session_state.setdefault("condition_regions", saved.get("region", "").split("·") if saved.get("region") else [])
    st.session_state.setdefault("condition_certificates", list(saved.get("certificates") or []))
    with st.container(key="condition-box"):
        # 직렬은 좁게, 지역·자격증은 넓게 (지역 3개를 골라도 안 잘리게)
        columns = st.columns([1.7, 3.6, 2.7, 1.3], vertical_alignment="bottom")
        with columns[0]:
            chosen = st.multiselect("희망 직렬", options=tracks, key="condition_tracks", placeholder="직렬")
        with columns[1]:
            regions = st.multiselect("근무 지역 (여러 개)", options=[ANY_REGION, *REGIONS], key="condition_regions",
                                     placeholder="지역을 골라 주세요")
        with columns[2]:
            certificates = st.multiselect(
                "보유 자격증 (없으면 비워 두기)",
                options=sorted(set(COMMON_CERTIFICATES) | set(st.session_state["condition_certificates"])),
                key="condition_certificates", accept_new_options=True, placeholder="검색하거나 직접 입력",
            )
        with columns[3]:
            clicked = st.button("공고 찾기", type="primary", use_container_width=True)
        label, first, second, _ = st.columns([1.15, 2.1, 2.1, 1.6], vertical_alignment="center")
        label.markdown('<div class="ex-label">처음이라면 예시로</div>', unsafe_allow_html=True)
        first.button("전기기사 있는 전기 준비생 ›", key="example-1", on_click=_use_example, args=(EXAMPLE,),
                     use_container_width=True)
        second.button("자격증 없는 전기 준비생 ›", key="example-2", on_click=_use_example, args=(EXAMPLE_NO_CERT,),
                      use_container_width=True)
        st.markdown('<div class="privacy-note">이름·연락처는 받지 않아요. 고른 조건은 이 창에서만 쓰고 저장하지 않아요.</div>',
                    unsafe_allow_html=True)
    if clicked:
        if not chosen or not regions:
            st.warning("희망 직렬과 근무 지역을 하나 이상 골라 주세요.")
        else:
            st.session_state["user_condition"] = _condition(chosen, regions, certificates)
            st.switch_page(MATCHES_PAGE)

    st.markdown('<div class="features">' + "".join(
        f'<div class="feature"><div class="feature-title">{escape(title)}</div><div class="feature-text">{escape(text)}</div></div>'
        for title, text in FEATURES) + "</div>", unsafe_allow_html=True)
    st.caption(DATA_NOTICE)


if __name__ == "__main__":
    render_conditions_page()
