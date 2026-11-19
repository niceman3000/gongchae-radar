"""이번 공고를 읽기 편하게 정리한 '한눈에 보기' 데이터 (코드만, AI 호출 없음).

작년과의 차이가 아니라 '이번 공고에서 지원자가 챙길 것'을 모은다.
  - period:      접수기간
  - rules:       기준일·유효기간 (어학성적 인정기간, 전역 기한, 졸업예정 기준 등)
  - submissions: 제출·입력해야 하는 것
  - benefits:    우대사항과 혜택. 작년 대비 new / changed / same 표시

날짜만 바뀌는 문구(예: 어학성적 '24.08.07. 이후 응시)는 매년 바뀌므로 변경 카드 대신 여기서
이번 공고 기준으로만 보여준다.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

try:
    from src.diff_stage1 import lines_of
    from src.notice_text import SUBJECT_MAX, is_list_like, normalize_name, split_items, strip_marker, subject_and_rest
except ModuleNotFoundError:  # `python src/report_builder.py` 직접 실행 지원
    from diff_stage1 import lines_of
    from notice_text import SUBJECT_MAX, is_list_like, normalize_name, split_items, strip_marker, subject_and_rest

RULE_FIELDS = ("aplyQlfcCn", "scrnprcdrMthdExpln", "prefCn")
RULE_KEYWORDS = re.compile(
    r"유효|기준일|이후\s*응시|부터\s*응시|전역\s*가능|졸업\s*예정|접수\s*마감일\s*현재|입사\s*예정일|정년"
)
RULE_TOPICS = [
    ("어학성적", re.compile(r"유효성적|어학|외국어|TOEIC|응시하고|입력이 가능한 성적")),
    ("병역", re.compile(r"병역|전역")),
    ("학력", re.compile(r"졸업|학력")),
    ("연령", re.compile(r"정년|연령|만\s*\d+세")),
    ("가점", re.compile(r"가점|수료|확정일|인턴")),
    ("재직", re.compile(r"재직")),
]
SUBMISSION_KEYWORDS = re.compile(r"제출|반드시\s*입력|입력하여야|증빙")
SECTION_HINT = re.compile(r"전형|공통|신입|보훈특별|사회형평")


def _period(item: Mapping[str, Any]) -> dict[str, str]:
    def fmt(value: Any) -> str:
        text = str(value or "")
        return f"{text[:4]}.{text[4:6]}.{text[6:8]}" if re.fullmatch(r"\d{8}", text) else (text or "확인 필요")

    return {"start": fmt(item.get("pbancBgngYmd")), "end": fmt(item.get("pbancEndYmd"))}


def _topic(text: str) -> str:
    for topic, pattern in RULE_TOPICS:
        if pattern.search(text):
            return topic
    return "기타"


def _rules(curr: Mapping[str, Any], extra_lines: Iterable[str]) -> list[dict[str, str]]:
    lines = []
    for field in RULE_FIELDS:
        lines.extend(line for line in lines_of(curr.get(field)) if RULE_KEYWORDS.search(line))
    lines.extend(extra_lines)
    seen, rules = set(), []
    for line in lines:
        text = strip_marker(line)
        key = normalize_name(text)
        if not key or key in seen:
            continue
        seen.add(key)
        rules.append({"topic": _topic(text), "text": text})
    order = {topic: index for index, (topic, _) in enumerate(RULE_TOPICS)}
    rules.sort(key=lambda rule: order.get(rule["topic"], len(order)))
    return rules


def _submissions(curr: Mapping[str, Any]) -> list[str]:
    seen, output = set(), []
    for field in RULE_FIELDS:
        for line in lines_of(curr.get(field)):
            if not SUBMISSION_KEYWORDS.search(line):
                continue
            text = strip_marker(line)
            if normalize_name(text) not in seen:
                seen.add(normalize_name(text))
                output.append(text)
    return output


def parse_benefits(text: Any) -> list[dict[str, Any]]:
    """우대사항 문구를 [{section, name, benefit, notes}]로 나눈다."""
    items: list[dict[str, Any]] = []
    section = ""
    parent: dict[str, Any] | None = None
    for raw in lines_of(text):
        stripped = raw.strip()
        body = strip_marker(stripped)
        if not body:
            continue
        if stripped.startswith(("※", "*")):
            if items:
                items[-1]["notes"].append(body)
            continue
        is_sub = stripped.startswith("-")
        pair = subject_and_rest(body)
        if pair:
            subject, rest = pair
            if is_sub and parent is not None and parent["benefit"] is None:
                parent.setdefault("parts", []).append(f"{subject}: {rest}")
                continue
            parent = {"section": section, "name": subject, "benefit": rest, "notes": []}
            items.append(parent)
            continue
        if is_list_like(body):
            for name in split_items(body):
                items.append({"section": section, "name": name, "benefit": None, "notes": []})
            parent = None
            continue
        if len(body) <= SUBJECT_MAX and SECTION_HINT.search(body) and not is_sub:
            section = body
            parent = None
            continue
        parent = {"section": section, "name": body, "benefit": None, "notes": []}
        items.append(parent)

    for item in items:
        parts = item.pop("parts", None)
        if parts:
            item["benefit"] = " / ".join(parts)
    return items


def _benefits(prev: Mapping[str, Any], curr: Mapping[str, Any]) -> list[dict[str, Any]]:
    previous = {}
    for item in parse_benefits(prev.get("prefCn")):
        previous.setdefault(normalize_name(item["name"]), item)
    output = []
    for item in parse_benefits(curr.get("prefCn")):
        old = previous.get(normalize_name(item["name"]))
        if old is None:
            change = "new"
        elif normalize_name(old.get("benefit") or "") != normalize_name(item.get("benefit") or ""):
            change = "changed"
        else:
            change = "same"
        output.append(
            {
                "section": item["section"],
                "name": item["name"],
                "benefit": item["benefit"],
                "notes": item["notes"],
                "change": change,
                "prev_benefit": (old or {}).get("benefit") if change == "changed" else None,
            }
        )
    return output


def build_notice_info(
    prev: Mapping[str, Any],
    curr: Mapping[str, Any],
    changes: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    date_lines = [
        str(change["curr_value"])
        for change in changes
        if change.get("change_type") == "date" and isinstance(change.get("curr_value"), str)
    ]
    return {
        "period": _period(curr),
        "rules": _rules(curr, date_lines),
        "submissions": _submissions(curr),
        "benefits": _benefits(prev, curr),
    }
