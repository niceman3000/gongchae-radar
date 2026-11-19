"""국가기술자격 이름을 '종목 + 등급'으로 나누고 공고의 인정 목록과 맞춰 본다 (코드만).

예) 전기기사 → (전기, 기사), 전기공사산업기사 → (전기공사, 산업기사),
    소방설비기사(전기) → (소방설비(전기), 기사)

공고 목록은 두 가지 형태로 적는다.
  {"names": ["전기기사", "전기공사기사"]}                      이름을 그대로 나열
  {"items": ["전기", "전기공사"], "grades": ["산업기사", "기사"]}  종목 × 등급 (예: '산업기사 이상')
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

GRADE_RANK = {"기능사": 1, "산업기사": 2, "기사": 3, "기능장": 3, "기술사": 4}
CERT = re.compile(r"^(?P<item>.+?)(?P<grade>기술사|기능장|산업기사|기사|기능사)(?P<paren>\(.+\))?$")

# 입력 화면에서 고를 수 있는 자주 쓰는 자격증. 목록에 없으면 직접 입력할 수 있다.
COMMON_CERTIFICATES = [
    "전기기사", "전기산업기사", "전기기능사", "전기기능장", "전기공사기사", "전기공사산업기사",
    "전자기사", "전자산업기사", "소방설비기사(전기)", "소방설비산업기사(전기)", "산업안전기사",
    "산업안전산업기사", "정보통신기사", "정보처리기사", "신재생에너지발전설비기사(태양광)",
    "발송배전기술사", "전기안전기술사", "일반기계기사", "기계설계산업기사", "에너지관리기사",
    "토목기사", "토목산업기사", "건축기사", "건축산업기사", "수자원개발기사", "건설재료시험기사",
    "측량및지형공간정보기사", "원자력기사", "방사선비파괴검사기사", "RI면허", "화공기사", "대기환경기사",
    "수질환경기사", "위험물산업기사", "정보보안기사", "무선설비기사", "빅데이터분석기사", "SQLD", "ADsP",
]


def normalize(text: str) -> str:
    return re.sub(r"[^\w]", "", text or "").replace("_", "")


def parse(name: str) -> tuple[str, str | None]:
    """자격증 이름 → (종목, 등급). 등급을 알 수 없으면 (이름, None)."""
    compact = re.sub(r"\s+", "", name or "")
    found = CERT.match(compact)
    if not found:
        return normalize(compact), None
    item = found.group("item") + (found.group("paren") or "")
    return normalize(item), found.group("grade")


def matches(name: str, rule: Mapping[str, Any]) -> bool:
    """자격증 하나가 공고의 인정 목록(rule)에 들어가는지."""
    if normalize(name) in {normalize(item) for item in rule.get("names") or []}:
        return True
    item, grade = parse(name)
    if grade is None or not rule.get("items"):
        return False
    return item in {normalize(value) for value in rule["items"]} and grade in set(rule.get("grades") or [])


def keep_highest_grade(names: Iterable[str]) -> list[str]:
    """같은 종목은 상위 등급 1개만 남긴다 (전기기사 + 전기산업기사 → 전기기사)."""
    best: dict[str, tuple[int, str]] = {}
    order: list[str] = []
    for name in names:
        item, grade = parse(name)
        rank = GRADE_RANK.get(grade or "", 0)
        if item not in best:
            order.append(item)
        if item not in best or rank > best[item][0]:
            best[item] = (rank, name)
    return [best[item][1] for item in order]
