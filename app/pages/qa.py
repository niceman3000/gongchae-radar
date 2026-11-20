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
from src.qa_service import NOT_FOUND, GroundedAnswer, ask

ROOT = Path(__file__).resolve().parents[2]
SESSION_LIMIT = 20  # 한 사람이 한 번 접속해서 할 수 있는 AI 질문 수 (비용 보호)
EXAMPLES = ["토익 몇 점 필요해?", "자기소개서는 언제 내?", "전기기사 가점 몇 점이야?", "나이 제한 있어?"]
SIDE_LABEL = {"curr": "올해 공고", "prev": "작년 공고"}


@st.cache_data(show_spinner=False)
def _page_text(sn: str) -> dict[str, str] | None:
    path = ROOT / "stage2" / f"bundle_{sn}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("all_text") or None


def _api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    try:  # 배포(Streamlit Cloud)에서는 Secrets에 넣는다
        return str(st.secrets.get("ANTHROPIC_API_KEY", "")).strip()
    except Exception:  # noqa: BLE001 - secrets 파일이 없으면 키 없음
        return ""


def _render_answer(result: GroundedAnswer, report: Mapping[str, Any]) -> None:
    if result.status == "answered":
        st.markdown('<span class="status-badge status-review_required">AI가 생성한 답변</span>', unsafe_allow_html=True)
        st.markdown(md_text(result.answer))
        st.caption("근거 (공고문 원문과 대조를 통과한 인용)")
        for item in result.evidence:
            title = report[item["side"]]["title"]
            st.markdown(f"- **{SIDE_LABEL[item['side']]} {item['page']}쪽** · {md_text(title)}  \n  “{md_text(item['quote'])}”")
    elif result.status == "not_found":
        st.info(f"**{NOT_FOUND}**  \n이 공고문에서 질문에 대한 내용을 찾지 못했어요. 기관 채용 문의처로 확인해 주세요.")
    else:
        st.warning(result.answer)
        if result.note:  # 왜 AI 답이 안 나왔는지 (키 없음, 모델 오류 내용 등)
            st.caption(f"사유: {result.note}")
    if result.excerpts and result.status != "answered":
        with st.expander("관련 있어 보이는 공고문 원문 발췌", expanded=result.status == "unavailable"):
            for item in result.excerpts:
                st.markdown(f"**{SIDE_LABEL[item['side']]} {item['page']}쪽**")
                st.text(item["text"])


def render_qa_page() -> None:
    apply_styles()
    st.title("공고문에 물어보기")
    st.caption("선택한 공고의 공고문 원문 안에서만 답해요. 공고문에 없는 내용은 ‘공고문에 명시 없음’으로 답해요. "
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
    curr_text = _page_text(str(report["curr"]["sn"]))
    prev_text = _page_text(str(report["prev"]["sn"]))
    if not curr_text:
        st.warning("이 공고는 공고문이 그림·스캔 파일이라 원문 질문을 할 수 없어요. ‘공고 비교’ 화면은 그대로 볼 수 있어요.")
        return

    st.caption("AI 답변: 켜짐 (API 키 있음)" if _api_key() else
               "AI 답변: 꺼짐 (API 키 없음) · 관련 원문 발췌만 보여줘요. 키를 넣은 PowerShell 창에서 "
               "`.venv\\Scripts\\python.exe -m streamlit run streamlit_app.py`로 켜야 해요.")
    st.write("예시 질문")
    columns = st.columns(len(EXAMPLES))
    clicked = False
    for column, example in zip(columns, EXAMPLES):
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
                result = ask(question, curr_text=curr_text, prev_text=prev_text, client=client)
        except ValueError as exc:
            st.error(str(exc))
            return
        if result.model_called:
            st.session_state["qa_used"] = used + 1
        if key and used >= SESSION_LIMIT and result.status == "unavailable":
            result.answer = f"이번 접속에서 AI 질문 {SESSION_LIMIT}회를 다 썼어요. 아래 원문 발췌를 확인해 주세요."
        answers[cache_key] = result
    st.markdown(f"**질문** {escape(question.strip())}")
    _render_answer(answers[cache_key], report)


if __name__ == "__main__":
    render_qa_page()
