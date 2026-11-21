"""② 맞춤 공고: 내 조건과 관련된 공고, 지원 상태(지원 가능·지원 불가·애매)와 판단 근거."""

from __future__ import annotations

from datetime import date
from html import escape
import re
from typing import Any, Mapping

import streamlit as st

from app.pages.report import _units, _is_minor
from app.ui_components import apply_styles, concise_change_title, md_text
from src.eligibility import readable_unit_name, EligibilityResult, UserCondition, evaluate_all
from src.result_pdf import build_result_pdf
from app.report_data import DATA_NOTICE, collection_skipped, load_reports

CONDITIONS_PAGE = "app/pages/conditions.py"
REPORT_PAGE = "app/pages/detail.py"  # ③ 공고 비교 (11-21 저녁: 상세 화면)
QA_PAGE = "app/pages/qa.py"


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
    return f"자격증 반영 {points:g}{unit}"  # '가점'이 아니라 서류 점수인 곳이 있어 중립적인 말 (화면 정리 메모 2번)


def _headline_reason(result: EligibilityResult) -> str:
    """한 줄 요약: 판정을 가른 이유 하나"""
    if result.status == "ambiguous" and result.review_items:
        return result.review_items[0]  # 모집단위 판정 이유가 먼저, 근무지 배치 안내는 맨 뒤 (eligibility.evaluate)
    return result.reasons[-1] if result.reasons else ""


VERDICT_TEXT = {"eligible": "✓ 지원 가능", "ambiguous": "애매", "ineligible": "지원 불가"}


def _date_short(value: str, today: date | None = None) -> str:
    """올해 마감은 '12.01', 다른 해는 '2025.12.08' (11-21 팀원 2차 점검 4번: 연도가 없어 정렬이 틀려 보임)"""
    if len(value) == 8 and value.isdigit():
        if value[:4] == str((today or date.today()).year):
            return f"{value[4:6]}.{value[6:]}"
        return f"{value[:4]}.{value[4:6]}.{value[6:]}"
    return value


def _d_day(value: str, today: date | None = None) -> str:
    if len(value) == 8 and value.isdigit():
        days = (date(int(value[:4]), int(value[4:6]), int(value[6:])) - (today or date.today())).days
        return "오늘 마감" if days == 0 else f"D-{days}"
    return ""


def _short_title(result: EligibilityResult) -> str:
    """공고 제목 앞의 기관 이름만 떼고 그대로 (11-21 팀원 2차 점검 2번: 괄호를 지우다 앞부분까지 잘림 → 괄호는 두고 CSS로 한 줄 자름)"""
    title = re.sub(r"^[\[(]?" + re.escape(result.institution) + r"(\(주\))?[\])]?\s*", "", result.title.strip())
    title = re.sub(r"\s+([,.)])", r"\1", title)  # '일반직 , 연구직' → '일반직, 연구직'
    return " ".join((title or result.title).split())


def _reason_line(result: EligibilityResult, status: str) -> str:
    """굵은 모집단위 이름 · 판정을 가른 이유 (예시 1)"""
    unit = next((item for item in result.units if item.get("status") == status), None)
    reason = _headline_reason(result)
    if unit and status != "ambiguous":
        reason = unit.get("reason") or reason
    name = f'<span class="m-unit">{escape(readable_unit_name(str(unit["name"])))}</span> · ' if unit else ""
    return name + escape(" ".join(str(reason).split()))  # 길이는 CSS가 한 줄로 자름 (2차 점검 9번)


def match_row_html(result: EligibilityResult, first: bool = False) -> str:
    """공고 한 건 = 줄 하나: 기관명 · 보조 정보 한 줄 · 이유 한 줄(넘치면 …), 오른쪽 끝에 D-day와 판정.
    11-21 팀원 2차 점검 9번(예시 2): 이유 한 줄 자르기, 모집단위 이름은 회색 보통 글씨, 오른쪽 '마감' 글자 없앰, 구분 기호는 '·' 하나"""
    status = result.status if result.status in {"eligible", "ambiguous", "ineligible"} else "ambiguous"
    open_now = is_open(result.deadline)
    # 마감된 공고에는 '지원 가능' 대신 '조건 맞음' (지금 지원할 수 있다는 뜻으로 읽히지 않게)
    label = VERDICT_TEXT[status] if open_now else PAST_LABELS.get(status, result.label or "")
    sub = [escape(_short_title(result)), f"{_date_short(result.deadline)} 마감"]
    best = _best_bonus(result)
    if best:
        sub.append(escape(best))
    side = f'<span class="m-dday">{escape(_d_day(result.deadline))}</span>' if open_now else ""
    tone = status if open_now or status != "eligible" else "past"
    return (f"""<div class="m-row{' m-first' if first else ''}"><div class="m-main"><div class="m-inst">{escape(result.institution)}</div>
        <div class="m-sub">{'<span class="m-bar">·</span>'.join(sub)}</div>
        <div class="m-reason">{_reason_line(result, status)}</div></div>
        <div class="m-side">{side}<span class="m-verdict v-{tone}">{escape(label)}</span></div></div>""")


def match_card(result: EligibilityResult, report: Mapping[str, Any], track: str, first: bool = False) -> None:
    st.markdown(match_row_html(result, first), unsafe_allow_html=True)
    with st.expander("자세히 보기"):
        _render_detail(result, report, track, is_open(result.deadline))


def _section(title: str) -> None:
    st.markdown(f'<div class="d-head">{escape(title)}</div>', unsafe_allow_html=True)


def _bullets(items: list[str]) -> None:
    st.markdown('<ul class="d-list">' + "".join(f"<li>{item}</li>" for item in items) + "</ul>",
                unsafe_allow_html=True)


LANGUAGE = re.compile(r"토익|TOEIC|어학|외국어|영어")


def _check_items(result: EligibilityResult) -> list[str]:
    """내가 확인할 것: 어학 기준을 맨 위에 굵게, 그다음 판정 확인·가점 규칙·공통 조건 (예시 2)"""
    items = [str(item) for item in result.review_items]
    if result.bonus_rule:
        items.append(str(result.bonus_rule))
    items += [str(item) for item in result.common_checks]
    language = [item for item in items if LANGUAGE.search(item)]
    rest = [item for item in items if item not in language]
    output = []
    for item in language:
        head, _, tail = item.partition("(")
        output.append(f"<b>{escape(head.strip())}</b>" + (f" ({escape(tail)}" if tail else ""))
    return output + [escape(item) for item in rest]


def _render_detail(result: EligibilityResult, report: Mapping[str, Any], track: str, open_now: bool) -> None:
    """펼친 카드: 구역마다 검은 선 + 굵은 제목, 근거는 '쪽 | 원문' 표 (11-21 팀원 예시 2)"""
    _section("판단 이유")
    reasons = [escape(str(reason)) for reason in result.reasons]
    bonus = _bonus_lines(result, track)
    if bonus:
        reasons.append("내 자격증 가점: " + escape(" / ".join(bonus)))
    _bullets(reasons)

    if result.units:
        _section(f"모집단위별 판정 {len(result.units)}개")
        rows = "".join(
            f'<tr><td class="d-unit">{escape(readable_unit_name(str(unit["name"])))}</td>'
            f'<td class="v-{unit.get("status", "ambiguous")}">'
            f'{escape(unit["label"] if open_now else PAST_LABELS.get(unit.get("status"), unit["label"]))}</td>'
            f'<td>{escape(str(unit["reason"]))}</td></tr>'
            for unit in result.units
        )
        st.markdown(f'<table class="d-table"><thead><tr><th>모집단위</th><th>판정</th><th>이유</th></tr></thead>'
                    f"<tbody>{rows}</tbody></table>", unsafe_allow_html=True)

    checks = _check_items(result)
    if checks:
        _section("내가 확인할 것")
        _bullets(checks)

    evidence = _unique_evidence(result.evidence)
    if evidence:
        _section(f"판정에 쓴 공고 근거 {len(evidence)}개")
        rows = "".join(
            f'<tr><td class="d-page">{"올해" if item.get("side") == "curr" else "작년"} {escape(str(item.get("page")))}쪽</td>'
            f'<td>“{escape(str(item.get("quote")))}”</td></tr>'
            for item in evidence
        )
        st.markdown(f'<table class="d-table d-evidence"><thead><tr><th>쪽</th><th>공고문 원문</th></tr></thead>'
                    f"<tbody>{rows}</tbody></table>", unsafe_allow_html=True)

    left, right, _ = st.columns([1.3, 1.3, 2])
    if left.button("작년과 달라진 점 ›", key=f"open-{result.pair_id}", type="tertiary"):
        st.session_state["selected_pair_id"] = result.pair_id
        st.switch_page(REPORT_PAGE)
    if right.button("공고문에 물어보기 ›", key=f"ask-{result.pair_id}", type="tertiary"):
        st.session_state["selected_pair_id"] = result.pair_id
        st.switch_page(QA_PAGE)


def _list_head(title: str, count: int, hint: str) -> None:
    st.markdown(f'<div class="m-head"><div><span class="m-head-title">{escape(title)}</span> '
                f'<span class="m-head-count">{count}</span></div><span class="m-head-hint">{escape(hint)}</span></div>',
                unsafe_allow_html=True)


def _render_list(results: list[EligibilityResult], reports: Mapping[str, Any], track: str, key: str,
                 first: int | None = None, more_label: str = "더 보기") -> None:
    """줄 목록. first개만 먼저 보이고 나머지는 '더 보기' (펼친 카드 안에 펼치기를 또 넣을 수 없어 버튼으로)"""
    shown = results if first is None or st.session_state.get(f"more-{key}") else results[:first]
    for index, result in enumerate(shown):
        match_card(result, reports[result.pair_id], track, first=index == 0)
    rest = len(results) - len(shown)
    if rest > 0 and st.button(f"{more_label} {rest}건 더 보기 ▾", key=f"more-btn-{key}", type="tertiary"):
        st.session_state[f"more-{key}"] = True
        st.rerun()


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
        type="secondary",
        use_container_width=True,
    )


BAR = '<span class="m-bar">·</span>'


def initials(name: str) -> str:
    """기관 머리글자: '한국동서발전' → '동서', '한전KPS' → 'KPS', '인천국제공항공사' → '인천'"""
    name = re.sub(r"^(한국|주식회사)", "", name)
    if name.startswith("한전") and len(name) > 2:
        return name[2:5]
    return name[:2]


def _go_detail(pair_id: str) -> None:
    st.session_state["selected_pair_id"] = pair_id
    st.session_state["go_detail"] = True


def _short_notice(result: EligibilityResult) -> str:
    """목록용 짧은 공고명: 괄호 안 설명을 빼서 '…' 없이 한 줄 ('2027년 상반기 신입직원 선발')"""
    title = _short_title(result)
    for _ in range(3):
        title = re.sub(r"\s*\([^()]*\)", "", title)
    return " ".join(title.replace("채용공고", "").replace("채용 공고", "").split()) or _short_title(result)


def _row(result: EligibilityResult, report: Mapping[str, Any], open_card: bool) -> None:
    """공고 한 줄 (화면 정리 메모 2번): 접수 중 카드와 지난 공고 줄은 같은 틀(왼쪽 내용 + 오른쪽 150px 칸),
    접수 중은 바탕색만 다름. 오른쪽 칸에 D-day·판정·'공고 비교 ›'를 세로로. 판정 이유는 잘리지 않고 줄 바꿈.
    안 맞는 공고에는 자격증 점수를 숨김. 기관 머리글자 상자는 뺌('지역'·'수자' 같은 잘린 글자)."""
    from src.change_summary import prev_start_text

    status = result.status if result.status in {"eligible", "ambiguous", "ineligible"} else "ambiguous"
    now = is_open(result.deadline)
    label = VERDICT_TEXT[status] if now else PAST_LABELS.get(status, result.label or "")
    tone = status if now or status != "eligible" else "past"
    sub = [escape(_short_notice(result)), f"{_date_short(result.deadline)} 마감"]
    best = _best_bonus(result)
    if best and status != "ineligible":
        sub.append(escape(best))
    hint = ""
    if not now and prev_start_text(report):
        hint = (f'<span class="cal-chip"><span class="cal-icon"></span>다음 공고 참고 · '
                f'<b>작년엔 {escape(prev_start_text(report))} 접수 시작</b></span>')
    with st.container(key=f"row-{'open' if open_card else 'past'}-{result.pair_id}"):
        main, side = st.columns([5, 1.25], vertical_alignment="top")
        main.markdown(f'<div class="m-inst">{escape(result.institution)}</div>'
                      f'<div class="m-sub">{BAR.join(sub)}</div>'
                      f'<div class="m-reason m-wrap">{_reason_line(result, status)}</div>{hint}', unsafe_allow_html=True)
        dday = f'<span class="m-dday">{escape(_d_day(result.deadline))}</span>' if now else ""
        side.markdown(f'<div class="m-side">{dday}<span class="badge b-{tone}">{escape(label)}</span></div>',
                      unsafe_allow_html=True)
        side.button("공고 비교 ›", key=f"go-{result.pair_id}", on_click=_go_detail, args=(result.pair_id,),
                    use_container_width=True)


def _list(items: list[EligibilityResult], reports: Mapping[str, Any], key: str, first: int | None = None,
          more_label: str = "", open_cards: bool = False) -> None:
    shown = items if first is None or st.session_state.get(f"more-{key}") else items[:first]
    for result in shown:
        _row(result, reports[result.pair_id], open_cards)
    rest = len(items) - len(shown)
    if rest > 0 and st.button(f"{more_label} {rest}건 더 보기 ▾", key=f"more-btn-{key}", type="tertiary"):
        st.session_state[f"more-{key}"] = True
        st.rerun()


def _tiles(items: list[tuple[str, str, str]]) -> None:
    st.markdown('<div class="tiles">' + "".join(
        f'<div class="tile {css}"><div class="tile-label">{escape(label)}</div><div class="tile-value">{escape(value)}</div></div>'
        for label, value, css in items) + "</div>", unsafe_allow_html=True)


def render_matches_page() -> None:
    """② 맞춤 공고 (11-21 저녁 절충안): 요약 칸 5개, 접수 중은 파란 테두리 카드, 지난 공고는 줄 + 작년 접수일 칩"""
    from app.flow import best_results, current_condition

    apply_styles()
    if st.session_state.pop("go_detail", False):
        st.switch_page(REPORT_PAGE)
    condition = current_condition()
    if not condition:
        st.markdown('<div class="radar-title">내 조건에 맞는 공고</div>', unsafe_allow_html=True)
        st.warning("먼저 희망 직렬·지역·자격증을 입력해 주세요.")
        st.page_link(CONDITIONS_PAGE, label="내 조건 입력하러 가기", icon=":material/tune:")
        return
    loaded, _ = load_reports()
    reports = {report["pair_id"]: report for report in loaded}
    pairs = best_results(condition, reports.values())
    results = [result for result, _ in pairs]
    matched = [item for item in results if item.relevance == "match"]
    other_region = [item for item in results if item.relevance == "region_mismatch"]
    no_track = [item for item in results if item.relevance == "track_missing"]
    open_now = sorted((item for item in matched if is_open(item.deadline)), key=lambda item: item.deadline)
    past = sorted((item for item in matched if not is_open(item.deadline)), key=lambda item: item.deadline, reverse=True)
    tracks = "·".join(condition.get("tracks") or [condition["track"]])

    head, button = st.columns([5, 1.2], vertical_alignment="center")
    with head:
        regions = region_text(str(condition["region"]).split("·"))
        certificates = ", ".join(condition.get("certificates") or []) or "자격증 없음"
        st.markdown(f'<div class="radar-title">내 조건에 맞는 공고</div>'
                    f'<div class="m-cond-line">{escape(tracks)} · {escape(regions)} · {escape(certificates)}</div>',
                    unsafe_allow_html=True)
    with button:
        if st.button("조건 바꾸기", type="secondary", use_container_width=True):
            st.switch_page(CONDITIONS_PAGE)

    counts = {key: sum(1 for item in matched if item.status == key) for key in ("eligible", "ambiguous", "ineligible")}
    # '내 지역 16건'과 '다른 지역 8건'을 나눠 씀 (화면 정리 메모 2번: '전기 직렬 공고 16건' 아래에 8건이 더 나와 헷갈림)
    cells = [("내 지역", f"{len(matched)}건", "t-total"), ("접수 중", str(len(open_now)), "t-open"),
             ("조건 맞음", str(counts["eligible"]), "t-eligible"), ("애매", str(counts["ambiguous"]), "t-ambiguous"),
             ("안 맞음", str(counts["ineligible"]), "t-ineligible")]
    st.markdown('<div class="sumrow">' + "".join(
        f'<span class="sum {css}">{escape(label)} <b>{escape(value)}</b></span>' for label, value, css in cells)
        + (f'<span class="sum-more">+ 다른 지역 {len(other_region)}건 (아래)</span>' if other_region else "") + "</div>",
        unsafe_allow_html=True)
    st.markdown(f'<div class="m-summary-hidden">{escape(tracks)} 직렬 공고 <b>{len(matched)}</b>건 · '
                f'지금 접수 중 <b>{len(open_now)}</b>건</div>', unsafe_allow_html=True)
    st.caption("합격 가능성이 아니라 공고에 적힌 지원 조건과 내 조건을 비교한 결과예요. 확정할 수 없으면 '애매'로 표시해요.")

    _list_head("지금 접수 중", len(open_now), "마감 빠른 순")
    if not open_now:
        st.markdown('<div class="m-empty">지금 접수 중인 공고는 없어요. 아래 지난 공고로 다음 채용을 준비해 보세요.</div>',
                    unsafe_allow_html=True)
    _list(open_now, reports, "open", open_cards=True)
    if past:
        _list_head("지난 공고", len(past), "다음 채용 대비")
        _list(past, reports, "past", first=3, more_label="지난 공고")
    if other_region:
        _list_head("희망 지역에 근무지가 없는 공고", len(other_region), "직렬은 맞지만 근무지역이 달라요")
        _list(other_region, reports, "region", first=3, more_label="다른 지역 공고")
    if no_track:
        st.markdown(f'<div class="m-empty m-notrack">{escape(tracks)} 직렬을 뽑지 않는 공고: '
                    + escape(", ".join(item.institution for item in no_track))
                    + ' · ‘공고 비교’ 메뉴에서는 어느 기관이든 볼 수 있어요.</div>', unsafe_allow_html=True)

    st.markdown('<div class="m-foot"></div>', unsafe_allow_html=True)
    note, pdf = st.columns([3, 1.2], vertical_alignment="center")
    with note:
        st.caption(DATA_NOTICE)
    with pdf:
        first = UserCondition(condition["track"], str(condition["region"]), tuple(condition.get("certificates") or ()))
        _pdf_button(first, reports, matched, other_region, no_track)
    skipped = collection_skipped()
    if skipped:
        with st.expander(f"공고를 모으지 못한 기관 {len(skipped)}곳"):
            for row in skipped:
                st.markdown(f"- {row['institution']}: {md_text(row.get('reason') or '사유 없음')}")


if __name__ == "__main__":
    render_matches_page()
