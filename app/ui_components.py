"""공채레이더 Streamlit 화면의 공통 표시 요소."""

from __future__ import annotations

from difflib import SequenceMatcher
import json
from html import escape
import re
from typing import Any, Mapping

import streamlit as st

from src.notice_text import describe_change, is_list_like, item_diff, list_section, number_diff


STATUS_LABELS = {
    "confirmed": "원문 확인",
    "review_required": "원문 확인 권장",
    "not_published": "기관 미공시",
}

# 11-19: 30곳을 같은 자동 과정으로 보여주기로 해서 손으로 쓴 제목(아래 두 표)은 화면에 쓰지 않는다.
# 핵심 3곳 원문 대조 결과는 evaluation/ground_truth의 정답지로 남아 있다. 다시 쓰려면 True.
USE_CURATED_COPY = False

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

LONG_TEXT_THRESHOLD = 30  # 11-21: 90자 미만 문장도 바뀐 부분 색 표시 (팀원 점검 14번)
IMPORTANCE_LABELS = {1: "중요", 2: "보통", 3: "참고"}
NUMBER_MEANING = {
    "배수": ("서류 통과 인원이 늘어나요 (모집인원 대비 배수가 커짐)", "서류 통과 인원이 줄어요 (모집인원 대비 배수가 작아짐)"),
    "명": ("뽑는 인원이 늘었어요", "뽑는 인원이 줄었어요"),
}


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #FFFFFF; }
        [data-testid="stHeader"] { background: #FFFFFF; }
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
        .status-review_required { color: #3B4656; background: #EEF1F5; }  /* 11-21: 노랑은 '애매' 한 뜻만 (팀원 점검 19번) */
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
            text-decoration: underline; text-underline-offset: .18em;  /* 흑백 인쇄·색약 대비 (11-21) */
        }
        .diff-ellipsis { color: #8791a2; padding: 0 .15rem; }
        .status-eligible { color: #0B6E4C; background: #E3F6EE; }
        .status-ambiguous { color: #8A5300; background: #FFF3D6; }
        .status-ineligible { color: #B02A2A; background: #FCE8E8; }

        /* ---- 11-20 디자인 정리: 글꼴 하나(Pretendard), 바탕 #F3F5F8, 포인트 #2453E6, 판정 3색 ---- */
        @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css");
        html, body, .stApp, .stApp button, .stApp input, .stApp textarea, .stApp select,
        [data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"] {
            font-family: "Pretendard Variable", Pretendard, -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
            letter-spacing: -0.01em;
        }
        .stApp { background: #FFFFFF; }
        [data-testid="stHeader"] { background: rgba(243, 245, 248, 0.9); }
        .block-container { max-width: 960px; padding-top: 3.2rem; }
        h1, h2, h3, h4, h5, h6, [data-testid="stHeading"] * {
            color: #16202E; letter-spacing: -0.025em;
            font-family: "Pretendard Variable", Pretendard, -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif !important;
        }
        h2 { font-size: 1.45rem !important; font-weight: 800 !important; }
        h3 { font-size: 1.2rem !important; font-weight: 800 !important; }
        h4 { font-size: 1.02rem !important; font-weight: 750 !important; margin-top: .6rem; }
        [data-testid="stMarkdownContainer"] ul { margin: .1rem 0 .5rem 0; padding-left: 1.2rem; }
        [data-testid="stMarkdownContainer"] li { margin: .15rem 0; }
        [data-testid="stMarkdownContainer"] li p { margin: 0; }
        [data-testid="stCaptionContainer"] { color: #5B6675; }
        .radar-title { color: #16202E; font-size: 1.85rem; font-weight: 800; line-height: 1.3; letter-spacing: -0.03em; }
        .radar-subtitle { color: #5B6675; font-size: 1rem; margin: .4rem 0 1.4rem 0; }
        .status-badge { font-variant-numeric: tabular-nums; }
        .num { font-variant-numeric: tabular-nums; }
        [data-testid="stVerticalBlockBorderWrapper"] { background: #FFFFFF; }
        [data-testid="stExpander"] details { background: #FFFFFF; }

        /* 첫 화면 소개 */
        .hero { padding: .4rem 0 1.6rem 0; }
        .hero-title { font-size: 2.35rem; font-weight: 800; line-height: 1.22; letter-spacing: -0.04em; color: #16202E; }
        .hero-title .q { display: block; color: #2453E6; }
        .hero-lead { color: #3B4656; font-size: 1.05rem; line-height: 1.7; margin-top: .9rem; max-width: 40rem; }
        .hero-facts { display: flex; flex-wrap: wrap; gap: 1.6rem; margin-top: 1.2rem; color: #5B6675; font-size: .92rem; }
        .hero-facts b { display: block; color: #16202E; font-size: 1.35rem; font-weight: 800; font-variant-numeric: tabular-nums; }
        .form-head { font-size: 1.1rem; font-weight: 750; color: #16202E; margin: .2rem 0 .1rem 0; }
        .privacy-note { color: #5B6675; font-size: .86rem; margin: .1rem 0 .8rem 0; }

        /* 맞춤 공고: 판정 막대 */
        .verdict { background: #FFFFFF; border: 1px solid #E3E8EF; border-radius: 1rem; padding: 1.1rem 1.2rem 1rem 1.2rem; margin: .6rem 0 1.2rem 0; }
        .verdict-head { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; flex-wrap: wrap; }
        .verdict-title { font-size: 1.15rem; font-weight: 800; color: #16202E; }
        .verdict-cond { color: #5B6675; font-size: .9rem; }
        .verdict-bar { display: flex; height: .9rem; border-radius: 999px; overflow: hidden; margin: .85rem 0 .7rem 0; background: #EEF1F5; }
        .verdict-bar span { display: block; height: 100%; }
        .vb-eligible { background: #12A574; } .vb-ambiguous { background: #F2B035; } .vb-ineligible { background: #E5534B; }
        .verdict-legend { display: flex; gap: 1.4rem; flex-wrap: wrap; font-size: .92rem; color: #3B4656; }
        .verdict-legend i { display: inline-block; width: .6rem; height: .6rem; border-radius: 50%; margin-right: .35rem; vertical-align: .05rem; }
        .verdict-legend b { font-variant-numeric: tabular-nums; color: #16202E; margin-left: .2rem; }

        /* 맞춤 공고: 한 줄 요약 */
        .row-top { display: flex; justify-content: space-between; align-items: flex-start; gap: .8rem; }
        .row-inst { font-size: 1.08rem; font-weight: 800; color: #16202E; }
        .row-title { color: #3B4656; font-size: .93rem; margin-top: .1rem; }
        .row-meta { display: flex; flex-wrap: wrap; gap: .45rem; margin-top: .65rem; }
        .chip { display: inline-block; border-radius: .5rem; padding: .22rem .55rem; font-size: .82rem; font-weight: 650; background: #F1F4F8; color: #3B4656; font-variant-numeric: tabular-nums; }
        .chip-bonus { background: #EAF0FF; color: #1D47C4; }
        .row-reason { color: #3B4656; font-size: .92rem; margin-top: .6rem; }
        .row-status { font-size: .85rem; padding: .32rem .7rem; border-radius: .55rem; white-space: nowrap; }
        [data-testid="stMetric"] { background: #FFFFFF; border: 1px solid #E3E8EF; border-radius: .9rem; padding: .8rem 1rem; }
        [data-testid="stMetricValue"] { font-weight: 800; font-variant-numeric: tabular-nums; font-size: 1.7rem; }
        [data-testid="stMetricLabel"] { color: #5B6675; }
        [data-testid="stAlert"] { border-radius: .8rem; }
        .chip-open { background: #E8EEFF; color: #1D47C4; font-weight: 800; }
        .row-status { font-size: .95rem !important; font-weight: 750; }
        .evidence-box { background: #F6F8FB; border: 1px solid #E3E8EF; border-radius: .7rem; padding: .6rem .8rem; margin: 0 0 .9rem 0; }
        .evidence-page { color: #16202E; font-size: .9rem; margin-bottom: .25rem; }
        .evidence-box .evidence-quote { margin: 0; border: 0; background: transparent; padding: 0; color: #3B4656; }
        .stButton button p { font-size: 1rem; font-weight: 700; }
        .block-container { padding-top: 4rem; }
        .section-head { font-size: 1.05rem; font-weight: 800; color: #16202E; margin: 1.6rem 0 .5rem 0; }
        /* ---- 11-21 팀원 예시 1~3: 상자 대신 줄, 구역은 검은 선 + 굵은 제목 ---- */
        [data-testid="stHeader"] { background: #FFFFFF; border-bottom: 1px solid #EEF1F5; }  /* 불투명: 내리면 메뉴 뒤로 글자가 비치던 것 (20번) */
        [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {
            font-family: "Pretendard Variable", Pretendard, -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif !important;
        }
        .m-cond { margin-bottom: .2rem; }
        .m-summary { color: #16202E; font-size: 1rem; margin: .9rem 0 .2rem 0; font-variant-numeric: tabular-nums; }
        .m-summary span { color: #5B6675; }
        .m-head { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem;
                  border-top: 2px solid #16202E; padding-top: .9rem; margin: 2rem 0 .2rem 0; }
        .m-head-title { font-size: 1.25rem; font-weight: 800; color: #16202E; }
        .m-head-count { font-size: 1.25rem; font-weight: 800; color: #2453E6; font-variant-numeric: tabular-nums; }
        .m-head-hint { color: #5B6675; font-size: .88rem; }
        .m-empty { color: #5B6675; font-size: .95rem; margin: .1rem 0 .6rem 0; }
        .m-notrack { margin-top: 1.6rem; }
        .m-row { display: flex; justify-content: space-between; gap: 1rem; border-top: 1px solid #DDE2EA;
                 padding: 1.05rem 0 .35rem 0; }
        .m-inst { font-size: 1.3rem; font-weight: 800; color: #16202E; letter-spacing: -0.02em; }
        .m-sub { color: #5B6675; font-size: .93rem; margin-top: .2rem; font-variant-numeric: tabular-nums; }
        .m-bar { color: #C5CCD6; margin: 0 .5rem; }
        .m-reason { color: #16202E; font-size: 1.02rem; margin-top: .55rem; }
        .m-side { display: flex; flex-direction: column; align-items: flex-end; gap: .55rem; white-space: nowrap; }
        .m-dday { background: #E8EEFF; color: #1D47C4; font-weight: 800; font-size: .88rem; border-radius: .4rem;
                  padding: .18rem .5rem; font-variant-numeric: tabular-nums; }
        .m-closed { color: #5B6675; font-size: .88rem; }
        .m-verdict { font-weight: 800; font-size: 1.02rem; }
        .v-eligible { color: #0B6E4C !important; } .v-ambiguous { color: #8A5300 !important; }
        .v-ineligible { color: #B02A2A !important; } .v-past { color: #3B4656 !important; }
        .m-foot { border-top: 1px solid #DDE2EA; margin-top: 1.6rem; }
        /* 줄 아래 '자세히 보기'는 상자 없이 파란 글자 */
        .m-first { border-top: 0; padding-top: .7rem; }
        [data-testid="stMain"] [data-testid="stExpander"] details { border: 0; background: transparent; }
        [data-testid="stMain"] [data-testid="stExpander"] summary { padding-left: 0; }
        [data-testid="stMain"] [data-testid="stExpander"] details[open] > div { padding-left: 0; padding-right: 0; }
        .d-table th, .d-table td { border-left: 0 !important; border-right: 0 !important; border-top: 0 !important; background: transparent !important; }
        [data-testid="stMain"] [data-testid="stExpander"] summary p { color: #2453E6; font-weight: 700; font-size: .95rem; }
        .d-head { border-top: 2px solid #16202E; padding-top: .75rem; margin: 1.3rem 0 .5rem 0;
                  font-size: 1.08rem; font-weight: 800; color: #16202E; }
        .d-head:first-child { margin-top: .2rem; }
        .d-list { margin: 0 0 .4rem 0; padding-left: 1.15rem; color: #16202E; font-size: 1.02rem; line-height: 1.65; }
        .d-list li { margin: .12rem 0; }
        .d-table { width: 100%; border-collapse: collapse; font-size: .97rem; color: #16202E; margin-bottom: .4rem; }
        .d-table th { text-align: left; color: #5B6675; font-weight: 600; font-size: .88rem;
                      border-bottom: 1px solid #16202E; padding: .45rem .6rem .45rem 0; }
        .d-table td { border-bottom: 1px solid #E3E8EF; padding: .6rem .6rem .6rem 0; vertical-align: top; line-height: 1.55; }
        .d-table td.d-unit, .d-table td.d-page { font-weight: 800; white-space: nowrap; }
        .d-table td[class^="v-"] { font-weight: 750; white-space: nowrap; }
        .d-evidence td:first-child { width: 6.5rem; }
        .stButton button[kind="tertiary"] p { color: #2453E6; font-size: .95rem; font-weight: 700; }
        /* 변경점 (예시 3) */
        .c-row { border-top: 1px solid #DDE2EA; padding-top: 1rem; margin-top: .4rem; }
        .c-tags { display: flex; justify-content: space-between; font-size: .85rem; }
        .c-tag-track { color: #2453E6; font-weight: 800; }
        .c-tag-sep { color: #C5CCD6; margin: 0 .45rem; }
        .c-tag-imp { color: #16202E; font-weight: 800; } .c-tag-low { color: #5B6675; font-weight: 600; }
        .c-check { color: #5B6675; }
        .c-title { font-size: 1.22rem; font-weight: 800; color: #16202E; margin-top: .3rem; letter-spacing: -0.02em; }
        .c-title .up { color: #0B6E4C; } .c-title .down { color: #B02A2A; }
        .c-meaning { color: #3B4656; font-size: 1rem; margin: .3rem 0 .6rem 0; }
        .c-table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: .95rem; }
        .c-table th { background: #F1F4F8 !important; color: #3B4656; text-align: left; font-weight: 700; font-size: .86rem;
                      padding: .5rem .7rem; border: 1px solid #DDE2EA; }
        .c-table td { padding: .65rem .7rem; border: 1px solid #DDE2EA; vertical-align: top; line-height: 1.65;
                      color: #273247; overflow-wrap: anywhere; background: #FFFFFF; }
        .c-legend { color: #5B6675; font-size: .82rem; margin: .35rem 0 .2rem 0; }
        .c-member { font-weight: 750; color: #16202E; margin: .7rem 0 .3rem 0; font-size: .95rem; }
        [data-baseweb="tab-list"] { gap: 1.4rem; border-bottom: 1px solid #DDE2EA; }
        [data-baseweb="tab"] p { font-size: 1.02rem; font-weight: 700; }
        /* ---- 11-21 팀원 2차 점검 8·9번 ---- */
        .hero { padding: .2rem 0 1.2rem 0; }
        .hero-kicker { color: #5B6675; font-size: .95rem; margin-bottom: .55rem; }
        .hero-kicker b { color: #2453E6; font-weight: 800; }
        .c-head { border-top: 2px solid #16202E; padding-top: .8rem; margin: .6rem 0 .5rem 0;
                  font-size: 1.15rem; font-weight: 800; color: #16202E; }
        .ex-label { color: #5B6675; font-size: .9rem; white-space: nowrap; transform: translateY(-.45rem); }
        .privacy-note { color: #5B6675; font-size: .85rem; margin: -.2rem 0 1.6rem 0; }
        .p-label { color: #5B6675; font-size: .88rem; margin: .7rem 0 .35rem 0; }
        .p-box { border: 1px solid #DDE2EA; border-radius: .5rem; padding: .2rem 1rem .7rem 1rem; margin-bottom: .4rem; }
        .p-box .m-row { padding-top: .6rem; }
        .p-box .c-title { margin-top: .6rem; }
        .p-box .c-meaning { margin-bottom: 0; }
        /* 이유는 한 줄, 넘치면 … (문장을 안 바꿔도 줄 높이가 같아짐). 강조는 기관명(굵게)·판정(색) 둘만 */
        .m-main { min-width: 0; flex: 1; }
        .m-sub, .m-reason { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .m-reason { color: #3B4656; font-size: .98rem; margin-top: .4rem; }
        .m-unit { color: #5B6675; font-weight: 400; }
        .m-side { justify-content: flex-start; }
        .m-bar { margin: 0 .45rem; }
        /* ---- 11-21 구조 개편: 화면 2개 ---- */
        .topbar { display: flex; gap: 1.4rem; align-items: baseline; border-bottom: 1px solid #E3E8EF;
                  padding: .2rem 0 .7rem 0; margin: 0 0 1rem 0; font-size: .95rem; }
        .topbar-name { font-weight: 800; color: #16202E; }
        .topbar a { color: #5B6675; text-decoration: none; } .topbar a:hover { color: #2453E6; }
        .s-title { font-size: 1.75rem; margin: .2rem 0 .4rem 0; }
        a.m-link { display: block; color: inherit !important; text-decoration: none !important; }
        a.m-link:hover .m-inst { color: #2453E6; }
        a.m-link:hover .m-row { background: #FAFBFD; }
        .m-hint { color: #5B6675; font-size: .9rem; margin-top: .3rem; }
        .m-hint b { color: #16202E; font-weight: 700; }
        .m-link .m-row { padding-bottom: 1rem; }
        .d-back { display: flex; gap: .9rem; align-items: baseline; font-size: .93rem; }
        .d-back a { color: #2453E6; font-weight: 700; text-decoration: none; }
        .d-back span { color: #5B6675; }
        .d-org { color: #5B6675; font-size: .9rem; margin-top: .8rem; }
        .d-title { font-size: 1.6rem; font-weight: 800; color: #16202E; letter-spacing: -0.03em; line-height: 1.3; margin: .2rem 0 .45rem 0; }
        .d-meta { color: #3B4656; font-size: .95rem; margin-bottom: .9rem; font-variant-numeric: tabular-nums; }
        .d-meta .m-dday { margin: 0 .3rem; }
        .d-closed { color: #5B6675; background: #EEF1F5; border-radius: .4rem; padding: .15rem .45rem; font-size: .85rem; margin: 0 .3rem; }
        a.d-outline { display: block; text-align: center; border: 1px solid #C9D1DC; border-radius: .6rem; padding: .45rem .8rem;
                      color: #16202E !important; text-decoration: none !important; font-weight: 600; font-size: .95rem; }
        a.d-outline:hover { border-color: #2453E6; color: #2453E6 !important; }
        .d-sec { border-top: 2px solid #16202E; padding-top: .85rem; margin: 1.9rem 0 .7rem 0;
                 font-size: 1.2rem; font-weight: 800; color: #16202E; }
        .d-side { font-size: .88rem; font-weight: 400; color: #5B6675; margin-left: .7rem; }
        .d-verdict { font-size: 1.35rem; font-weight: 800; }
        .d-unit-name { color: #16202E; font-size: 1.02rem; font-weight: 700; }
        .d-reason { color: #3B4656; font-size: 1rem; margin: .3rem 0 .5rem 0; }
        .d-page-ref { color: #5B6675; font-size: .9rem; }
        .d-units-head { font-weight: 800; color: #16202E; margin: 1rem 0 .3rem 0; font-size: 1rem; }
        .d-units li { font-size: .95rem; }
        .s-table { width: 100%; border-collapse: separate !important; border-spacing: 0; border: 1px solid #DDE2EA !important; border-radius: .6rem; overflow: hidden; }
        .s-table th, .s-table td { border: 0 !important; border-bottom: 1px solid #EEF1F5 !important; padding: .85rem .9rem !important;
                                   vertical-align: top; background: #FFFFFF !important; text-align: left; }
        .s-table tr:last-child th, .s-table tr:last-child td { border-bottom: 0 !important; }
        .s-table th { width: 7.5rem; font-weight: 800; color: #16202E; font-size: .98rem; }
        .s-state { width: 6.5rem; }
        .s-chip { display: inline-block; font-size: .8rem; font-weight: 700; border-radius: .35rem; padding: .15rem .5rem; white-space: nowrap; }
        .s-same { background: #EEF1F5; color: #3B4656; } .s-changed { background: #E8EEFF; color: #1D47C4; }
        .s-new { background: #E3F6EE; color: #0B6E4C; }
        .s-hard, .s-none { background: #FFFFFF; color: #5B6675; border: 1px solid #C9D1DC; }
        .s-answer { color: #16202E; font-size: 1rem; line-height: 1.55; }
        .s-sub { font-size: .85rem; margin-top: .25rem; color: #5B6675; }
        .s-sub a { color: #2453E6; font-weight: 700; text-decoration: none; }
        .t-table { width: 100%; border-collapse: separate !important; border-spacing: 0; border: 1px solid #DDE2EA !important; border-radius: .6rem; overflow: hidden; table-layout: fixed; }
        .t-table td { border: 0 !important; border-right: 1px solid #EEF1F5 !important; padding: .7rem .8rem !important; background: #FFFFFF !important; }
        .t-table td:last-child { border-right: 0 !important; }
        .t-table td.now { background: #EEF3FF !important; }
        .t-name { color: #5B6675; font-size: .85rem; } .t-date { font-weight: 800; color: #16202E; font-size: 1rem; font-variant-numeric: tabular-nums; }
        @media (max-width: 640px) {
            .t-table, .t-table tr, .t-table td { display: block; width: 100%; }
            .s-table, .s-table tbody { display: block; }
            .s-table tr { display: grid; grid-template-columns: 1fr auto; border-bottom: 1px solid #EEF1F5; }
            .s-table th, .s-table td { border-bottom: 0 !important; width: auto !important; }
            .s-table td:last-child { grid-column: 1 / -1; padding-top: 0 !important; }
            .hero-title { font-size: 1.8rem; }
            .row-top, .m-row { flex-direction: column; }
            .m-side { flex-direction: row; align-items: center; }
        }
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


def _diff_key(token: str) -> str:
    """색칠 전에 같게 볼 차이: 띄어쓰기·쉼표·괄호 같은 기호, 숫자 뒤 '점' ('사무20' = '사무20점')
    11-21 팀원 2차 점검 9번(예시 3): 이런 조각까지 빨강·초록이 생겨서 진짜 바뀐 '전기(배전, 송변전) : 10배수'가 묻힘"""
    if not token.strip() or re.fullmatch(r"[^\w\s]", token):
        return ""
    return re.sub(r"(\d)점$", r"\1", token)


def diff_side_html(previous: str, current: str, side: str) -> str:
    """긴 문장에서 공통 부분은 접고 삭제·추가 구절만 강조한다."""
    previous_tokens = re.findall(r"\s+|[\w]+|[^\w\s]", previous)
    current_tokens = re.findall(r"\s+|[\w]+|[^\w\s]", current)
    previous_keys = [_diff_key(token) for token in previous_tokens]
    current_keys = [_diff_key(token) for token in current_tokens]
    matcher = SequenceMatcher(None, previous_keys, current_keys, autojunk=False)
    own = previous_tokens if side == "prev" else current_tokens
    output: list[str] = []
    for tag, prev_start, prev_end, curr_start, curr_end in matcher.get_opcodes():
        start, end = (prev_start, prev_end) if side == "prev" else (curr_start, curr_end)
        text = "".join(own[start:end])
        keys = (previous_keys if side == "prev" else current_keys)[start:end]
        if tag == "equal":
            output.append(_shorten_equal_text(text))
        elif not text:
            continue
        elif not any(keys):  # 기호·띄어쓰기만 다름 → 색칠 안 함
            output.append(escape(text))
        elif side == "prev":
            output.append(f'<span class="diff-removed">{escape(text)}</span>')
        else:
            output.append(f'<span class="diff-added">{escape(text)}</span>')
    return "".join(output)


def _tidy_list_text(text: str) -> str:
    """"추가: ['배전(보훈)', '배전(일반)']" → "추가: 배전(보훈), 배전(일반)" (11-21 팀원 2차 점검 6번: 프로그램 목록 표기)"""
    def join(match: re.Match[str]) -> str:
        items = [item.strip(" '\"") for item in re.findall(r"'[^']*'|\"[^\"]*\"|[^,]+", match.group(1))]
        items = [item for item in items if item]
        return ", ".join(items[:4]) + (f" 외 {len(items) - 4}개" if len(items) > 4 else "")
    return re.sub(r"\[([^\[\]]*)\]", join, text)


def concise_change_title(
    change: Mapping[str, Any], pair_id: str, notice_info: Mapping[str, Any] | None = None
) -> tuple[str, str]:
    """(카드 제목, 지원자에게 의미 한 줄 또는 None). 의미를 규칙으로 쓸 수 없으면 None → 화면에서 숨김 (11-21)"""
    curated = CHANGE_COPY.get((pair_id, str(change.get("id")))) if USE_CURATED_COPY else None
    if curated:
        return curated

    # 숫자 변경은 숫자 규칙 먼저 (대상 이름 규칙은 '사무 : 50배수, 기술 : 15배수'에서 엉뚱한 대상을 고름, 11-21)
    numbered = number_title(change)
    if numbered:
        return numbered

    described = describe_change(change, notice_info)
    if described:
        return described

    raw_title = _tidy_list_text(str(change["title"]))
    if len(raw_title) <= 80:
        return raw_title, None

    prefix = raw_title.split(":", 1)[0].strip()
    subject = prefix if 1 <= len(prefix) <= 16 else str(change.get("category") or "공고")
    return f"{subject} 문구 변경", None


def _as_int(value: Any) -> int | None:
    text = str(value or "").replace(",", "").strip()
    return int(text) if text.isdigit() else None


def _number_value_diff(prev: str, curr: str) -> tuple[list[str], list[str]]:
    """숫자 값으로 비교한 (빠진 숫자, 생긴 숫자). '사무20' → '사무20점'처럼 단위만 붙은 것은 같은 숫자 (11-21).
    결과에는 원문에 단위가 있으면 붙여 보여 준다 ('15배수')."""
    from collections import Counter

    def values(text: str) -> list[str]:
        return re.findall(r"\d+(?:\.\d+)?", text)

    def with_unit(number: str, text: str) -> str:
        match = re.search(rf"(?<![\d.]){re.escape(number)}\s*(배수|점|명|%|개월)", text)
        return f"{number}{match.group(1)}" if match else number

    gone_counter = Counter(values(prev)) - Counter(values(curr))
    new_counter = Counter(values(curr)) - Counter(values(prev))
    gone = [with_unit(number, prev) for number in gone_counter.elements()]
    new = [with_unit(number, curr) for number in new_counter.elements()]
    return gone, new


def _changed_fragment(prev: str, curr: str, numbers: list[str], added: bool) -> str | None:
    """추가(또는 삭제)된 글자 조각 중 그 숫자가 든 것 ('전기(배전, 송변전) : 10배수,' → '전기(배전, 송변전) 10배수')"""
    a_tokens = re.findall(r"\s+|[\w]+|[^\w\s]", prev)
    b_tokens = re.findall(r"\s+|[\w]+|[^\w\s]", curr)
    matcher = SequenceMatcher(None, a_tokens, b_tokens, autojunk=False)
    for tag, a1, a2, b1, b2 in matcher.get_opcodes():
        piece = "".join(b_tokens[b1:b2] if added else a_tokens[a1:a2])
        if tag == "equal" or not any(re.sub(r"[^\d.]", "", number) in piece for number in numbers):
            continue
        piece = re.sub(r"\s*:\s*", " ", piece).strip(" ,/·:;○")
        words = [word for word in re.findall(r"[가-힣A-Za-z]{2,}", piece) if word not in {"배수", "또는", "이상", "이하", "및"}]
        clean = (re.match(r"[\w\[(]", piece) and not re.search(r"(또는|및|~|\()$", piece)
                 and not re.match(r"(또는|및)\b", piece) and piece.count("(") == piece.count(")"))
        if 3 <= len(piece) <= 30 and words and clean:
            return piece
    return None


def _multiples(text: str) -> dict[str, str]:
    """'사무 : 50배수, 전기(배전, 송변전) : 10배수' → {'사무': '50', '전기(배전, 송변전)': '10'} (괄호 안 쉼표는 안 끊음)"""
    pairs: dict[str, str] = {}
    for match in re.finditer(r"([^:]*?)\s*:\s*(\d+)\s*배수", text):
        head, depth, start = match.group(1), 0, 0
        for index, char in enumerate(head):
            depth += char == "("
            depth -= char == ")"
            if depth == 0 and char in ",/○":
                start = index + 1
        subject = head[start:].strip()
        if subject:
            pairs[subject] = match.group(2)
    return pairs


def _fragment_meaning(prev: str, curr: str, fragment: str, numbers: list[str], added: bool) -> str | None:
    """'전기(배전, 송변전) 10배수 신설' → '작년엔 기술 분야 전체가 15배수였는데, 올해 전기(배전, 송변전)는 10배수예요.'
    (11-21 팀원 2차 점검 6번: '새 기준이 생겼어요'는 두루뭉술). 배수가 아니거나 짝을 못 찾으면 None → 숨김"""
    if not added or "배수" not in fragment:
        return None
    before, after = _multiples(prev), _multiples(curr)
    gone = [(subject, number) for subject, number in before.items() if subject not in after]
    target = next((subject for subject in after if subject in fragment), None)
    if not (gone and target):
        return None
    subject, number = gone[0]
    new_number = after[target]
    trend = "줄었어요" if int(new_number) < int(number) else "늘었어요" if int(new_number) > int(number) else "같아요"
    return f"작년엔 {subject} 분야 전체가 {number}배수였는데, 올해 {target}는 {new_number}배수로 {trend}."


def number_title(change: Mapping[str, Any]) -> tuple[str, str | None] | None:
    """숫자가 바뀐 카드: '421명 → 490명 (+69명)', '15배수 → 10배수' + 규칙으로 쓴 의미 한 줄 (11-21 팀원 점검 6·15번)"""
    if change.get("change_type") != "number":
        return None
    category = str(change.get("category") or "")
    prev, curr = change.get("prev_value"), change.get("curr_value")
    before, after = _as_int(prev), _as_int(curr)
    if before is not None and after is not None:
        unit = "명" if category == "인원" else ""
        delta = after - before
        meaning = NUMBER_MEANING["명"][0 if delta > 0 else 1] if unit == "명" else None
        return (f"{category or '숫자'}: {before:,}{unit} → {after:,}{unit} ({delta:+,}{unit})",
                f"{meaning} ({abs(delta):,}명)" if meaning else None)
    if not isinstance(prev, str) or not isinstance(curr, str):
        return None
    gone, new = _number_value_diff(prev, curr)
    if not gone and not new or len(gone) > 3 or len(new) > 3:
        return None
    if any(value.replace(".", "").isdigit() for value in gone + new):  # 단위 없는 숫자(날짜·번호)가 섞이면 숫자 제목을 쓰지 않음
        return None
    label = {"전형": "전형 기준", "가점": "가점"}.get(category, category or "숫자")
    title = f"{label}: {', '.join(gone) or '없음'} → {', '.join(new) or '없음'}"
    fragment = _changed_fragment(prev, curr, new or gone, added=bool(new))
    if fragment and not (gone and new):  # 한쪽에만 있는 숫자: 바뀐 조각으로 제목 (11-21 팀원 점검 13번 '전기(배전, 송변전) 10배수 신설')
        return f"{fragment} {'신설' if new else '없어짐'}", _fragment_meaning(prev, curr, fragment, new or gone, bool(new))
    units = {re.sub(r"[\d.\s]", "", value) for value in gone + new}
    meaning = None
    if units == {"배수"} and gone and new:
        smaller = min(float(re.sub(r"[^\d.]", "", value)) for value in new) < min(
            float(re.sub(r"[^\d.]", "", value)) for value in gone)
        meaning = NUMBER_MEANING["배수"][1 if smaller else 0] + ". 어느 직렬에 해당하는지는 아래 표시를 보세요."
    elif units == {"점"} and category == "자격" and len(gone) == len(new):
        values = [(float(re.sub(r"[^\d.]", "", a)), float(re.sub(r"[^\d.]", "", b))) for a, b in zip(gone, new)]
        if all(b < a for a, b in values):
            meaning = "기준 점수가 낮아졌어요. 어떤 시험의 기준인지는 아래 표시를 보세요."
        elif all(b > a for a, b in values):
            meaning = "기준 점수가 높아졌어요. 어떤 시험의 기준인지는 아래 표시를 보세요."
    elif units == {"%"} and category == "가점" and len(gone) == len(new) == 1:
        before_value, after_value = (float(value.rstrip("%")) for value in (gone[0], new[0]))
        meaning = "가점 비율이 커졌어요." if after_value > before_value else "가점 비율이 작아졌어요."
    elif units == {"점"} and category in {"전형", "가점"}:
        meaning = "배점이 바뀌었어요. 어느 항목의 배점인지는 아래 표시를 보세요."
    return title, meaning


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
    """근거 한 개 = 상자 하나: 첫 줄에 굵은 쪽수, 그 아래 인용 (11-21 팀원 점검 18번: 쪽수가 앞 인용에 붙어 보임)"""
    side = str(item["side"])
    year_label = "작년 공고" if side == "prev" else "올해 공고"
    st.markdown(
        f'<div class="evidence-box"><div class="evidence-page"><b>{year_label} {escape(str(item["page"]))}쪽</b>'
        f' · {escape(titles[side])}</div><div class="evidence-quote">“{escape(str(item["quote"]))}”</div></div>',
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
            st.caption(f'{change["category"]} · {IMPORTANCE_LABELS.get(change["importance"], "참고")}')
            if impact:
                st.markdown(f"**지원자에게 의미:** {md_text(impact)}")
        with right:
            status_badge(str(change["status"]))

        _render_values(change)
        _render_evidence(list(change.get("evidence") or []), titles)


def group_title(
    unit: Mapping[str, Any], pair_id: str, notice_info: Mapping[str, Any] | None = None
) -> tuple[str, str]:
    group = unit["group"]
    curated = GROUP_COPY.get((pair_id, str(group["id"]))) if USE_CURATED_COPY else None
    if curated:
        return curated
    described = [describe_change(change, notice_info) for change in unit["changes"]]
    first = next((item[0] for item in described if item), None)
    if first:
        return (
            f'{first} 외 {len(unit["changes"]) - 1}건',
            "같은 변경이 공고 여러 곳에 나뉘어 잡혀 한 장으로 묶었어요. 아래 문구별 차이를 함께 확인하세요.",
        )
    terms = ", ".join(group.get("shared_terms") or [])
    return (
        f'{unit["category"]} 관련 변경 {len(unit["changes"])}건' + (f" · {terms}" if terms else ""),
        "같은 변경이 공고 여러 곳에 나뉘어 잡혀 한 장으로 묶었어요. 아래 문구별 차이를 함께 확인하세요.",
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
                f'{unit["category"]} · {IMPORTANCE_LABELS.get(unit["importance"], "참고")} · 관련 문구 {len(members)}개를 묶음'
            )
            if impact:
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


# ---- 11-21 팀원 예시 3: 변경점은 상자 대신 줄, 작년|올해 두 칸 대비표 ----
PREV_HEAD, CURR_HEAD = "작년 공고 (2025)", "올해 공고 (2026)"
DIFF_LEGEND = ('<div class="c-legend">빨강 + 취소선 = 빠진 글자 · 초록 + 밑줄 = 추가된 글자 '
               '(띄어쓰기·쉼표·괄호, \'20\'↔\'20점\' 같은 단위 차이는 색칠 안 함)</div>')


def _title_html(title: str) -> str:
    """'인원: 421명 → 490명 (+69명)'의 증감을 초록(늘어남)·빨강(줄어듦) 글자로"""
    match = re.search(r"\(([+-])([\d,]+[^)]*)\)$", title)
    if not match:
        return escape(title)
    css = "up" if match.group(1) == "+" else "down"
    return f'{escape(title[:match.start()])}<span class="{css}">({escape(match.group(1) + match.group(2))})</span>'


def _two_column(prev_html: str, curr_html: str) -> str:
    return (f'<table class="c-table"><thead><tr><th>{PREV_HEAD}</th><th>{CURR_HEAD}</th></tr></thead>'
            f"<tbody><tr><td>{prev_html}</td><td>{curr_html}</td></tr></tbody></table>")


def change_values_table(change: Mapping[str, Any]) -> None:
    """바뀐 값 한 쌍을 '작년 공고 | 올해 공고' 표로. 정수만 바뀐 숫자는 제목에 다 있으니 표를 생략"""
    previous, current = change.get("prev_value"), change.get("curr_value")
    if change.get("change_type") == "number" and _as_int(previous) is not None and _as_int(current) is not None:
        return
    if change.get("change_type") == "text" and is_list_like(previous) and is_list_like(current):
        removed, added, same = item_diff(previous, current)
        st.markdown(_two_column(_chips(removed, "removed") or "빠진 항목 없음", _chips(added, "added") or "새 항목 없음"),
                    unsafe_allow_html=True)
        with st.expander(f"그대로인 항목 {same}개와 원문 전체"):
            st.markdown(_two_column(escape(previous), escape(current)), unsafe_allow_html=True)
        return
    if isinstance(previous, str) and isinstance(current, str):
        st.markdown(_two_column(diff_side_html(previous, current, "prev"), diff_side_html(previous, current, "curr")),
                    unsafe_allow_html=True)
        if max(len(previous), len(current)) >= 60:
            with st.expander("원문 전체 비교"):
                st.markdown(_two_column(escape(previous), escape(current)), unsafe_allow_html=True)
        return
    st.markdown(_two_column(escape(display_value(previous)), escape(display_value(current))), unsafe_allow_html=True)


def change_row(
    unit: Mapping[str, Any],
    titles: Mapping[str, str],
    pair_id: str,
    notice_info: Mapping[str, Any] | None = None,
    track: str | None = None,
    first: bool = False,
) -> None:
    """변경 한 건 = 줄 하나: 꼬리표(내 직렬 관련 | 중요) · 굵은 제목 · 의미 한 줄 · 대비표 (예시 3)"""
    members = list(unit["changes"])
    if unit["kind"] == "group":
        title, impact = group_title(unit, pair_id, notice_info)
    else:
        title, impact = concise_change_title(members[0], pair_id, notice_info)
    # 꼬리표는 하나만: 내 직렬 관련이면 그것, 아니면 분류 (11-21 팀원 2차 점검 9번·예시 3)
    tags = ([f'<span class="c-tag-track">내 직렬({escape(track)}) 관련</span>'] if track
            else [f'<span class="c-tag-imp">{escape(str(unit["category"]))}</span>'])
    check = "원문 확인됨" if unit["status"] == "confirmed" else "원문 확인 권장"
    st.markdown(
        f'<div class="c-row{" m-first" if first else ""}"><div class="c-tags"><div>'
        + '<span class="c-tag-sep">|</span>'.join(tags)
        + f'</div><span class="c-check">{check}</span></div>'
        f'<div class="c-title">{_title_html(title)}</div>'
        + (f'<div class="c-meaning">{escape(impact)}</div>' if impact else '<div class="c-meaning"></div>')
        + "</div>",
        unsafe_allow_html=True,
    )
    for index, change in enumerate(members, 1):
        if len(members) > 1:
            st.markdown(f'<div class="c-member">{index}. {escape(_member_label(change, notice_info))}</div>',
                        unsafe_allow_html=True)
        change_values_table(change)
    _render_evidence([item for change in members for item in change.get("evidence") or []], titles)
