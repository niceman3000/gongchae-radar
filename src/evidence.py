"""공고문 쪽수·인용 검증과 확정 변경점 표시 규칙."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping


def _compact(value: Any) -> str:
    """PDF 표·줄바꿈 차이를 허용하되 글자와 문장부호는 그대로 비교한다."""
    return re.sub(r"\s+", "", str(value or ""))


def check_evidence(
    evidence: Mapping[str, Any], all_text: Mapping[str, str]
) -> tuple[bool, str]:
    """Evidence의 인용문이 지정한 쪽에 존재하는지 확인한다."""
    page = evidence.get("page")
    quote = str(evidence.get("quote") or "").strip()

    if not isinstance(page, int) or page < 1:
        return False, "쪽수는 1 이상의 정수여야 합니다."
    if not quote:
        return False, "원문 인용이 비어 있습니다."

    page_text = all_text.get(str(page))
    if page_text is None:
        return False, f"{page}쪽 추출 텍스트가 없습니다."
    if _compact(quote) not in _compact(page_text):
        return False, f"인용문이 {page}쪽 원문에 없습니다."
    return True, "쪽 일치"


def verify_evidence(
    evidence: Mapping[str, Any], all_text: Mapping[str, str]
) -> dict[str, Any]:
    """입력을 변경하지 않고 계약에 맞는 verified 값을 넣은 사본을 반환한다."""
    checked = deepcopy(dict(evidence))
    valid, _ = check_evidence(checked, all_text)
    checked["verified"] = valid
    return checked


def can_confirm_change(change: Mapping[str, Any]) -> bool:
    """표시할 값이 있는 각 연도에 검증된 근거가 있는지 판정한다."""
    required_sides = set()
    if change.get("prev_value") is not None:
        required_sides.add("prev")
    if change.get("curr_value") is not None:
        required_sides.add("curr")
    if not required_sides:
        return False

    verified_sides = {
        item.get("side")
        for item in change.get("evidence") or []
        if item.get("verified") is True
    }
    return required_sides.issubset(verified_sides)


def validate_report_semantics(report: Mapping[str, Any]) -> list[str]:
    """JSON Schema 밖의 교차 필드 규칙을 검사한다."""
    errors: list[str] = []
    prev_sn = str((report.get("prev") or {}).get("sn") or "")
    curr_sn = str((report.get("curr") or {}).get("sn") or "")
    seen_ids: set[str] = set()

    for index, change in enumerate(report.get("changes") or []):
        change_id = str(change.get("id") or f"index-{index}")
        if change_id in seen_ids:
            errors.append(f"중복 change id: {change_id}")
        seen_ids.add(change_id)

        for item in change.get("evidence") or []:
            side = item.get("side")
            expected_sn = prev_sn if side == "prev" else curr_sn if side == "curr" else None
            if expected_sn is None:
                errors.append(f"{change_id}: evidence side가 올바르지 않습니다.")
            elif str(item.get("notice_sn")) != expected_sn:
                errors.append(f"{change_id}: {side} evidence의 공고번호가 다릅니다.")

        if change.get("status") == "confirmed" and not can_confirm_change(change):
            errors.append(f"{change_id}: confirmed에 필요한 양쪽 검증 근거가 없습니다.")

    return errors
