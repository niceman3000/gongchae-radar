import json

import pytest

from src.ai_pipeline import (
    AiPipelineError,
    classify_text_changes,
    extract_notice,
    parse_json_response,
)
from src.model_client import ModelResponse


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.usage = []

    def complete(self, *, model, system, user, max_tokens):
        return ModelResponse(
            text=self.responses.pop(0),
            model=model,
            input_tokens=10,
            output_tokens=5,
            elapsed_seconds=0.01,
        )


def bundle():
    return {
        "sent_pages": [2],
        "pages": [{"page": 2, "text": "배전 전체 10명", "tables": ""}],
        "all_text": {"2": "배전 전체 10명"},
    }


def test_extract_notice_accepts_json_and_verifies_quote_against_page():
    payload = {
        "units": [
            {
                "unit_name": "배전",
                "track": "전기",
                "headcount_total": {
                    "value": 10,
                    "evidence": {"page": 2, "quote": "배전 전체 10명"},
                },
                "headcount_by_region": [],
                "required_qualifications": [],
                "certificate_bonus": [],
                "stages": [],
            }
        ],
        "notice_level": {"schedule": [], "advance_notices": []},
    }
    client = FakeClient([json.dumps(payload, ensure_ascii=False)])

    result = extract_notice(bundle(), client)

    evidence = result["units"][0]["headcount_total"]["evidence"]
    assert evidence["verified"] is True
    assert evidence["verification"] == "쪽 일치"
    assert result["_meta"]["evidence_check"] == {"verified": 1}


def test_extract_notice_keeps_unmatched_ai_quote_rejected():
    payload = {
        "units": [
            {
                "unit_name": "배전",
                "headcount_total": {
                    "value": 99,
                    "evidence": {"page": 2, "quote": "배전 전체 99명"},
                },
            }
        ]
    }
    result = extract_notice(bundle(), FakeClient([json.dumps(payload, ensure_ascii=False)]))

    evidence = result["units"][0]["headcount_total"]["evidence"]
    assert evidence["verified"] is False
    assert result["_meta"]["evidence_check"] == {"rejected": 1}


def test_classification_merges_only_valid_ids_and_labels():
    changes = [
        {"field": "전형방법", "type": "text", "prev": "장애인", "curr": "장애인 및 보훈"},
        {"field": "채용인원", "type": "number", "prev": 10, "curr": 20},
    ]
    response = json.dumps(
        [
            {
                "id": 0,
                "label": "실질 변경",
                "who_is_affected": "보훈 지원자",
                "one_line": "보훈 지원자도 서류를 통과합니다.",
                "confidence": "높음",
            }
        ],
        ensure_ascii=False,
    )

    result = classify_text_changes(changes, FakeClient([response]))

    assert len(result) == 1
    assert result[0]["field"] == "전형방법"
    assert result[0]["prev"] == "장애인"


def test_parse_json_response_rejects_non_json_text():
    with pytest.raises(AiPipelineError):
        parse_json_response("결과를 만들지 못했습니다.", dict)
