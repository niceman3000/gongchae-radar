"""④ 근거 질문 (T029): 선택한 공고의 공고문 원문 안에서만 답한다."""

from __future__ import annotations

from html import escape
import json
import os
from pathlib import Path
from typing import Any, Mapping

import streamlit as st

from app.report_data import load_reports
from app.ui_components import apply_styles, md_text
from src.model_client import AnthropicClient
from src.qa_service import NOT_FOUND, NOT_FOUND_DETAIL, GroundedAnswer, ask

ROOT = Path(__file__).resolve().parents[2]
SESSION_LIMIT = 20  # 한 사람이 한 번 접속해서 할 수 있는 AI 질문 수 (비용 보호)
# 시연 공고마다 눌러 본 질문 (11-21 팀원 질문 테스트 6번: 못 고친 버튼은 맞게 답하는 질문으로)
EXAMPLES = ["토익 몇 점 필요해?", "자격증 점수 기준 알려줘", "필기시험 언제야?", "면접은 어떻게 봐?"]
SIDE_LABEL = {"curr": "올해 공고", "prev": "작년 공고"}


@st.cache_data(show_spinner=False)
def _page_text(sn: str) -> dict[str, str] | None:
    path = ROOT / "stage2" / f"bundle_{sn}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("all_text") or None


@st.cache_data(show_spinner=False)
def _text_source(sn: str) -> str:
    """'ocr'이면 그림 공고문을 AI가 옮겨 적은 글자 (tools/ocr_notices.py)"""
    path = ROOT / "stage2" / f"bundle_{sn}.json"
    if not path.exists():
        return ""
    return str(json.loads(path.read_text(encoding="utf-8")).get("source") or "pdf")


def _api_key() -> str:
    if os.environ.get("GONGCHAE_IGNORE_SECRETS") == "1":  # 테스트용: 키를 아예 안 씀 (11-20 시험 중 실제 AI 호출)
        return ""  # 먼저 봐야 함: Streamlit이 secrets.toml 맨 위 칸을 환경변수로도 넣기 때문 (11-21 PC에서만 실패)
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    try:  # 배포(Streamlit Cloud)에서는 Secrets에 넣는다
        secrets = st.secrets
        value = secrets.get("ANTHROPIC_API_KEY")
        if not value:  # '[anthropic]' 같은 칸 안에 넣은 경우도 읽는다
            for section in secrets.values():
                if isinstance(section, Mapping) and section.get("ANTHROPIC_API_KEY"):
                    value = section.get("ANTHROPIC_API_KEY")
                    break
        return str(value or "").strip()
    except Exception as exc:  # noqa: BLE001 - secrets 파일이 없거나 형식 오류면 키 없음
        st.session_state["secrets_problem"] = type(exc).__name__
        return ""


def _secrets_hint() -> str:
    """키가 안 읽힐 때 이유 (키 값은 절대 보여 주지 않고 이름·오류 종류만)"""
    problem = st.session_state.get("secrets_problem")
    if problem:
        return f" · Secrets 읽기 오류: {problem} (형식 확인: ANTHROPIC_API_KEY = \"키\")"
    try:
        names = [str(name) for name in st.secrets.keys()]
    except Exception:  # noqa: BLE001
        names = []
    if names:
        return f" · Secrets에 있는 이름: {', '.join(names)} (ANTHROPIC_API_KEY 이어야 해요)"
    return " · Secrets가 비어 있어요"


def _render_answer(result: GroundedAnswer, report: Mapping[str, Any]) -> None:
    if result.status == "answered":
        st.markdown('<span class="status-badge status-review_required">AI가 생성한 답변</span>', unsafe_allow_html=True)
        st.markdown(md_text(result.answer))
        st.caption("근거 (공고문 원문과 대조를 통과한 인용)")
        for item in result.evidence:
            title = report[item["side"]]["title"]
            st.markdown(f"- **{SIDE_LABEL[item['side']]} {item['page']}쪽** · {md_text(title)}  \n  “{md_text(item['quote'])}”")
    elif result.status == "not_found":
        st.info(f"**{NOT_FOUND}**  \n{NOT_FOUND_DETAIL}")
    elif result.status == "other_institution":
        st.info(result.answer)
    else:
        st.warning(result.answer)
        if result.note:  # 왜 AI 답이 안 나왔는지 (키 없음, 모델 오류 내용 등)
            st.caption(f"사유: {result.note}")
    if result.excerpts and result.status != "answered":
        with st.expander("관련 있어 보이는 공고문 원문", expanded=result.status in {"unavailable", "not_found"}):
            for item in result.excerpts:
                st.markdown(f"**{SIDE_LABEL[item['side']]} {item['page']}쪽**")
                st.text(item["text"])


def render_qa_page() -> None:
    apply_styles()
    st.markdown('<div class="radar-title">공고문에 물어보기</div>', unsafe_allow_html=True)  # 다른 화면과 같은 크기 (20번)
    st.caption("선택한 공고의 공고문 원문 안에서만 답해요. 답을 찾지 못하면 관련 원문을 보여 드려요. "
               "이름·연락처 같은 개인정보는 입력하지 마세요.")
    reports, _ = load_reports()
    if not reports:
        st.error("표시할 공고가 없습니다.")
        return
    by_id = {report["pair_id"]: report for report in reports}
    default = st.session_state.get("selected_pair_id")
    ids = list(by_id)
    pair_id = st.selectbox("질문할 공고", ids, index=ids.index(default) if default in ids else 0,
                           format_func=lambda value: f"{by_id[value]['institution']} · {by_id[value]['curr']['title']}")
    st.session_state["selected_pair_id"] = pair_id
    report = by_id[pair_id]
    render_qa_box(report)


def render_qa_box(report: Mapping[str, Any], examples: list[str] | None = None) -> None:
    """질문 입력·예시 질문·답과 근거 (11-21 구조 개편: 공고 상세 화면 4구역으로도 씀, 공고는 이 공고로 고정)"""
    pair_id = str(report["pair_id"])
    curr_text = _page_text(str(report["curr"]["sn"]))
    prev_text = _page_text(str(report["prev"]["sn"]))
    if not curr_text:
        st.warning("이 공고는 공고문이 그림·스캔 파일이라 원문 질문을 할 수 없어요. ‘공고 비교’ 화면은 그대로 볼 수 있어요.")
        return
    if _text_source(str(report["curr"]["sn"])) == "ocr":
        st.caption("이 공고문은 그림·스캔 파일이라, AI가 그림의 글자를 옮겨 적은 내용을 원문으로 써요. "
                   "숫자·날짜는 공고문 원본으로 한 번 더 확인하세요.")

    if not _api_key():  # 켜져 있을 때는 안내하지 않음 (11-21 팀원 점검 16번)
        st.caption("AI 답변: 꺼짐 (API 키 없음) · 관련 원문 발췌만 보여줘요. "
                   "(PC: 키를 넣은 창에서 실행하거나 `.streamlit/secrets.toml`, 배포: Streamlit Cloud Secrets)"
                   + _secrets_hint())
    st.write("예시 질문")
    columns = st.columns(len(examples or EXAMPLES))
    clicked = False
    for column, example in zip(columns, examples or EXAMPLES):
        if column.button(example, key=f"example-{example}"):
            st.session_state["qa_question"] = example
            clicked = True
    with st.form("qa-form", clear_on_submit=False):
        question = st.text_input("질문", key="qa_question", max_chars=300, placeholder="예: 토익 몇 점 필요해?")
        submitted = st.form_submit_button("물어보기", type="primary")
    submitted = submitted or clicked  # 예시 질문을 누르면 바로 물어본다
    if not submitted or not question.strip():
        return

    answers = st.session_state.setdefault("qa_answers", {})
    cache_key = (pair_id, question.strip())
    if cache_key not in answers:
        used = st.session_state.get("qa_used", 0)
        key = _api_key()
        client = AnthropicClient(key) if key and used < SESSION_LIMIT else None
        try:
            with st.spinner("공고문에서 찾는 중..."):
                names = [str(item["institution"]) for item in load_reports()[0]]
                result = ask(question, curr_text=curr_text, prev_text=prev_text, client=client,
                             selected=str(report["institution"]), institutions=names)
        except ValueError as exc:
            st.error(str(exc))
            return
        if result.model_called:
            st.session_state["qa_used"] = used + 1
        if key and used >= SESSION_LIMIT and result.status == "unavailable":
            result.answer = f"이번 접속에서 AI 질문 {SESSION_LIMIT}회를 다 썼어요. 아래 공고문 원문을 확인해 주세요."
        answers[cache_key] = result
    st.markdown(f"**질문** {escape(question.strip())}")
    _render_answer(answers[cache_key], report)


if __name__ == "__main__":
    render_qa_page()
