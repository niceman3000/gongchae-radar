"""전년도 대비 변경점 상세 화면."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from app.ui_components import apply_styles, change_row, md_text
from src.change_groups import display_units
from app.report_data import DATA_NOTICE, load_reports
from src.report_repository import ReportContractError


ROOT = Path(__file__).resolve().parents[2]


CHANGE_MARK = {"new": "작년에 없던 항목", "changed": "혜택 바뀜", "same": "작년과 같음"}


def _units(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    """화면 카드 단위. 같은 변경을 나눠 잡은 후보는 한 장으로 센다.

    날짜만 바뀐 후보(어학성적 인정 시작일 등)는 매년 바뀌는 값이라 카드에서 빼고
    '이번 공고 한눈에 보기'에서 이번 공고 기준으로 보여준다.
    """
    changes = [change for change in report["changes"] if change.get("change_type") != "date"]
    return display_units(changes, report.get("change_groups"))


def _render_notice_info(report: Mapping[str, Any]) -> None:
    info = report.get("notice_info")
    if not info:
        return

    st.subheader("이번 공고 한눈에 보기")
    st.caption("작년과 달라졌는지와 상관없이, 이번 공고에 지원할 때 챙길 기준을 모았습니다.")
    period = info["period"]
    st.markdown(f"**접수기간:** {period['start']} ~ {period['end']}")

    rules = info.get("rules") or []
    if rules:
        st.markdown("#### 기준일·유효기간")
        st.dataframe(
            pd.DataFrame([{"구분": rule["topic"], "이번 공고 기준": rule["text"]} for rule in rules]),
            hide_index=True,
            use_container_width=True,
        )

    submissions = info.get("submissions") or []
    if submissions:
        st.markdown("#### 제출·입력해야 할 것")
        for item in submissions:
            st.markdown(f"- {md_text(item)}")

    benefits = info.get("benefits") or []
    if benefits:
        new_count = sum(item["change"] == "new" for item in benefits)
        changed_count = sum(item["change"] == "changed" for item in benefits)
        badge = []
        if new_count:
            badge.append(f"작년에 없던 항목 {new_count}개")
        if changed_count:
            badge.append(f"혜택 바뀜 {changed_count}개")
        title = f"우대사항과 혜택 {len(benefits)}개" + (f" · {', '.join(badge)}" if badge else "")
        with st.expander(title):
            rows = []
            for item in benefits:
                benefit = item["benefit"] or "공고문 가점표 참고 (API 문구에 혜택 없음)"
                if item.get("notes"):
                    benefit += " ※ " + " ※ ".join(item["notes"])
                row = {"대상": item["name"], "혜택": benefit, "작년 대비": CHANGE_MARK[item["change"]]}
                if any(entry["section"] for entry in benefits):
                    row = {"구분": item["section"] or "-", **row}
                rows.append(row)
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def _ymd(value: Any) -> str:
    text = str(value or "")
    return f"{text[:4]}.{text[4:6]}.{text[6:]}" if len(text) == 8 and text.isdigit() else text


def _closed(report: Mapping[str, Any]) -> bool:
    from datetime import date

    end = str(report["curr"]["period"]["end"] or "")
    return len(end) == 8 and end.isdigit() and end < date.today().strftime("%Y%m%d")


def _render_header(report: Mapping[str, Any]) -> None:
    institution = escape(str(report["institution"]))
    st.markdown(
        f'<div class="radar-title">{institution} 채용공고 비교</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="radar-subtitle">올해 공고와 작년 공고에서 달라진 내용을 나란히 보여 드려요.</div>',
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        current, previous = st.columns(2)
        with current:
            st.markdown("**올해 공고 (2026)**" + (" · 접수 마감" if _closed(report) else ""))
            st.write(report["curr"]["title"])
            st.caption(
                f"공고번호 {report['curr']['sn']} · 접수 {_ymd(report['curr']['period']['start'])} ~ {_ymd(report['curr']['period']['end'])}"
            )
        with previous:
            st.markdown("**작년 공고 (2025)**")
            st.write(report["prev"]["title"])
            st.caption(
                f"공고번호 {report['prev']['sn']} · 접수 {_ymd(report['prev']['period']['start'])} ~ {_ymd(report['prev']['period']['end'])}"
            )
    st.caption(DATA_NOTICE)



def _render_sources(report: Mapping[str, Any]) -> None:
    st.subheader("공식 공고 원문")
    st.caption("수집할 때 저장한 공식 공고문이에요. 변경 카드의 내용을 여기서 바로 확인할 수 있어요.")

    columns = st.columns(2)
    for column, (label, key) in zip(columns, (("올해 공고 (2026)", "curr"), ("작년 공고 (2025)", "prev"))):
        notice = report[key]
        pdf_path = ROOT / str(notice["pdf_path"])
        with column:
            st.markdown(f"**{label}**")
            if pdf_path.exists():
                st.download_button(
                    "원문 PDF 내려받기",
                    data=pdf_path.read_bytes(),
                    file_name=f"{notice['sn']}.pdf",
                    mime="application/pdf",
                    key=f"download-{notice['sn']}",
                    use_container_width=True,
                )
            else:
                st.caption("이 공고는 원문이 그림·한글 파일이라 PDF를 저장하지 않았어요.")

    selection = st.selectbox(
        "화면에서 바로 볼 공고",
        options=["선택 안 함", "올해 공고 (2026)", "작년 공고 (2025)"],
        index=0,
    )
    selected_key = {
        "올해 공고 (2026)": "curr",
        "작년 공고 (2025)": "prev",
    }.get(selection)
    if selected_key:
        notice = report[selected_key]
        pdf_path = ROOT / str(notice["pdf_path"])
        if pdf_path.exists():
            st.pdf(
                pdf_path,
                height=720,
                key=f"viewer-{notice['sn']}",
                alt=f"{notice['title']} 공식 공고문",
            )
        else:
            st.caption("이 공고는 원문이 그림·한글 파일이라 PDF를 저장하지 않았어요.")


def _render_visual_summary(report: Mapping[str, Any]) -> None:
    summary = report.get("visual_summary")
    if not summary:
        return

    st.subheader("숫자로 보는 핵심 변화")
    st.caption("그래프는 원문 확인이 끝난 수치만 써요. 정확한 문장은 아래 변경사항에서 확인할 수 있습니다.")

    total = summary["total_headcount"]
    total_delta = total["curr"] - total["prev"]
    total_rate = total_delta / total["prev"] * 100 if total["prev"] else 0
    selection = summary.get("selection_multiple")
    if selection:
        total_column, selection_column = st.columns(2)
    else:
        total_column = st.container()
    total_column.metric(
        total["label"],
        f'{total["curr"]:g}{total["unit"]}',
        f'{total_delta:+g}{total["unit"]} ({total_rate:+.1f}%)',
    )
    if selection:
        selection_column.metric(
            selection["label"],
            f'{selection["curr"]:g}{selection["unit"]}',
            f'2025년 {selection["prev"]:g}{selection["unit"]}',
            delta_color="off",
        )

    breakdown = summary.get("headcount_breakdown") or []
    if breakdown:
        st.markdown("#### 전체 선발인원의 구성")
        if summary.get("scope_note"):
            st.caption(summary["scope_note"])
        for year_key, year_label in (("prev", "2025"), ("curr", "2026")):
            detail = ", ".join(
                f'{row["label"]} {row[year_key]:g}명' for row in breakdown
            )
            st.markdown(f'**{year_label}: 총 {total[year_key]:g}명** ({detail})')
        breakdown_rows = [
            {
                "전형": row["label"],
                "2025": row["prev"],
                "2026": row["curr"],
                "증감": row["curr"] - row["prev"],
            }
            for row in breakdown
        ]
        st.dataframe(
            pd.DataFrame(breakdown_rows),
            hide_index=True,
            use_container_width=True,
            column_config={
                "2025": st.column_config.NumberColumn("2025", format="%d명"),
                "2026": st.column_config.NumberColumn("2026", format="%d명"),
                "증감": st.column_config.NumberColumn("증감", format="%+d명"),
            },
        )

    headcount_rows = [
        {
            "직렬": row["label"],
            "2025": row["prev"],
            "2026": row["curr"],
            "증감": row["curr"] - row["prev"],
        }
        for row in summary.get("headcount_by_track") or []
    ]
    if headcount_rows:
        headcount = pd.DataFrame(headcount_rows)
        st.markdown("#### 직렬별 일반전형 채용인원")
        st.bar_chart(
            headcount.set_index("직렬")[["2025", "2026"]],
            horizontal=True,
            stack=False,
            height=390,
        )
        st.dataframe(
            headcount,
            hide_index=True,
            use_container_width=True,
            column_config={
                "2025": st.column_config.NumberColumn("2025", format="%d명"),
                "2026": st.column_config.NumberColumn("2026", format="%d명"),
                "증감": st.column_config.NumberColumn("증감", format="%+d명"),
            },
        )

    interview_weights = summary.get("interview_weights") or []
    if selection and interview_weights:
        multiple_column, interview_column = st.columns(2)
        with multiple_column:
            st.markdown("#### 전기직 서류 선발배수")
            multiples = pd.DataFrame(
                [
                    {"연도": "2025", "선발배수": selection["prev"]},
                    {"연도": "2026", "선발배수": selection["curr"]},
                ]
            ).set_index("연도")
            st.bar_chart(multiples, horizontal=True, height=250)
        with interview_column:
            st.markdown("#### 일반직 면접 배점 구성")
            weights = pd.DataFrame(
                {
                    "연도": ["2025", "2026"],
                    "직무면접": [interview_weights[0]["prev"], interview_weights[0]["curr"]],
                    "경험면접": [interview_weights[1]["prev"], interview_weights[1]["curr"]],
                }
            ).set_index("연도")
            st.bar_chart(weights, horizontal=True, stack=True, height=250)


def _render_ai_usage() -> None:
    with st.expander("AI는 이 서비스에서 어디에 사용되나요?"):
        st.markdown(
            """
- **코드가 하는 일:** 작년·올해 공고 비교, 같은 변경 묶기, 지원 가능·애매·불가 판정, 가점 계산, 인용문이 원문에 있는지 대조
- **AI가 하는 일:** 공고문에서 지원 자격·가점을 정해진 칸에 정리(미리 한 번), 그림 공고의 글자 옮겨 적기(미리 한 번), 공고문 안에서만 질문 답변
- **사람이 하는 일:** 비교할 공고 고르기 규칙, 판정 규칙, 정답지로 정확도 확인

이 비교 화면은 실시간 AI를 부르지 않아요. 지금 보이는 수치와 설명은 미리 저장한 결과이고,
AI가 원문에 없는 조건이나 숫자를 만들어 판정하지 못하게 나눠 두었어요.
"""
        )


def _is_minor(change: Mapping[str, Any]) -> bool:
    """이름·표기만 바뀐 사소한 변경 (숫자 없음, 바뀐 조각이 짧음): 행사·시스템 이름 등 (11-21 팀원 점검 7·13번)"""
    from difflib import SequenceMatcher

    prev, curr = change.get("prev_value"), change.get("curr_value")
    if change.get("change_type") == "rename":
        return True
    if change.get("change_type") != "text" or not isinstance(prev, str) or not isinstance(curr, str):
        return False
    matcher = SequenceMatcher(None, prev, curr, autojunk=False)
    gone = "".join(prev[a:b] for tag, a, b, _, _ in matcher.get_opcodes() if tag in {"delete", "replace"})
    new = "".join(curr[c:d] for tag, _, _, c, d in matcher.get_opcodes() if tag in {"insert", "replace"})
    if any(char.isdigit() for char in gone + new):
        return False
    return 0 < len(gone.strip()) <= 10 and 0 < len(new.strip()) <= 12 and matcher.ratio() >= 0.7


def _mentions_track(unit: Mapping[str, Any], track: str | None) -> bool:
    if not track:
        return False
    texts = [str(change.get(key) or "") for change in unit["changes"] for key in ("prev_value", "curr_value", "title")]
    return any(track in text for text in texts)


def render_report(report: Mapping[str, Any]) -> None:
    apply_styles()
    _render_header(report)

    units = _units(report)
    track = (st.session_state.get("user_condition") or {}).get("track")
    main = [unit for unit in units if not all(_is_minor(change) for change in unit["changes"])]
    minor = [unit for unit in units if unit not in main]
    # 내 직렬 이름이 들어간 변경을 맨 위로 (11-21 팀원 점검 13번)
    main.sort(key=lambda unit: (not _mentions_track(unit, track), unit["importance"]))

    related = [unit for unit in main if _mentions_track(unit, track)]
    total = len(main) + len(minor)
    st.markdown(f'<div class="m-head"><div><span class="m-head-title">작년과 달라진 점</span> '
                f'<span class="m-head-count">{total}</span><span class="m-head-title">건</span></div></div>',
                unsafe_allow_html=True)
    dated = sum(change.get("change_type") == "date" for change in report["changes"])
    st.caption(
        "작년·올해 공고 문구를 코드로 비교해 찾은 후보예요. 중요한 변경은 아래 ‘공식 공고 원문’으로 확인하세요."
        + (f" 날짜만 바뀐 {dated}건은 ‘이번 공고 한눈에 보기’에 있어요." if dated else "")
    )
    if not total:
        st.info("작년 공고와 비교해 찾은 변경 후보가 없어요.")
    else:
        titles = {"prev": report["prev"]["title"], "curr": report["curr"]["title"]}
        pair_id, info = str(report["pair_id"]), report.get("notice_info")
        tabs = ([(f"내 직렬({track}) 관련 {len(related)}", "related")] if related else []) + [(f"전체 {len(main)}", "all")]
        if minor:
            tabs.append((f"사소한 변경 {len(minor)}", "minor"))
        for tab, (_, kind) in zip(st.tabs([label for label, _ in tabs]), tabs):
            with tab:
                if kind == "related":
                    for index, unit in enumerate(related):
                        change_row(unit, titles, pair_id, info, track, first=index == 0)
                elif kind == "all":
                    more_key = f"more-changes-{pair_id}"
                    shown = main if st.session_state.get(more_key) else main[:6]
                    for index, unit in enumerate(shown):
                        change_row(unit, titles, pair_id, info, track if unit in related else None, first=index == 0)
                    if len(main) > len(shown) and st.button(f"나머지 변경 {len(main) - len(shown)}건 보기 ▾",
                                                            key=f"btn-{more_key}", type="tertiary"):
                        st.session_state[more_key] = True
                        st.rerun()
                else:
                    st.caption("행사·시스템 이름처럼 이름·표기만 바뀐 변경이에요.")
                    for index, unit in enumerate(minor):
                        change_row(unit, titles, pair_id, info, first=index == 0)

    _render_visual_summary(report)
    _render_notice_info(report)
    _render_ai_usage()
    _render_sources(report)


def _report_option_label(report: Mapping[str, Any]) -> str:
    units = _units(report)
    confirmed = sum(item["status"] == "confirmed" for item in units)
    review = sum(item["status"] == "review_required" for item in units)
    status = f"확인 {confirmed}건 · 후보 {review}건" if confirmed else f"변경 후보 {review}건"
    category = f"[{report['category']}] " if report.get("category") else ""
    return f'{category}{report["institution"]} · {report["pair_name"]} · {status}'


def render_report_page(pair_id: str = "kepco-2025-2026-h2") -> None:
    try:
        reports, _ = load_reports()
        if not reports:
            raise KeyError("표시할 리포트가 없습니다.")

        reports_by_id = {report["pair_id"]: report for report in reports}
        pair_id = st.session_state.get("selected_pair_id") or pair_id
        default_index = list(reports_by_id).index(pair_id) if pair_id in reports_by_id else 0
        apply_styles()
        if st.session_state.get("user_condition"):
            st.page_link("app/pages/matches.py", label="맞춤 공고 목록으로 돌아가기", icon=":material/arrow_back:")
        selected_pair_id = st.selectbox(
            "지원할 기업과 비교 공고 선택",
            options=list(reports_by_id),
            index=default_index,
            format_func=lambda value: _report_option_label(reports_by_id[value]),
            help="올해 공고와 작년 같은 공고 한 쌍을 골라요.",
        )
        report = reports_by_id[selected_pair_id]
        st.session_state["selected_pair_id"] = selected_pair_id  # ④ 질문 화면이 같은 공고를 연다
        try:  # 화면 하나만 따로 띄울 때(자동 테스트)는 다른 화면 링크가 없어서 건너뛴다
            st.page_link("app/pages/qa.py", label="이 공고에 대해 공고문에 물어보기", icon=":material/forum:")
        except Exception:  # noqa: BLE001 - StreamlitPageNotFoundError
            pass
    except (KeyError, ReportContractError) as exc:
        apply_styles()
        st.error(f"리포트를 열 수 없습니다: {exc}")
        return
    render_report(report)


if __name__ == "__main__":
    render_report_page()
