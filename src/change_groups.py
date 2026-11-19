"""한 가지 변경이 여러 문장에 나뉘어 잡힌 후보를 묶는다 (코드만, AI 호출 없음).

1단계는 문장을 한 줄씩 비교하므로 "자기소개서 적부평가 폐지" 같은 변경 하나가
'사전평가 문구 변경', '자기소개서 적격자만 필기시험 삭제', '사전평가 면제 추가'처럼
여러 후보로 쪼개질 수 있다.

규칙
  1. 같은 카테고리(전형·자격·가점 등) 안에서만 묶는다.
  2. 후보마다 '바뀐 낱말'을 구한다.
       문구 변경: 이전에만 있는 낱말 + 새 공고에만 있는 낱말
       추가·삭제: 그 줄의 모든 낱말
  3. 두 후보의 바뀐 낱말이 다음 중 하나를 만족하면 같은 묶음이다.
       - 3글자 이상 핵심어를 1개 이상 공유 (예: 자기소개서, 사전평가)
       - 2글자 핵심어를 2개 이상 공유 (예: 보훈 + 장애)
  4. '경우', '적용', '전형'처럼 어디에나 나오는 낱말은 핵심어에서 뺀다.

묶음은 변경점 id를 바꾸지 않는다. 사람이 확인한 근거(evaluation/ground_truth)는
기존 id에 그대로 연결되고, 화면만 묶음을 카드 한 장으로 보여준다.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

WORD = re.compile(r"[가-힣A-Za-z]+")
# 낱말 끝 조사. '평가'의 '가'처럼 낱말 일부를 자르지 않도록 '이·가'는 넣지 않는다.
PARTICLES = ("에서", "으로", "에게", "부터", "까지", "에", "의", "을", "를", "은", "는", "로", "과", "와", "도", "만")
STOPWORDS = {
    "단", "및", "등", "또는", "경우", "해당", "해당자", "시행", "적용", "가능", "불가", "이상", "이하",
    "미만", "초과", "대상", "대상자", "인원", "지원", "지원자", "전형", "채용", "모집", "기준", "관련",
    "사항", "포함", "제외", "이후", "이전", "까지", "부터", "한해", "한함", "있는", "없는", "하는",
    "한하여", "따라", "따른", "통해", "위한", "대한", "기타", "내용", "확인", "자", "시", "차", "점",
    "명", "년", "월", "일", "년도", "제", "중", "후", "전", "개", "각", "회",
    # 모집단위 이름에 늘 붙는 말
    "신입", "경력", "대졸수준", "고졸수준", "일반",
}
# 날짜만 바뀐 후보(date)는 변경 카드가 아니라 '이번 공고 한눈에 보기'에 들어가므로 묶지 않는다.
GROUPABLE_TYPES = {"text", "added", "removed", "number", "rename", "list"}


def _strip_particle(word: str) -> str:
    for particle in PARTICLES:
        if word.endswith(particle) and len(word) - len(particle) >= 2:
            return word[: -len(particle)]
    return word


def words_of(value: Any) -> set[str]:
    """문장(또는 목록)을 비교용 낱말 집합으로 바꾼다."""
    if value is None:
        return set()
    if isinstance(value, (list, tuple)):
        text = " ".join(str(item) for item in value)
    else:
        text = str(value)
    return {_strip_particle(word) for word in WORD.findall(text)}


def changed_words(change: Mapping[str, Any]) -> set[str]:
    """이 후보에서 실제로 바뀐 낱말 (핵심어만)."""
    prev = words_of(change.get("prev_value"))
    curr = words_of(change.get("curr_value"))
    if change.get("change_type") in {"added", "removed", "list"}:
        # 추가·삭제는 줄 전체가, 목록은 빠진 항목·생긴 항목 전체가 바뀐 내용이다.
        changed = prev | curr
    else:
        changed = prev ^ curr
    return {word for word in changed if len(word) >= 2 and word not in STOPWORDS}


def related_terms(left: set[str], right: set[str]) -> list[str]:
    """두 후보를 묶을 근거가 되는 공통 핵심어. 묶지 않으면 빈 목록."""
    shared = left & right
    long_terms = sorted(term for term in shared if len(term) >= 3)
    if long_terms:
        return sorted(shared, key=lambda term: (-len(term), term))
    if len(shared) >= 2:
        return sorted(shared)
    return []


def find_change_groups(changes: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """같은 변경을 다른 문장에서 잡은 후보들을 묶음 목록으로 돌려준다.

    반환 형식: [{"id", "category", "member_ids", "shared_terms"}]
    후보가 1개뿐인 묶음은 만들지 않는다. 순서는 입력 순서를 따른다.
    """
    items = [
        change
        for change in changes
        if change.get("change_type") in GROUPABLE_TYPES and change.get("id")
    ]
    words = {str(change["id"]): changed_words(change) for change in items}

    parent = {str(change["id"]): str(change["id"]) for change in items}

    def root(change_id: str) -> str:
        while parent[change_id] != change_id:
            parent[change_id] = parent[parent[change_id]]
            change_id = parent[change_id]
        return change_id

    links: dict[frozenset[str], list[str]] = {}
    for index, left in enumerate(items):
        for right in items[index + 1 :]:
            if left.get("category") != right.get("category"):
                continue
            left_id, right_id = str(left["id"]), str(right["id"])
            terms = related_terms(words[left_id], words[right_id])
            if terms:
                links[frozenset((left_id, right_id))] = terms
                parent[root(right_id)] = root(left_id)

    members: dict[str, list[str]] = {}
    for change in items:
        change_id = str(change["id"])
        members.setdefault(root(change_id), []).append(change_id)

    category_by_id = {str(change["id"]): str(change.get("category") or "") for change in items}
    groups = []
    for member_ids in members.values():
        if len(member_ids) < 2:
            continue
        shared: list[str] = []
        for pair, terms in links.items():
            if pair <= set(member_ids):
                shared.extend(term for term in terms if term not in shared)
        groups.append(
            {
                "id": "group-" + sorted(member_ids)[0],
                "category": category_by_id[member_ids[0]],
                "member_ids": member_ids,
                "shared_terms": shared[:6],
            }
        )
    return groups


def display_units(
    changes: Iterable[Mapping[str, Any]], groups: Iterable[Mapping[str, Any]] | None
) -> list[dict[str, Any]]:
    """화면에 보여줄 카드 단위. 묶음은 카드 1장, 나머지는 후보 1개가 카드 1장.

    카드 순서는 각 카드의 첫 후보가 원래 목록에서 나온 순서를 따른다.
    묶음은 모든 후보가 원문 확인(confirmed)일 때만 confirmed로 본다.
    """
    change_list = list(changes)
    by_id = {str(change["id"]): change for change in change_list}
    group_of = {}
    for group in groups or []:
        present = [member for member in group["member_ids"] if member in by_id]
        if len(present) >= 2:
            for member in present:
                group_of[member] = (group, present)

    units = []
    emitted = set()
    for change in change_list:
        change_id = str(change["id"])
        if change_id in emitted:
            continue
        if change_id in group_of:
            group, present = group_of[change_id]
            member_changes = [by_id[member] for member in present]
            statuses = {member["status"] for member in member_changes}
            units.append(
                {
                    "kind": "group",
                    "id": group["id"],
                    "group": group,
                    "changes": member_changes,
                    "status": "confirmed" if statuses == {"confirmed"} else "review_required",
                    "importance": min(member["importance"] for member in member_changes),
                    "category": group.get("category") or member_changes[0]["category"],
                }
            )
            emitted.update(present)
        else:
            units.append(
                {
                    "kind": "single",
                    "id": change_id,
                    "changes": [change],
                    "status": change["status"],
                    "importance": change["importance"],
                    "category": change["category"],
                }
            )
            emitted.add(change_id)
    return units
