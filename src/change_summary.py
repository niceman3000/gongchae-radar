"""'작년과 달라진 점' 5줄 요약 + 올해 일정 표 (11-21 구조 개편 명세 4번). 규칙 기반, AI 호출 없음.

이미 있는 변경 기록(report["changes"]), 우대사항 정리(notice_info.benefits), 공고 제목·모집단위만으로 만든다.
30곳 모두 같은 규칙 (11-19 '같은 과정' 결정 유지). 판정 로직·인용 대조·데이터는 건드리지 않는다.

줄: 몇 명 뽑나 / 전형 단계 / 지원 자격 / 가점·우대 / 일정
상태: 같음 · 바뀜 · 새로 · 비교 어려움 · 정보 없음 ('같음'은 작년·올해 둘 다 확인됐을 때만)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STATUSES = ("같음", "바뀜", "새로", "비교 어려움", "정보 없음")
# 전형 구분: 작년·올해 구분이 다르면 인원은 '비교 어려움'
KINDS = ("일반", "보훈", "장애", "고졸", "별정직", "지역인재", "사회형평", "경력")
GLOSSARY = {
    "본사이전 지역인재": "본사 이전 지역 학교 출신만 해당",
    "지역인재": "본사 이전 지역 학교 출신만 해당",
    "배수": "서류 통과 인원 = 뽑는 인원 × 배수",
}
BULLET = re.compile(r"^\s*(?:[□■○●◦ㅇ※\-·•*▶▷>]|\d{1,2}[.)]|\(\d{1,2}\)|[①-⑳]|[가-하][.)])\s*")
DATE = re.compile(r"(?:(\d{4})|['’‘](\d{2}))\s*[.년]\s*(\d{1,2})\s*[.월]\s*(\d{1,2})")
DATE_SHORT = re.compile(r"(?<![\d.])(\d{1,2})\s*\.\s*(\d{1,2})\s*\.?")


@dataclass
class SummaryRow:
    key: str            # 'count', 'stages', 'eligibility', 'bonus', 'schedule'
    question: str       # 몇 명 뽑나
    status: str         # STATUSES 중 하나
    answer: str         # 한두 문장
    note: str = ""      # 작은 회색 글씨 (용어 풀이, 직렬별 인원 안내)
    categories: list[str] = field(default_factory=list)  # '원문 대조 ›'가 여는 분류


# ---------------------------------------------------------------- 정리
def strip_bullet(text: Any) -> str:
    """문장 앞 번호·기호('1.', '-', '○', '□', '※', '①') 지우기"""
    value = str(text or "").strip()
    for _ in range(3):
        stripped = BULLET.sub("", value)
        if stripped == value:
            break
        value = stripped
    return value.strip()


def normalize(text: Any) -> str:
    """비교용: 번호·기호를 지우고 띄어쓰기·쉼표·괄호 같은 기호와 숫자 뒤 '점'을 무시 (색칠 규칙과 같은 정규화)"""
    value = strip_bullet(text)
    value = re.sub(r"(\d)\s*점", r"\1", value)
    return re.sub(r"[\W_]+", "", value)


def same_after_normalize(prev: Any, curr: Any) -> bool:
    return isinstance(prev, str) and isinstance(curr, str) and normalize(prev) == normalize(curr)


def _head_noun(text: str) -> str:
    """':' 앞 핵심 명사 ('본사이전 지역인재 : 아래 분야 …' → '본사이전지역인재')"""
    head = strip_bullet(text).split(":", 1)[0]
    head = normalize(head)
    return head if 4 <= len(head) <= 30 and ":" in strip_bullet(text) else ""


def similar_exists(text: str, others: Iterable[str]) -> bool:
    """작년 공고에 비슷한 문장이 있나: 정규화 후 SequenceMatcher 0.6 이상이거나 핵심 명사가 같음"""
    key = normalize(text)
    noun = _head_noun(text)
    if not key:
        return True
    for other in others:
        other_key = normalize(other)
        if not other_key:
            continue
        if noun and noun == _head_noun(other):
            return True
        if noun and noun in other_key:
            return True
        if SequenceMatcher(None, key, other_key, autojunk=False).ratio() >= 0.6:
            return True
    return False


def _texts(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]


def prev_lines(report: Mapping[str, Any]) -> list[str]:
    """작년 공고 문장: 변경 기록의 작년 값 + (있으면) 작년 공고문 글자 묶음"""
    lines = [text for change in report.get("changes") or [] for text in _texts(change.get("prev_value"))]
    for benefit in (report.get("notice_info") or {}).get("benefits") or []:
        if benefit.get("prev_benefit"):
            lines.append(f"{benefit['name']} : {benefit['prev_benefit']}")
    sn = str((report.get("prev") or {}).get("sn") or "")
    path = ROOT / "stage2" / f"bundle_{sn}.json"
    if sn and path.exists():
        try:
            pages = json.loads(path.read_text(encoding="utf-8")).get("all_text") or {}
            for text in (pages.values() if isinstance(pages, dict) else pages):
                lines.extend(line for line in str(text).splitlines() if len(line.strip()) >= 4)
        except (OSError, ValueError):
            pass
    return lines


# ---------------------------------------------------------------- 날짜
def _dates(text: str, default_year: int) -> list[date]:
    found: list[date] = []
    for match in DATE.finditer(text):
        year = int(match.group(1)) if match.group(1) else 2000 + int(match.group(2))
        try:
            found.append(date(year, int(match.group(3)), int(match.group(4))))
        except ValueError:
            continue
    if not found:  # 공고문 원문의 '10.24.(금)', '10. 24.(금) ~ 10. 28.(화)' (연도 없음 → 공고 연도)
        for match in DATE_SHORT.finditer(text):
            try:
                found.append(date(default_year, int(match.group(1)), int(match.group(2))))
            except ValueError:
                continue
        return found[:2]
    if found:
        # '2025.12.05.(금) ∼ 12.08.(월)'의 뒤 날짜
        tail = text[text.rfind(f"{found[-1].day:02d}") + 2:] if found else ""
        match = re.search(r"[~∼～-]\s*(\d{1,2})\s*\.\s*(\d{1,2})", tail)
        if match:
            try:
                found.append(date(found[-1].year, int(match.group(1)), int(match.group(2))))
            except ValueError:
                pass
    return found


def is_schedule_line(text: Any) -> bool:
    return bool(DATE.search(str(text or "")))


def date_only_change(change: Mapping[str, Any]) -> bool:
    """날짜만 바뀐 변경 (→ 변경점이 아니라 '올해 일정')"""
    if change.get("change_type") == "date":
        return True
    prev, curr = change.get("prev_value"), change.get("curr_value")
    texts = [text for text in (prev, curr) if isinstance(text, str)]
    if not texts or not all(is_schedule_line(text) for text in texts):
        return False
    if change.get("change_type") in {"added", "removed"}:
        return True
    strip = lambda text: normalize(DATE_SHORT.sub("", DATE.sub("", re.sub(r"\([월화수목금토일]\)", "", text))))
    return strip(prev) == strip(curr) or SequenceMatcher(None, strip(prev), strip(curr)).ratio() >= 0.8


def meaningful_changes(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    """원문 대조에 보여 줄 변경: 정리한 뒤 같은 문장과 날짜만 바뀐 것은 뺌"""
    output = []
    for change in report.get("changes") or []:
        if change.get("change_type") == "text" and same_after_normalize(change.get("prev_value"), change.get("curr_value")):
            continue
        if date_only_change(change):
            continue
        output.append(change)
    return output


# ---------------------------------------------------------------- 전형 구분
def kinds_of(texts: Iterable[str]) -> set[str]:
    joined = " ".join(texts)
    return {kind for kind in KINDS if kind in joined}


def _kind_sets(report: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    prev_texts = [str((report.get("prev") or {}).get("title") or "")]
    curr_texts = [str((report.get("curr") or {}).get("title") or "")]
    for change in report.get("changes") or []:
        if change.get("category") in {"모집단위", "학력조건"}:
            if change.get("change_type") == "list":
                prev_texts += _texts(change.get("prev_value"))
                curr_texts += _texts(change.get("curr_value"))
    prev, curr = kinds_of(prev_texts), kinds_of(curr_texts)
    # '일반'은 제목에 안 쓰는 곳이 많아서 한쪽에만 있으면 무시
    if ("일반" in prev) != ("일반" in curr):
        prev.discard("일반")
        curr.discard("일반")
    return prev, curr


def _kind_sentence(prev: set[str], curr: set[str]) -> str:
    parts = [f"{kind} 전형 없어짐" for kind in KINDS if kind in prev - curr]
    parts += [f"{kind} 전형 새로 생김" for kind in KINDS if kind in curr - prev]
    return " · ".join(parts)


# ---------------------------------------------------------------- 줄별 규칙
def _count_row(report: Mapping[str, Any], track: str) -> SummaryRow:
    note = f"{track} 직렬 인원은 공고문 표에서 확인" if track else ""
    number = next((change for change in report.get("changes") or []
                   if change.get("category") == "인원" and change.get("change_type") == "number"), None)
    if not number:
        return SummaryRow("count", "몇 명 뽑나", "정보 없음", "작년과 비교할 인원 기록이 없어요.", note, ["인원"])
    prev, curr = int(number["prev_value"]), int(number["curr_value"])
    prev_kinds, curr_kinds = _kind_sets(report)
    if prev_kinds != curr_kinds:
        added = [kind for kind in KINDS if kind in curr_kinds - prev_kinds]
        removed = [kind for kind in KINDS if kind in prev_kinds - curr_kinds]
        reason = (f"올해는 {'·'.join(added)} 전형이 새로 들어가" if added
                  else f"올해는 {'·'.join(removed)} 전형이 빠져")
        return SummaryRow("count", "몇 명 뽑나", "비교 어려움",
                          f"전체 {prev}명 → {curr}명. {reason} 단순 비교가 어려워요.", note, ["인원", "모집단위"])
    if prev == curr:
        return SummaryRow("count", "몇 명 뽑나", "같음", f"전체 {curr}명으로 작년과 같아요.", note, ["인원"])
    diff = curr - prev
    return SummaryRow("count", "몇 명 뽑나", "바뀜", f"{prev}명 → {curr}명 ({diff:+d}명)", note, ["인원"])


def _multiples(text: str) -> dict[str, str]:
    from app.ui_components import _multiples as parse  # 같은 규칙을 화면 제목에도 씀

    return parse(text)


def _interviews(lines: Iterable[str]) -> int:
    rounds = {match for line in lines for match in re.findall(r"(\d)\s*차\s*면접", line)}
    has_interview = any("면접" in line for line in lines)
    return len(rounds) if rounds else (1 if has_interview else 0)


def _stage_row(report: Mapping[str, Any], track: str) -> SummaryRow:
    changes = [change for change in report.get("changes") or [] if change.get("category") == "전형"]
    if not changes:
        return SummaryRow("stages", "전형 단계", "정보 없음", "작년과 비교할 전형 기록이 없어요.", "", ["전형"])
    found: list[tuple[int, str]] = []
    multiple_note = ""
    for change in changes:
        prev, curr = change.get("prev_value"), change.get("curr_value")
        if not (isinstance(prev, str) and isinstance(curr, str)):
            continue
        before, after = _multiples(prev), _multiples(curr)
        for subject, number in after.items():
            old = before.get(subject)
            if old is None:  # 작년엔 '기술 : 15배수' 하나 → 올해 '전기(배전, 송변전) : 10배수'
                gone = [(name, value) for name, value in before.items() if name not in after]
                old = gone[0][1] if gone else None
            if old and old != number:
                label = subject.replace(", ", "·")
                found.append((0 if track and track in subject else 1, f"{label} 서류 {old}배수 → {number}배수"))
                multiple_note = GLOSSARY["배수"]
        ratio_prev = re.findall(r"(\d{2})\s*:\s*(\d{2})(?!\s*배수)", prev)
        ratio_curr = re.findall(r"(\d{2})\s*:\s*(\d{2})(?!\s*배수)", curr)
        if ratio_prev and ratio_curr and ratio_prev[0] != ratio_curr[0] and "면접" in curr:
            found.append((1, f"면접 배점 {':'.join(ratio_prev[0])} → {':'.join(ratio_curr[0])}"))
    prev_lines_ = [str(change.get("prev_value")) for change in changes if change.get("prev_value")]
    curr_lines_ = [str(change.get("curr_value")) for change in changes if change.get("curr_value")]
    before, after = _interviews(prev_lines_), _interviews(curr_lines_)
    if before >= 2 and after == 1:
        found.append((1, f"면접 {before}번(1차·2차) → 1번"))
    elif before == 1 and after >= 2:
        found.append((1, f"면접 1번 → {after}번"))
    if found:
        found.sort(key=lambda item: item[0])
        answer = " · ".join(dict.fromkeys(text for _, text in found[:2]))
        return SummaryRow("stages", "전형 단계", "바뀜", answer, multiple_note, ["전형"])
    wording = [change for change in changes if not date_only_change(change)
               and not same_after_normalize(change.get("prev_value"), change.get("curr_value"))]
    if wording:
        return SummaryRow("stages", "전형 단계", "바뀜", f"문구 바뀜 {len(wording)}건", "", ["전형"])
    return SummaryRow("stages", "전형 단계", "같음", "단계는 같고 날짜만 바뀌었어요.", "", ["전형"])


def _eligibility_row(report: Mapping[str, Any]) -> SummaryRow:
    categories = ["자격", "결격사유", "학력조건", "모집단위"]
    prev_kinds, curr_kinds = _kind_sets(report)
    sentence = _kind_sentence(prev_kinds, curr_kinds)
    changes = [change for change in meaningful_changes(report) if change.get("category") in categories]
    if sentence:
        changed = (prev_kinds ^ curr_kinds)
        note = "대졸 일반 지원자에게 직접 영향은 적어요" if "일반" not in changed else ""
        return SummaryRow("eligibility", "지원 자격", "바뀜", sentence, note, categories)
    if changes:
        return SummaryRow("eligibility", "지원 자격", "바뀜", f"문구 바뀜 {len(changes)}건", "", categories)
    if any(change.get("category") in categories for change in report.get("changes") or []):
        return SummaryRow("eligibility", "지원 자격", "같음", "띄어쓰기·표기만 바뀌었어요.", "", categories)
    return SummaryRow("eligibility", "지원 자격", "정보 없음", "작년과 비교할 자격 기록이 없어요.", "", categories)


def _numbers(text: Any) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)?\s*(?:%|점|배수|명)", str(text or ""))


def _bonus_row(report: Mapping[str, Any]) -> SummaryRow:
    benefits = (report.get("notice_info") or {}).get("benefits") or []
    changes = [change for change in report.get("changes") or [] if change.get("category") == "가점"]
    if not benefits and not changes:
        return SummaryRow("bonus", "가점·우대", "정보 없음", "작년과 비교할 우대사항 기록이 없어요.", "", ["가점"])
    previous = prev_lines(report)
    added_texts = [text for change in changes if change.get("change_type") == "added"
                   for text in _texts(change.get("curr_value"))]
    changed: list[str] = []
    kept: list[str] = []
    new: list[str] = []
    note = ""
    for benefit in benefits:
        name, now, before = str(benefit.get("name") or ""), benefit.get("benefit"), benefit.get("prev_benefit")
        if benefit.get("change") == "changed" and now and before:
            if set(_numbers(now)) != set(_numbers(before)) and _numbers(now):
                changed.append(f"{name} {', '.join(dict.fromkeys(_numbers(before)))} → {', '.join(dict.fromkeys(_numbers(now)))}")
            elif _numbers(now):
                kept.append(f"{name} {', '.join(dict.fromkeys(_numbers(now)))} 그대로. 적용 대상 표기만 바뀜")
            if "지역인재" in name:
                note = GLOSSARY["지역인재"]
        elif benefit.get("change") == "new" and now and _numbers(now):
            line = f"{name} : {now}"
            in_added = any(normalize(name)[:8] in normalize(text) for text in added_texts)
            if in_added and not similar_exists(line, previous):
                new.append(f"{name} {now}")
    if changed:
        return SummaryRow("bonus", "가점·우대", "바뀜", " · ".join(changed[:2]), note, ["가점"])
    if new:
        return SummaryRow("bonus", "가점·우대", "새로", " · ".join(new[:2]), note, ["가점"])
    if kept:
        return SummaryRow("bonus", "가점·우대", "같음", kept[0], note, ["가점"])
    wording = [change for change in changes if not same_after_normalize(change.get("prev_value"), change.get("curr_value"))]
    if wording:
        return SummaryRow("bonus", "가점·우대", "바뀜", f"문구 바뀜 {len(wording)}건 (점수·비율은 그대로)", note, ["가점"])
    return SummaryRow("bonus", "가점·우대", "같음", "작년과 같아요.", note, ["가점"])


# ---------------------------------------------------------------- 일정
STAGES = (  # (칸 이름, 찾는 말, 빼는 말)
    ("지원서 접수", r"(입사)?지원서\s*접수|원서\s*접수|접수\s*기간", r"발표"),
    ("필기 합격 발표", r"필기\s*(전형\s*)?합격(자)?\s*발표", r""),
    ("서류 합격 발표", r"서류\s*(전형\s*)?합격(자)?\s*발표", r""),
    ("자기소개서", r"자기소개서", r""),
    ("면접", r"면접(전형)?", r"발표|대상자|합격"),
    ("최종 발표", r"최종\s*합격(자)?\s*발표", r""),
)


def _stage_dates(lines: Iterable[str], year: int) -> dict[str, list[date]]:
    output: dict[str, list[date]] = {}
    for line in lines:
        text = strip_bullet(line)
        for name, pattern, exclude in STAGES:
            if name in output or not re.search(pattern, text) or (exclude and re.search(exclude, text)):
                continue
            dates = _dates(text, year)
            if len(dates) > 1 and dates[-1] < dates[0]:  # 끝이 앞보다 이르면 뒤 날짜는 버림 (다른 줄이 섞인 것)
                dates = dates[:1]
            if dates:
                output[name] = dates
                break
    return output


def _bundle_lines(sn: str) -> list[str]:
    path = ROOT / "stage2" / f"bundle_{sn}.json"
    if not sn or not path.exists():
        return []
    try:
        pages = json.loads(path.read_text(encoding="utf-8")).get("all_text") or {}
    except (OSError, ValueError):
        return []
    texts = pages.values() if isinstance(pages, dict) else pages
    return [line.strip() for text in texts for line in str(text).splitlines() if 6 <= len(line.strip()) <= 120]


def _schedule_lines(report: Mapping[str, Any], side: str) -> list[str]:
    """일정 줄: 변경 기록(채용정보 API 문장) 먼저, 없으면 공고문 원문 글자에서 날짜가 있는 줄"""
    key = "curr_value" if side == "curr" else "prev_value"
    lines = [text for change in report.get("changes") or [] if change.get("category") in {"전형", "일정", "기타"}
             for text in _texts(change.get(key)) if is_schedule_line(text)]
    if side == "curr":
        info = report.get("notice_info") or {}
        lines += [str(item.get("text") or "") for item in info.get("rules") or []]
        lines += [str(item) for item in info.get("submissions") or []]
    return lines


def _all_stage_dates(report: Mapping[str, Any], side: str, year: int) -> dict[str, list[date]]:
    """변경 기록(API 문장)에서 먼저 찾고, 없는 단계만 공고문 원문 글자에서. 원문의 '접수' 줄은 안 씀 (다른 줄이 섞임)"""
    found = _stage_dates(_schedule_lines(report, side), year)
    sn = str((report.get(side) or {}).get("sn") or "")
    extra = _stage_dates([line for line in _bundle_lines(sn) if DATE.search(line) or DATE_SHORT.search(line)], year)
    extra.pop("지원서 접수", None)
    return {**extra, **found}


def schedule(report: Mapping[str, Any], today: date | None = None) -> list[dict[str, Any]]:
    """올해 일정 표 (최대 5칸): 지원서 접수 · 필기(또는 서류) 합격 발표 · 자기소개서 · 면접 · 최종 발표"""
    today = today or date.today()
    period = (report.get("curr") or {}).get("period") or {}
    year = int(str(period.get("start") or "2026")[:4])
    found = _all_stage_dates(report, "curr", year)
    start, end = str(period.get("start") or ""), str(period.get("end") or "")
    if "지원서 접수" not in found and len(start) == 8 and len(end) == 8:  # 없으면 채용정보 API 공고 기간
        found = {"지원서 접수": [date(int(start[:4]), int(start[4:6]), int(start[6:])),
                             date(int(end[:4]), int(end[4:6]), int(end[6:]))], **found}
    if "필기 합격 발표" in found:
        found.pop("서류 합격 발표", None)
    cells = []
    for name, _, _ in STAGES:
        if name in found:
            dates = found[name]
            text = f"{dates[0]:%m.%d}" + (f"~{dates[-1]:%m.%d}" if len(dates) > 1 and dates[-1] != dates[0] else "")
            cells.append({"name": name, "text": text.lstrip("0").replace("~0", "~").replace(".0", "."),
                          "first": dates[0], "last": dates[-1]})
    current = next((cell for cell in cells if cell["last"] >= today), None)
    for cell in cells:
        cell["current"] = cell is current
    return cells[:5]


def _schedule_row(report: Mapping[str, Any]) -> SummaryRow:
    period = (report.get("curr") or {}).get("period") or {}
    year = int(str(period.get("start") or "2026")[:4])
    prev_year = int(str(((report.get("prev") or {}).get("period") or {}).get("start") or year - 1)[:4])
    curr = _all_stage_dates(report, "curr", year)
    prev = _all_stage_dates(report, "prev", prev_year)
    for name in ("필기 합격 발표", "서류 합격 발표", "면접"):
        if name in curr and name in prev:
            now, before = curr[name][0], prev[name][0]
            try:
                shifted = before.replace(year=now.year)
            except ValueError:
                shifted = before.replace(year=now.year, day=28)
            gap = (now - shifted).days
            if gap > 180:
                gap -= 365
            elif gap < -180:
                gap += 365
            label = f"{name} {now:%m.%d}"
            if abs(gap) < 7:
                return SummaryRow("schedule", "일정", "같음",
                                  f"{label} (작년 {before:%m.%d}과 비슷한 때)", "", ["일정"])
            weeks = round(abs(gap) / 7)
            amount = f"약 {weeks}주" if weeks else f"{abs(gap)}일"
            return SummaryRow("schedule", "일정", "바뀜",
                              f"{label} (작년 {before:%m.%d}보다 {amount} {'늦음' if gap > 0 else '빠름'})", "", ["일정"])
    if curr:
        name, dates = next(iter(curr.items()))
        return SummaryRow("schedule", "일정", "정보 없음",
                          f"올해 {name} {dates[0]:%m.%d}. 작년 같은 단계 날짜는 공고문에서 확인하세요.", "", ["일정"])
    return SummaryRow("schedule", "일정", "정보 없음", "공고에서 일정 줄을 찾지 못했어요.", "", ["일정"])


def summarize(report: Mapping[str, Any], track: str = "") -> list[SummaryRow]:
    """고정 5줄"""
    return [_count_row(report, track), _stage_row(report, track), _eligibility_row(report),
            _bonus_row(report), _schedule_row(report)]


def changed_points(report: Mapping[str, Any], track: str = "", limit: int = 2) -> list[str]:
    """목록 한 줄용 '바뀐 점': 상태가 '바뀜'·'새로'인 줄의 답 최대 2개"""
    rows = [row for row in summarize(report, track) if row.status in {"바뀜", "새로"} and not row.answer.startswith("문구 바뀜")]
    return [_short(row.answer) for row in rows[:limit]]


def _short(text: str, limit: int = 34) -> str:
    text = re.sub(r"\s*\([^)]*\)$", "", text) if len(text) > limit else text
    return text if len(text) <= limit else text[: limit - 1] + "…"


def prev_start_text(report: Mapping[str, Any]) -> str:
    """지난 공고 '다음 공고 참고': 작년 공고 접수 시작일 ('9월 9일')"""
    start = str(((report.get("prev") or {}).get("period") or {}).get("start") or "")
    return f"{int(start[4:6])}월 {int(start[6:])}일" if len(start) == 8 and start.isdigit() else ""
