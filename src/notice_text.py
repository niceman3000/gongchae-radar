"""공고 문구를 읽기 쉬운 단위로 나누는 규칙 (코드만, AI 호출 없음).

- split_items: "장애인, 취업지원대상자, 체험형인턴 우수인턴" 같은 나열을 항목으로 나눈다.
- subject_and_rest: "1. 취업지원 대상자: 서류전형(면제) …" 를 (대상, 내용)으로 나눈다.
- describe_change: 변경 후보 하나에 "무엇이 어떻게" 바뀌었는지 짧은 제목·설명을 붙인다.
"""

from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher
import re
from typing import Any, Mapping

MARKER = re.compile(r"^\s*(?:[○□■●▢\-*·•※]|\d+\.|\d+\)|[가-하]\.|[가-하]\))\s*")
NUM_UNIT = re.compile(r"\d+(?:\.\d+)?\s*(?:배수|점|명|%|개월)")
SUBJECT_MAX = 30
LIST_MIN_ITEMS = 3
LIST_ITEM_MAX = 45
FRAGMENT_MAX = 30
VAGUE_SUBJECTS = {"기타", "비고", "참고"}

FIELD_NOUN = {"가점": "혜택", "자격": "기준", "전형": "방법", "결격사유": "기준"}
LIST_LABEL = {"가점": "우대 대상", "자격": "응시자격", "전형": "전형 항목", "결격사유": "결격사유"}
FIELD_LABEL = {"가점": "우대사항", "자격": "응시자격", "전형": "전형방법", "결격사유": "결격사유"}


def strip_marker(text: str) -> str:
    """앞쪽 기호·번호('○', '1.', '- ', '가.')를 뗀다. 여러 겹이면 모두 뗀다."""
    previous = None
    text = text.strip()
    while previous != text:
        previous = text
        text = MARKER.sub("", text, count=1).strip()
    return text


def split_items(text: str) -> list[str]:
    """괄호 밖 쉼표로 나눈 항목. '장애인, 취업지원대상자' → ['장애인', '취업지원대상자']"""
    items, depth, current = [], 0, []
    for char in strip_marker(text):
        if char in "([{（「":
            depth += 1
        elif char in ")]}）」" and depth:
            depth -= 1
        if char in ",，" and depth == 0:
            items.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    items.append("".join(current).strip())
    return [item for item in items if item]


def normalize_name(text: str) -> str:
    return re.sub(r"[^\w]", "", text or "").replace("_", "")


def is_list_like(text: Any) -> bool:
    """짧은 이름을 쉼표로 늘어놓은 문구인지. 쉼표가 든 긴 문장은 나열로 보지 않는다."""
    if not isinstance(text, str) or ":" in text:
        return False
    items = split_items(text)
    return len(items) >= LIST_MIN_ITEMS and max(len(item) for item in items) <= LIST_ITEM_MAX


def changed_fragments(prev: str, curr: str) -> tuple[list[str], list[str]]:
    """두 문장에서 빠진 조각, 생긴 조각 (낱말 단위)."""
    a = re.findall(r"\w+|[^\w\s]", prev or "")
    b = re.findall(r"\w+|[^\w\s]", curr or "")
    gone, new = [], []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in {"delete", "replace"}:
            gone.append(_join(a[i1:i2]))
        if tag in {"insert", "replace"}:
            new.append(_join(b[j1:j2]))
    return [item for item in gone if item], [item for item in new if item]


def _join(tokens: list[str]) -> str:
    text = ""
    for token in tokens:
        if text and re.match(r"\w", token) and re.search(r"\w$", text):
            text += " "
        text += token
    return text.strip(" ,")


def fragment_title(prev: str, curr: str) -> str | None:
    """바뀐 조각이 짧으면 "'A' → 'B'" 형태로 적는다. 길면 None."""
    gone, new = changed_fragments(prev, curr)
    if not gone and not new:
        return None
    if sum(len(item) for item in gone + new) > FRAGMENT_MAX * 2:
        return None
    if gone and new:
        return f"‘{' / '.join(gone)}’ → ‘{' / '.join(new)}’"
    if new:
        return f"‘{' / '.join(new)}’ 추가"
    return f"‘{' / '.join(gone)}’ 삭제"


def subject_and_rest(text: Any) -> tuple[str, str] | None:
    """'대상: 내용' 형식이면 (대상, 내용). 대상이 너무 길면 문장 속 쌍점으로 보고 무시한다."""
    if not isinstance(text, str) or ":" not in text:
        return None
    subject, rest = strip_marker(text).split(":", 1)
    subject = subject.strip()
    if not subject or len(subject) > SUBJECT_MAX or not rest.strip():
        return None
    return subject, rest.strip()


def number_diff(prev: str, curr: str) -> tuple[list[str], list[str]]:
    """이전에만 있는 숫자+단위, 새 공고에만 있는 숫자+단위."""
    a = Counter(re.sub(r"\s+", "", value) for value in NUM_UNIT.findall(prev or ""))
    b = Counter(re.sub(r"\s+", "", value) for value in NUM_UNIT.findall(curr or ""))
    return list((a - b).elements()), list((b - a).elements())


def item_diff(prev: str, curr: str) -> tuple[list[str], list[str], int]:
    """나열 문구의 (빠진 항목, 생긴 항목, 그대로인 항목 수)."""
    prev_items = split_items(prev)
    curr_items = split_items(curr)
    prev_names = {normalize_name(item) for item in prev_items}
    curr_names = {normalize_name(item) for item in curr_items}
    removed = [item for item in prev_items if normalize_name(item) not in curr_names]
    added = [item for item in curr_items if normalize_name(item) not in prev_names]
    same = len(prev_names & curr_names)
    return removed, added, same


def _short(text: str, limit: int = 40) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def list_section(curr: Any, notice_info: Mapping[str, Any] | None) -> str:
    """나열 문구가 우대사항 표의 어느 구분(예: '사회형평, 보훈특별')에 속하는지."""
    if not isinstance(curr, str) or not notice_info:
        return ""
    names = {normalize_name(item) for item in split_items(curr)}
    sections: dict[str, set[str]] = {}
    for item in notice_info.get("benefits") or []:
        sections.setdefault(str(item.get("section") or ""), set()).add(normalize_name(item["name"]))
    for section, members in sections.items():
        if section and members == names:
            return section
    return ""


def describe_change(
    change: Mapping[str, Any], notice_info: Mapping[str, Any] | None = None
) -> tuple[str, str] | None:
    """사람이 문구를 따로 쓰지 않은 후보에 붙일 제목·설명. 규칙에 안 맞으면 None.

    notice_info를 주면 나열 문구가 어느 전형의 목록인지까지 적는다.
    """
    category = str(change.get("category") or "")
    kind = change.get("change_type")
    prev, curr = change.get("prev_value"), change.get("curr_value")

    # 1) 나열 문구에서 항목이 생기거나 빠진 경우: 무엇이 생기고 빠졌는지 이름을 적는다.
    if kind == "text" and is_list_like(prev) and is_list_like(curr):
        removed, added, same = item_diff(prev, curr)
        if removed or added:
            label = LIST_LABEL.get(category, "항목")
            parts = []
            if added:
                parts.append(", ".join(_short(item, 30) for item in added) + " 추가")
            if removed:
                parts.append(", ".join(_short(item, 30) for item in removed) + " 삭제")
            if added and not removed:
                title = f"{label} 추가: " + ", ".join(_short(item, 30) for item in added)
            elif removed and not added:
                title = f"{label} 삭제: " + ", ".join(_short(item, 30) for item in removed)
            else:
                title = f"{label} 변경: " + " · ".join(parts)
            section = list_section(curr, notice_info)
            where = f"{section} 전형" if section and "전형" not in section else section
            if where:
                title = title.replace(f"{label} ", f"{label}({where}) ", 1)
            if category == "가점":
                subject = f"{where}에서 " if where else ""
                impact = f"이 줄은 {subject}가점을 받는 대상 목록이에요. "
                if added:
                    impact += f"2026년에 {', '.join(added)}이(가) 목록에 들어가 해당 지원자도 가점을 받아요. "
                if removed:
                    impact += f"{', '.join(removed)}은(는) 목록에서 빠져 더 이상 가점 대상이 아닙니다. "
                impact += f"나머지 {same}개 대상은 작년과 같아요."
                if added:
                    impact += " 가점 크기는 이 문구에 없어 공고문 가점표를 확인해야 해요."
            else:
                impact = f"나머지 {same}개 항목은 작년과 같아요."
            return title, impact

    # 2) '대상: 내용' 형식: 어느 대상의 무엇이 바뀌었는지 적는다.
    noun = FIELD_NOUN.get(category, "내용")
    pair_prev = subject_and_rest(prev)
    pair_curr = subject_and_rest(curr)
    if kind == "added" and pair_curr:
        subject, rest = pair_curr
        verb = "우대 신설" if category == "가점" else "신설"
        return f"{subject} {verb}", f"2026 {noun}: {rest}"
    if kind == "removed" and pair_prev:
        subject, rest = pair_prev
        verb = "우대 삭제" if category == "가점" else "삭제"
        return f"{subject} {verb}", f"2025에 있던 {noun} '{_short(rest, 60)}'이(가) 2026 공고에서 빠졌어요."
    if kind in {"text", "number"} and pair_prev and pair_curr:
        subject = pair_curr[0]
        if subject in VAGUE_SUBJECTS:
            subject = f"{FIELD_LABEL.get(category, category)}({subject})"
        if normalize_name(pair_prev[0]) != normalize_name(pair_curr[0]):
            # 대상 이름 자체가 바뀜 (예: '자기소개서' → '자기소개서, 직무역량기술서')
            detail = fragment_title(pair_prev[0], pair_curr[0])
            title = f"{subject}: {detail}" if detail else f"{subject} {noun} 변경"
            return title, f"2026 {noun}: {pair_curr[1]}"
        gone, new = number_diff(pair_prev[1], pair_curr[1])
        title = f"{subject} {noun} 변경"
        if gone and new and len(gone) == len(new) <= 2:
            title += f": {', '.join(gone)} → {', '.join(new)}"
        return title, f"2026 {noun}: {pair_curr[1]}"

    # 3) 그 밖의 긴 문장: 바뀐 조각이 짧으면 그 조각을 제목에 적는다.
    if kind == "text" and isinstance(prev, str) and isinstance(curr, str):
        detail = fragment_title(prev, curr)
        if detail:
            label = FIELD_LABEL.get(category, category or "공고")
            return f"{label} 문구: {detail}", "문장 전체는 그대로이고 표시한 부분만 달라졌어요."
    return None
