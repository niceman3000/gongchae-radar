from src.evidence import (
    can_confirm_change,
    check_evidence,
    validate_report_semantics,
    verify_evidence,
)


def evidence(side="curr", page=2, quote="전기 직렬 10명", verified=False):
    return {
        "side": side,
        "notice_sn": "200" if side == "curr" else "100",
        "page": page,
        "quote": quote,
        "verified": verified,
    }


def test_quote_on_the_declared_page_is_verified_with_whitespace_normalization():
    item = evidence(quote="전기 직렬 10명")
    checked = verify_evidence(item, {"2": "모집분야\n전기  직렬\t10명"})

    assert checked["verified"] is True


def test_quote_on_a_different_page_is_rejected():
    valid, reason = check_evidence(evidence(page=3), {"2": "전기 직렬 10명"})

    assert valid is False
    assert "3쪽" in reason


def test_empty_quote_is_rejected():
    valid, reason = check_evidence(evidence(quote=""), {"2": "전기 직렬 10명"})

    assert valid is False
    assert "인용" in reason


def test_two_sided_change_requires_verified_evidence_for_both_sides():
    change = {
        "prev_value": "15배수",
        "curr_value": "10배수",
        "evidence": [evidence("curr", verified=True)],
    }

    assert can_confirm_change(change) is False

    change["evidence"].append(evidence("prev", verified=True))
    assert can_confirm_change(change) is True


def test_added_change_only_requires_current_evidence():
    change = {
        "prev_value": None,
        "curr_value": "보훈 전형 추가",
        "evidence": [evidence("curr", verified=True)],
    }

    assert can_confirm_change(change) is True


def test_confirmed_change_without_required_evidence_fails_semantic_validation():
    report = {
        "prev": {"sn": "100"},
        "curr": {"sn": "200"},
        "changes": [
            {
                "id": "change-1",
                "status": "confirmed",
                "prev_value": "15배수",
                "curr_value": "10배수",
                "evidence": [evidence("curr", verified=True)],
            }
        ],
    }

    errors = validate_report_semantics(report)

    assert errors
    assert "change-1" in errors[0]
