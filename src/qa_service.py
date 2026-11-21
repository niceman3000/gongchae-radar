"""근거 질문 서비스 (T028): 공고문 원문 안에서만 답한다.

흐름
1. 코드가 질문 낱말과 공고문 각 줄을 비교해 관련 원문 조각을 고른다 (무료)
2. 관련 원문이 없으면 AI를 부르지 않고 '공고문에 명시 없음'
3. 있으면 그 조각만 AI에 보내 그 안에서만 답하게 한다
4. AI 답의 인용을 원문과 대조한다. 확인되는 인용이 하나도 없으면 '공고문에 명시 없음'
5. API 키가 없거나 오류면 'unavailable' + 원문 조각만 보여준다 (리포트 화면은 영향 없음)

반환값은 data-model 9절 GroundedAnswer (status: answered | not_found | unavailable).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import re
from typing import Any, Mapping

from src.evidence import check_evidence
from src.model_client import ModelClientError

NOT_FOUND = "공고문에 명시 없음"
UNAVAILABLE = "지금은 AI 답변을 만들 수 없어요. 아래 공고문 원문 발췌를 직접 확인해 주세요."
# 11-19: 오늘 확실히 작동한 Sonnet 5.5 + '생각' 끄기(between_tools)를 쓴다 (질문 하나 약 $0.015).
# '생각'이 켜져 있으면 출력 한도를 다 써서 빈 답이 올 수 있다 (11-19 한수원 추출에서 겪음). QA_MODEL 환경변수로 바꿀 수 있다
DEFAULT_QA_MODEL = os.environ.get("QA_MODEL", "claude-sonnet-5-5")
THINKING = {"claude-sonnet-5-5": {"type": "between_tools"}}
MAX_QUESTION = 300
MAX_PASSAGES = 8
CONTEXT_LINES = 2
MIN_HITS = 2  # 질문 낱말 하나가 그대로 있거나(2점) 두 낱말이 일부씩 있어야(1+1) '관련 원문'으로 본다

PREV_WORDS = re.compile(r"작년|전년|지난|2025|바뀌|바뀐|달라|변경|비교|차이|이전")
PERSONAL = re.compile(r"\d{6}\s*-\s*[1-4]\d{6}|01[016789][-\s.]?\d{3,4}[-\s.]?\d{4}|[\w.+-]+@[\w-]+\.[\w.]+")
JOSA = ("이에요", "인가요", "이야", "예요", "에서는", "으로는", "에서", "으로", "에게", "부터", "까지", "이랑", "랑",
        "하고", "은", "는", "이", "가", "을", "를", "에", "의", "도", "만", "로", "와", "과", "야", "요")
STOPWORDS = {"공고", "채용", "알려줘", "알려주세요", "뭐야", "뭐예요", "무엇", "어떻게", "있어", "있나요", "있어요",
             "되나요", "돼요", "돼", "하나요", "해요", "몇", "언제", "어디", "얼마", "이번", "올해", "작년", "전년",
             "필요해", "필요한가요", "필요", "가능", "가능해", "궁금", "질문", "달라졌어", "바뀌었어", "기준", "점"}
# 취준생이 쓰는 말 → 공고문 표현. 질문 낱말 '안에' 들어 있어도 적용한다 (11-19 '토익점수' → TOEIC 못 찾음)
SYNONYMS = {"토익": ["TOEIC", "외국어"], "토플": ["TOEFL", "외국어"], "텝스": ["TEPS", "외국어"], "오픽": ["OPIc", "외국어"],
            "토스": ["TOEIC Speaking", "외국어"], "영어": ["외국어", "어학", "TOEIC"], "어학": ["외국어", "어학성적"],
            "자소서": ["자기소개서"], "군대": ["병역"], "군필": ["병역"], "나이": ["연령"], "가산점": ["가점"],
            "연봉": ["보수", "급여", "연봉"], "월급": ["보수", "급여"], "근무지": ["근무지역", "배치", "근무예정지"],
            "마감": ["접수기간", "마감"], "학점": ["학력", "성적"], "전공": ["학과", "전공"], "졸업": ["학력", "졸업"],
            "인적성": ["인성검사", "적성"], "NCS": ["직업기초능력"], "합격자": ["합격자", "발표"], "발표": ["발표"],
            "지역인재": ["이전지역인재", "지역인재"], "보훈": ["취업지원대상자", "보훈"], "장애": ["장애인"]}
SPLIT_WORDS = ("점수", "성적", "기준", "조건", "제한", "자격", "시험", "일정", "기간", "인원", "배점")

SYSTEM = f"""너는 공공기관 채용공고문 안내 도우미다. 아래 [공고문 발췌]에 적힌 내용만으로 답한다.
규칙
1. 발췌에 질문과 관련된 내용이 전혀 없을 때만 status를 "not_found", answer를 "{NOT_FOUND}"로 한다.
   일부만 확인되면 확인되는 만큼 답하고(status "answered"), 모자란 부분은 원문 표현대로 알려준다
   (예: "기술직은 선발 분야 기사 자격증 등이 지원자격이며, 세부 목록은 공고문 붙임 2를 확인하세요").
2. 답은 한국어 1~3문장, 해요체("~예요", "~해요")로 쓴다. 숫자·날짜는 원문 그대로. 발췌에 없는 내용을 지어내지 않는다.
3. evidence에는 답의 근거가 되는 원문 줄을 1~3개, 발췌에 적힌 그대로 복사한다 (40자 이내, 글자 바꾸지 말 것).
   side는 발췌 머리의 "올해 공고" → "curr", "작년 공고" → "prev", page는 쪽 번호.
4. 합격 가능성·추천·개인 판단은 하지 않는다.
5. JSON 객체 하나만 출력: {{"status":"answered 또는 not_found","answer":"","evidence":[{{"side":"curr","page":1,"quote":""}}]}}"""


@dataclass
class GroundedAnswer:
    status: str                      # answered | not_found | unavailable
    answer: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    ai_generated: bool = False
    excerpts: list[dict[str, Any]] = field(default_factory=list)  # 고른 원문 조각 (키 없을 때 보여줌)
    note: str = ""
    model_called: bool = False       # AI를 불렀는지 (비용·횟수 세기용)


def _terms(question: str) -> list[tuple[set[str], set[str]]]:
    """질문 → 낱말 묶음 목록 [(같은 낱말로 보는 표기들, 원래 낱말의 2글자 조각)].
    나눈 말(필기시험 → 필기, 시험)·바꿔 쓴 말(토익 → TOEIC)은 원래 낱말과 한 묶음으로 센다
    (11-20 한수원 '필기시험 직업기초능력은 몇 문항이야?': 필기·시험이 따로 점수를 받아 정답 줄이 밀려남)."""
    groups: list[tuple[set[str], set[str]]] = []
    seen: set[str] = set()
    for word in re.findall(r"[가-힣A-Za-z0-9]+", question):
        for josa in JOSA:
            if len(word) > len(josa) + 1 and word.endswith(josa):
                word = word[: -len(josa)]
                break
        if word in STOPWORDS or len(word) < 2 or word in seen:
            continue
        seen.add(word)
        forms = {word}
        for key, values in SYNONYMS.items():  # 붙여 쓴 말 안에 있어도 (토익점수 → 토익)
            if key in word:
                forms.update(values + [key])
        for tail in SPLIT_WORDS:  # '토익점수' → '토익', '점수'
            if word.endswith(tail) and len(word) > len(tail) + 1:
                forms.update([word[: -len(tail)], tail])
                break
        # 자격증 이름은 가점표에 '종목'과 '등급'이 칸으로 나뉘어 있으므로 둘로도 찾는다 (전기기사 → 전기, 기사)
        for grade in ("산업기사", "기능사", "기능장", "기술사", "기사"):
            if word.endswith(grade) and len(word) > len(grade) + 1:
                forms.update([word[: -len(grade)], grade])
                break
        grams = {word[i: i + 2].upper() for i in range(len(word) - 1)}
        groups.append(({form.upper() for form in forms}, grams))
    return groups


def _score(line: str, terms: list[tuple[set[str], set[str]]]) -> int:
    """낱말 묶음마다 최대 2점: 표기 중 하나가 그대로 있으면 2점, 원래 낱말의 2글자 조각이 절반 이상 있으면 1점."""
    text = re.sub(r"\s+", "", line).upper()
    score = 0
    for forms, grams in terms:
        if any(form in text for form in forms):
            score += 2
        elif len(grams) > 1 and sum(gram in text for gram in grams) * 2 >= len(grams):
            score += 1
    return score


def find_passages(question: str, curr_text: Mapping[str, str] | None,
                  prev_text: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    """관련 원문 조각: [{side, page, text, score}] 점수 높은 순."""
    terms = _terms(question)
    if not terms:
        return []
    sources = [("curr", curr_text or {})]
    if prev_text and PREV_WORDS.search(question):
        sources.append(("prev", prev_text))
    found = []
    for side, pages in sources:
        for page, text in pages.items():
            lines = str(text).split("\n")
            for index, line in enumerate(lines):
                # 표는 칸마다 줄이 나뉘므로(예: '전기전자' / '기사·기능장 5점') 앞뒤 한 줄까지 합쳐서 본다
                score = _score(" ".join(lines[max(0, index - 1): index + 2]), terms)
                if score >= MIN_HITS:
                    start, end = max(0, index - CONTEXT_LINES), min(len(lines), index + CONTEXT_LINES + 1)
                    found.append({"side": side, "page": int(page), "score": score, "line": index,
                                  "text": "\n".join(lines[start:end]).strip()})
    found.sort(key=lambda item: (-item["score"], item["side"] != "curr", item["page"], item["line"]))
    chosen, seen, per_page = [], set(), {}
    for item in found:  # 같은 쪽 가까운 줄은 한 번만, 한 쪽에서는 최대 2조각 (여러 쪽을 보게)
        key = (item["side"], item["page"], item["line"] // (CONTEXT_LINES * 2 + 1))
        page_key = (item["side"], item["page"])
        if key in seen or per_page.get(page_key, 0) >= 2:
            continue
        seen.add(key)
        per_page[page_key] = per_page.get(page_key, 0) + 1
        chosen.append({key_: item[key_] for key_ in ("side", "page", "text", "score")})
        if len(chosen) >= MAX_PASSAGES:
            break
    # 작년 단어가 있으면 작년 조각도 최소 하나는 넣는다 (비교 질문)
    if prev_text and PREV_WORDS.search(question) and not any(item["side"] == "prev" for item in chosen):
        prev = [item for item in found if item["side"] == "prev"][:2]
        chosen = chosen[: MAX_PASSAGES - len(prev)] + [{k: item[k] for k in ("side", "page", "text", "score")} for item in prev]
    return chosen


def _prompt(question: str, passages: list[dict[str, Any]]) -> str:
    label = {"curr": "올해 공고", "prev": "작년 공고"}
    body = "\n\n".join(f"[{label[item['side']]} {item['page']}쪽]\n{item['text']}" for item in passages)
    return f"[질문]\n{question}\n\n[공고문 발췌]\n{body}"


def _parse(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for start in [index for index, char in enumerate(text) if char == "{"]:
        try:
            value, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "answer" in value:
            return value
    return None


def ask(question: str, *, curr_text: Mapping[str, str] | None, prev_text: Mapping[str, str] | None = None,
        client: Any = None, model: str = DEFAULT_QA_MODEL) -> GroundedAnswer:
    """질문 하나에 답한다. client가 None이면(키 없음) 원문 발췌만 돌려준다."""
    question = (question or "").strip()
    if not question:
        raise ValueError("질문을 입력해 주세요.")
    if len(question) > MAX_QUESTION:
        raise ValueError(f"질문은 {MAX_QUESTION}자 이내로 입력해 주세요.")
    if PERSONAL.search(question):
        raise ValueError("이름·연락처·주민등록번호 같은 개인정보는 입력하지 마세요.")
    if not curr_text:
        return GroundedAnswer("unavailable", "이 공고는 공고문이 그림·스캔 파일이라 원문 질문을 할 수 없어요.",
                              note="공고문 글자 없음")

    passages = find_passages(question, curr_text, prev_text)
    if not passages:
        return GroundedAnswer("not_found", NOT_FOUND, note="관련 원문 없음 (AI 호출 안 함)")
    if client is None:
        return GroundedAnswer("unavailable", UNAVAILABLE, excerpts=passages, note="API 키 없음")

    try:
        response = client.complete(model=model, system=SYSTEM, user=_prompt(question, passages), max_tokens=4000,
                                   **({"thinking": THINKING[model]} if model in THINKING else {}))
    except ModelClientError as exc:
        return GroundedAnswer("unavailable", UNAVAILABLE, excerpts=passages, note=str(exc)[:200], model_called=True)
    raw = _parse(response.text)
    if raw is None:
        return GroundedAnswer("unavailable", UNAVAILABLE, excerpts=passages, note="AI 답 형식 오류", model_called=True)

    texts = {"curr": curr_text or {}, "prev": prev_text or {}}
    evidence = []
    for item in raw.get("evidence") or []:
        if not isinstance(item, dict) or item.get("side") not in texts:
            continue
        page = item.get("page")
        page = int(page) if isinstance(page, str) and page.isdigit() else page
        checked = {"side": item["side"], "page": page, "quote": str(item.get("quote") or "").strip()[:300]}
        ok, _ = check_evidence(checked, texts[item["side"]])
        if ok:
            evidence.append({**checked, "verified": True})
    if raw.get("status") != "answered" or not evidence:
        if raw.get("status") != "answered":
            note = "AI가 발췌에서 답을 찾지 못함"
        else:
            quotes = " / ".join(str(item.get("quote")) for item in raw.get("evidence") or [] if isinstance(item, dict))[:150]
            note = f"AI 인용이 원문에 없어 버림 (AI 답: {str(raw.get('answer'))[:60]} · 인용: {quotes})"
        return GroundedAnswer("not_found", NOT_FOUND, excerpts=passages, note=note, model_called=True)
    return GroundedAnswer("answered", str(raw.get("answer") or "").strip(), evidence=evidence,
                          ai_generated=True, excerpts=passages, model_called=True)
