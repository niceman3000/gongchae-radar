"""근거 질문 서비스 (T027): 근거 있음 · 근거 없음 · 인용 미검증 · API 키 없음 · 모델 오류."""

from __future__ import annotations

import json

import pytest

from src.model_client import ModelClientError, ModelResponse
from src.qa_service import NOT_FOUND, GroundedAnswer, ask, find_passages

CURR = {
    "3": "□ 지원자격\n○ 외국어: TOEIC 700점 이상 (보훈·장애 전형은 제외)\n○ 병역: 남자는 군필 또는 면제자",
    "7": "□ 전형방법\n○ 서류전형: 자기소개서 적부 판정\n○ 필기전형: 직업기초능력 50문항",
}
PREV = {"3": "□ 지원자격\n○ 외국어: TOEIC 650점 이상"}


class FakeClient:
    def __init__(self, payload=None, error=None):
        self.payload, self.error, self.calls = payload, error, 0

    def complete(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return ModelResponse(text=json.dumps(self.payload, ensure_ascii=False), model="fake",
                             input_tokens=100, output_tokens=20, elapsed_seconds=0.1)


def _ask(question, client, prev=None):
    return ask(question, curr_text=CURR, prev_text=prev, client=client)


def test_answer_with_verified_quote_is_answered_and_marked_ai():
    client = FakeClient({"status": "answered", "answer": "TOEIC 700점 이상이 필요합니다.",
                         "evidence": [{"side": "curr", "page": 3, "quote": "외국어: TOEIC 700점 이상"}]})

    result = _ask("토익 몇 점 필요해?", client)

    assert isinstance(result, GroundedAnswer)
    assert result.status == "answered"
    assert result.ai_generated is True
    assert result.evidence == [{"side": "curr", "page": 3, "quote": "외국어: TOEIC 700점 이상", "verified": True}]
    assert client.calls == 1


def test_question_without_matching_text_returns_not_found_without_model_call():
    client = FakeClient({"status": "answered", "answer": "지어낸 답", "evidence": []})

    result = _ask("기숙사 제공돼?", client)

    assert result.status == "not_found"
    assert result.answer == NOT_FOUND
    assert result.ai_generated is False
    assert client.calls == 0  # 관련 원문이 없으면 돈을 쓰지 않는다


def test_answer_whose_quotes_are_not_in_pdf_becomes_not_found():
    client = FakeClient({"status": "answered", "answer": "TOEIC 800점 이상입니다.",
                         "evidence": [{"side": "curr", "page": 3, "quote": "TOEIC 800점 이상"}]})

    result = _ask("토익 몇 점 필요해?", client)

    assert result.status == "not_found"
    assert result.answer == NOT_FOUND
    assert result.evidence == []


def test_model_saying_not_found_is_not_found():
    client = FakeClient({"status": "not_found", "answer": NOT_FOUND, "evidence": []})

    result = _ask("토익 유효기간은 언제까지 인정돼?", client)

    assert result.status == "not_found"
    assert result.answer == NOT_FOUND


def test_no_api_key_is_unavailable_with_original_excerpts():
    result = _ask("토익 몇 점 필요해?", None)

    assert result.status == "unavailable"
    assert result.ai_generated is False
    assert any(item["page"] == 3 and "TOEIC 700점" in item["text"] for item in result.excerpts)


def test_model_error_is_unavailable_with_original_excerpts():
    result = _ask("토익 몇 점 필요해?", FakeClient(error=ModelClientError("모델 API 오류 529")))

    assert result.status == "unavailable"
    assert result.excerpts


def test_last_year_words_include_last_year_notice():
    passages = find_passages("작년이랑 토익 기준 달라졌어?", CURR, PREV)

    assert {item["side"] for item in passages} == {"curr", "prev"}


def test_personal_information_in_question_is_rejected():
    with pytest.raises(ValueError):
        _ask("010-1234-5678 로 연락 주세요. 토익 몇 점?", FakeClient())


def test_attached_words_and_everyday_words_find_notice_text():
    """11-19: '토익점수'처럼 붙여 쓰면 TOEIC 줄을 못 찾아 AI 없이 '명시 없음'이 나왔음."""
    assert any(item["page"] == 3 for item in find_passages("토익점수 필요해?", CURR))
    assert any(item["page"] == 3 for item in find_passages("영어 성적 몇 점?", CURR))


# ---- 11-21 팀원 질문 테스트 (동서발전 11문항) 회귀 ----
import json as _json
from pathlib import Path as _Path

from src.qa_service import ask as _qa_ask, find_passages as _find, other_institution as _other

_DONGSEO = _json.loads((_Path(__file__).resolve().parents[2] / "stage2" / "bundle_307149.json")
                       .read_text(encoding="utf-8"))["all_text"]


def test_dongseo_table_pages_have_the_answers() -> None:
    """공고문 글자에 표 내용이 있다 (17쪽 '기사 10', 9쪽 '2026. 12. 19.', 7쪽 '필기 전형 만점의 5%')"""
    assert "기사 10" in _DONGSEO["17"]
    assert "2026. 12. 19." in _DONGSEO["9"]
    assert "필기 전형 만점의 5%" in _DONGSEO["7"]


def test_table_pages_are_always_candidates() -> None:
    """질문 종류가 맞으면 표 쪽 전체를 근거 후보로 (전에는 낱말 몇 개로만 골라 표 쪽을 놓침)"""
    pages = lambda question: [item["page"] for item in _find(question, _DONGSEO)]
    assert 17 in pages("전기기사 가점 몇 점이야?")
    assert 17 in pages("전기기사랑 전기공사기사 둘 다 인정돼?")
    assert 9 in pages("필기 과목이랑 날짜, 장소 알려줘") and 4 in pages("필기 과목이랑 날짜, 장소 알려줘")
    assert 4 in pages("면접 몇 번 봐?")
    assert {4, 9} <= set(pages("서류 합격 발표 언제야? 몇 배수?"))
    assert 7 in pages("동서발전 청년인턴 했는데 가점 있어?")
    assert 6 in pages("부산에서 대학 나왔는데 지역인재 우대 돼?")


def test_other_institution_in_question_is_not_answered() -> None:
    """동서발전을 고르고 '한전은 토익 몇 점이야?' → 답하지 않고 안내"""
    names = ["한국동서발전", "한국전력공사", "한전KPS"]
    assert _other("한전은 토익 몇 점이야?", "한국동서발전", names) == "한국전력공사"
    assert _other("동서발전 청년인턴 했는데 가점 있어?", "한국동서발전", names) is None
    assert _other("한전KPS 토익?", "한전KPS", names) is None
    result = _qa_ask("한전은 토익 몇 점이야?", curr_text=_DONGSEO, selected="한국동서발전", institutions=names)
    assert result.status == "other_institution" and not result.model_called
    assert "지금 선택한 공고는 한국동서발전이에요" in result.answer
