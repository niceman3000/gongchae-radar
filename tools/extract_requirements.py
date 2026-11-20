# -*- coding: utf-8 -*-
"""
공기업 30곳의 지원 자격·가점을 유료 AI(Claude)로 뽑기 (tasks.md T045)

30곳 모두 이 프로그램으로 뽑는다 (11-19부터 핵심 3곳 포함).
핵심 3곳의 evaluation/ground_truth/<기관>_requirements.json은 화면에 쓰지 않고, 이 프로그램 결과를 채점하는 정답지로 쓴다
(tools/score_against_ground_truth.py).
나머지 27곳은 같은 형식을 AI가 올해 공고문 PDF에서 뽑는다.
  - 인용문(쪽수 + 원문 문장)은 PDF 글자와 다시 대조해서, 원문에 없는 인용은 버린다
  - 근거가 하나도 안 남은 항목은 버린다 (근거 없는 조건으로 판정하지 않게)
  - 결과: evaluation/ai_extracted/<기관코드>_requirements.json  (핵심 3곳 파일과 섞지 않음)
  - 사용량·비용 기록: evaluation/ai_extracted/usage.json

실행 (프로젝트 최상위 폴더, PowerShell)
  $env:ANTHROPIC_API_KEY = "키"            ← 이 창에서만, 파일·채팅에 남기지 않음
  1) 비용만 계산 (돈 안 듦, 토큰 세기만):
     .\\.venv\\Scripts\\python.exe tools\\extract_requirements.py
  2) 한 곳만 시험:
     .\\.venv\\Scripts\\python.exe tools\\extract_requirements.py --run --only 한국서부발전
  3) 전부:
     .\\.venv\\Scripts\\python.exe tools\\extract_requirements.py --run
  그다음 리포트 다시 만들기:
     .\\.venv\\Scripts\\python.exe tools\\build_auto_reports.py

이미 뽑은 기관은 건너뛴다(--force면 다시). 새 공고가 수집돼 짝(pair_id)이 바뀌면 다시 뽑는다. 누적 비용이 --max-cost(기본 $2)를 넘으면 멈춘다.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
import os
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ai_pipeline import AiPipelineError  # noqa: E402
from src.evidence import check_evidence  # noqa: E402
from src.model_client import AnthropicClient, ModelClientError  # noqa: E402
from src.report_builder import TRACK_PATTERNS, load_api_item, unit_track  # noqa: E402
from tools.build_auto_reports import _bundle_text, all_pairs  # noqa: E402

OUT_DIR = ROOT / "evaluation" / "ai_extracted"
RAW_DIR = OUT_DIR / "raw"
REVIEW_DIR = ROOT / "evaluation" / "ground_truth"
DEFAULT_MODEL = "claude-sonnet-5-5"
# 달러 / 100만 토큰 (입력, 출력). 2026-11 Anthropic 요금표. Haiku 5.5는 입력 10만 토큰 이하 기준
PRICES = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}
OUTPUT_GUESS = 14000         # 비용 계산 때 가정하는 출력 토큰 수 (한 곳당, 11-19 서부발전 실제 14,219)
MAX_OUTPUT = 24000           # 11-19: 12000으로는 서부발전 답이 잘림 → 한도 올리고 답을 짧게 받음
FULL_TEXT_LIMIT = 80000      # 공고문 전체 글자가 이보다 적으면 전 쪽을 보낸다 (아니면 관련 쪽만)
THINKING = {"claude-sonnet-5-5": {"type": "between_tools"}}
TRACKS = [name for name, _ in TRACK_PATTERNS] + ["기타"]
KINDS = {"major", "accepted", "required", "bonus"}
GRADES = {"기능사", "산업기사", "기사", "기능장", "기술사"}  # 리포트 규격이 받는 등급

SYSTEM = f"""너는 공공기관 채용공고문에서 '누가 지원할 수 있는지'와 '자격증 가점'을 정리하는 도구다.
규칙
1. 제공된 공고문 안의 사실만 쓴다. 추측하지 않는다. 없으면 빈 배열.
2. 모든 항목에 evidence(근거)를 1~2개 붙인다. 근거 = {{"page":쪽번호,"quote":"그 쪽 원문을 그대로 복사한 40자 이내 한 줄"}}.
   quote는 글자·기호를 바꾸지 말고 원문 그대로 복사한다 (원문 대조로 검사하며, 다르면 버려진다).
3. track(직렬)은 다음 중 하나: {", ".join(TRACKS)}.
4. applicable_units는 아래 [모집단위] 목록에 있는 이름만 그대로 쓴다. 직렬 전체에 해당하면 빈 배열.
5. 일반 신입 모집단위 기준으로 정리한다. 보훈·장애·사회형평·고졸 등 별도 조건 모집단위만 unit_notes로 적는다.
   일반 모집단위에는 unit_notes를 만들지 않는다 (지역인재 비율 같은 선발 방식은 지원 자격이 아니다).
6. JSON 객체 하나만, 들여쓰기·줄바꿈 없이 한 줄로 출력한다. 설명 문장은 쓰지 않는다.
7. 짧게: name은 60자 이내. 가점 자격증은 이름을 하나씩 나열하지 말고 가능하면 items × grades로 묶는다.
8. 빠짐없이 (요약 금지): 직렬(직군)마다 지원 가능 전공·자격증이나 가점표가 따로 있으면 직렬마다 따로 적고,
   표에 나온 종목은 하나도 빼지 말고 전부 items에 적는다. 모든 직렬이 정말 같은 표를 쓸 때만 track을 비우고 한 번 적는다.
   전공 제한이 있는 직렬은 그 직렬의 major 항목을 꼭 적는다 (전공자 또는 자격증이면 major와 accepted 둘 다).

items의 kind
- "major": 지원 가능 전공. 전공·학력 제한이 없으면 "unrestricted": true
- "accepted": 전공자가 아니어도 이 자격증이 있으면 지원 가능 (전공 또는 자격증)
- "required": 이 자격증이 반드시 있어야 지원 가능 (명시된 경우만)
- "bonus": 자격증 가점. "points"(숫자)와 "unit"("점" 또는 "%", 배점의 n%면 "%")를 적는다. 등급별로 점수가 다르면 항목을 나눈다
- accepted·required·bonus는 "match"를 적는다:
  {{"names":["전기기사","정보처리기사"]}} 처럼 자격증 이름 나열, 또는
  {{"items":["전기","전기공사"],"grades":["기사","산업기사"]}} 처럼 종목 × 등급(기술사·기능장·기사·산업기사·기능사)

형식
{{"scope":"정리한 직렬들","items":[{{"kind":"","track":"","name":"사람이 읽는 한 줄 설명","points":0,"unrestricted":false,
"match":{{}},"applicable_units":[],"evidence":[]}}],
"bonus_rule":{{"text":"가점 인정 개수·중복 규칙","evidence":[]}} 또는 null,
"common_checks":[{{"text":"외국어 성적·병역 등 모든 지원자 공통 조건","evidence":[]}}],
"region_note":{{"text":"근무지 배치 규칙","evidence":[]}} 또는 null,
"unit_notes":[{{"pattern":"모집단위 이름에 들어가는 말 (예: 보훈, 고졸)","kind":"special 또는 condition","text":"","evidence":[]}}]}}
special = 대상자만 지원 가능한 특별전형, condition = 추가 조건이 있는 모집단위."""


def pair_inputs(pair: dict) -> tuple[dict, dict | None, list[str]]:
    """(올해 API 상세, 올해 PDF 글자 묶음 또는 None, 모집단위 이름 목록)"""
    curr = load_api_item(ROOT / pair["curr_api"])
    bundle_path = ROOT / "stage2" / f"bundle_{pair['curr_sn']}.json"
    # 글자 묶음이 없거나 PDF가 더 새것이면(다시 받은 PDF) 먼저 다시 만든다
    # (11-20 도로공사: 붙임을 이어 붙인 37쪽 PDF 대신 옛 10쪽 묶음을 읽어 자격증 목록 없이 추출됨)
    _bundle_text(ROOT, pair["curr_sn"], ROOT / pair["curr_pdf"], print)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8")) if bundle_path.exists() else None
    units = [str(name) for name in dict.fromkeys(step.get("recrutPbancTtl") for step in curr.get("steps") or []) if name]
    return curr, bundle, units


def user_prompt(pair: dict, curr: dict, bundle: dict, units: list[str]) -> str:
    all_text = bundle.get("all_text") or {}
    total = sum(len(text) for text in all_text.values())
    if total <= FULL_TEXT_LIMIT:
        pages = [(int(number), text) for number, text in all_text.items()]
    else:  # 너무 긴 공고문은 build_bundle이 고른 관련 쪽만
        pages = [(page["page"], page.get("text", "") + "\n" + page.get("tables", "")) for page in bundle.get("pages") or []]
    unit_lines = "\n".join(f"- {name} (직렬 추정: {unit_track(name)})" for name in units) or "- (API에 모집단위 정보 없음)"
    body = "\n".join(f"=== {number}쪽 ===\n{text}" for number, text in sorted(pages))
    return (
        f"[기관] {pair['institution']}\n[공고] {curr.get('recrutPbancTtl')}\n"
        f"[근무지역(API)] {curr.get('workRgnNmLst') or '없음'}\n[직무분야(API)] {curr.get('ncsCdNmLst') or '없음'}\n"
        f"[모집단위]\n{unit_lines}\n\n[공고문]\n{body}"
    )


def parse_result(text: str) -> dict:
    """AI 답에서 'items'가 있는 JSON 객체를 찾는다 (안쪽의 작은 객체를 잘못 집지 않게)."""
    decoder = json.JSONDecoder()
    for start in [index for index, char in enumerate(text) if char == "{"]:
        try:
            value, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        # match 칸의 {"items":["전기",...]}를 잘못 집지 않게: items가 항목(객체) 목록인 것만
        items = value.get("items") if isinstance(value, dict) else None
        if isinstance(items, list) and all(isinstance(item, dict) for item in items):
            return value
    salvaged = salvage_truncated(text)
    if salvaged is not None:
        return salvaged
    raise AiPipelineError("AI 답에서 items가 있는 JSON을 찾지 못했습니다.")


def salvage_truncated(text: str) -> dict | None:
    """출력 한도에 걸려 끝이 잘린 답에서 온전한 항목만 살린다 (11-19 지역난방·KPS·광해·LH).
    "items":[ 다음 객체를 하나씩 읽다가 잘린 객체에서 멈춘다. items 뒤의 칸(공통 조건 등)은 잘려서 없다."""
    start = text.find('"items"')
    bracket = text.find("[", start) if start >= 0 else -1
    if bracket < 0:
        return None
    decoder = json.JSONDecoder()
    items, index = [], bracket + 1
    while True:
        while index < len(text) and text[index] in " \n\r\t,":
            index += 1
        if index >= len(text) or text[index] != "{":
            break
        try:
            value, index = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            break  # 잘린 마지막 항목
        if isinstance(value, dict):
            items.append(value)
    if not items:
        return None
    scope = ""
    try:
        scope = json.loads(text[: start].rstrip().rstrip(",") + "}").get("scope", "")
    except json.JSONDecodeError:
        pass
    return {"scope": scope, "items": items, "_partial": True}


def _other_page(quote: str, all_text: dict) -> int | None:
    """인용문이 들어 있는 쪽이 딱 하나면 그 쪽 번호"""
    compact = re.sub(r"\s+", "", quote)
    pages = [int(number) for number, text in all_text.items() if compact and compact in re.sub(r"\s+", "", text or "")]
    return pages[0] if len(pages) == 1 else None


def checked_evidence(raw, all_text: dict, fix_pages: bool = False) -> tuple[list[dict], int]:
    """원문에 실제로 있는 인용만 남긴다. (남은 근거, 버린 개수)
    fix_pages: 그림 공고(옮겨 적은 글자)에서는 AI가 쪽수를 틀리게 적는 일이 있어(11-20 석유공사),
    인용문이 다른 한 쪽에만 있으면 그 쪽으로 고친다. 인용문 자체는 원문 대조를 통과해야 한다."""
    kept, dropped = [], 0
    for item in raw or []:
        if not isinstance(item, dict):
            dropped += 1
            continue
        evidence = {"side": "curr", "page": item.get("page"), "quote": str(item.get("quote") or "").strip()[:300]}
        if isinstance(evidence["page"], str) and evidence["page"].isdigit():
            evidence["page"] = int(evidence["page"])
        ok, _ = check_evidence(evidence, all_text)
        if not ok and fix_pages:
            page = _other_page(evidence["quote"], all_text)
            if page:
                evidence["page"] = page
                ok = True
        if ok:
            kept.append(evidence)
        else:
            dropped += 1
    return kept, dropped


GRADE_SUFFIX = ("기술사", "기능장", "산업기사", "기사", "기능사")
AT_LEAST = [  # 항목 이름의 'n 이상' → 인정 등급 (긴 말부터 확인)
    ("기능사 이상", ["기능사", "산업기사", "기사", "기능장", "기술사"]),
    ("산업기사 이상", ["산업기사", "기사", "기능장", "기술사"]),
    ("기사 이상", ["기사", "기능장", "기술사"]),
]


def names_to_items(match: dict, name: str) -> dict:
    """AI가 '산업기사 이상' 목록을 종목 이름만('전기', '전기공사') names에 적은 경우 종목 × 등급으로 바꾼다.
    (11-19 한수원: 이 때문에 전기기사 보유자도 지원 가능 자격증으로 인정되지 않음)
    등급이 붙은 이름(전기기사)이나 면허·외국어 등은 names에 그대로 둔다."""
    names = match.get("names") or []
    grades = next((value for phrase, value in AT_LEAST if phrase in name), None)
    if not names or not grades or match.get("items"):
        return match
    def is_profession(value: str) -> bool:  # 변호사·세무사·건축사 같은 전문 자격 (단 '비파괴검사'는 종목)
        return value.endswith("사") and not value.endswith("검사")
    bare = [value for value in names if not value.endswith(GRADE_SUFFIX) and not is_profession(value)
            and not any(word in value for word in ("면허", "급", "점", "자격"))]
    if not bare:
        return match
    kept = [value for value in names if value not in bare]
    converted = {"items": bare, "grades": grades}
    if kept:
        converted["names"] = kept
    return converted


def clean_result(raw: dict, all_text: dict, units: list[str], fix_pages: bool = False) -> tuple[dict, dict]:
    """AI 결과를 핵심 3곳 조건 파일과 같은 형식으로 다듬고 근거를 대조한다. (결과, 통계)"""
    stats = {"items_kept": 0, "items_dropped": 0, "quotes_kept": 0, "quotes_dropped": 0}

    def note(block):
        if not isinstance(block, dict) or not block.get("text"):
            return None
        evidence, dropped = checked_evidence(block.get("evidence"), all_text, fix_pages)
        stats["quotes_kept"] += len(evidence)
        stats["quotes_dropped"] += dropped
        return {"text": str(block["text"]), "evidence": evidence} if evidence else None

    items = []
    for item in raw.get("items") or []:
        if not isinstance(item, dict) or item.get("kind") not in KINDS or not item.get("name"):
            stats["items_dropped"] += 1
            continue
        evidence, dropped = checked_evidence(item.get("evidence"), all_text, fix_pages)
        stats["quotes_kept"] += len(evidence)
        stats["quotes_dropped"] += dropped
        if not evidence:
            stats["items_dropped"] += 1
            continue
        cleaned = {"kind": item["kind"], "name": str(item["name"]), "evidence": evidence,
                   "applicable_units": [name for name in item.get("applicable_units") or [] if name in units]}
        if item.get("track") in TRACKS:
            cleaned["track"] = item["track"]
        if item["kind"] == "major" and item.get("unrestricted") is True:
            cleaned["unrestricted"] = True
        if item["kind"] in {"accepted", "required", "bonus"}:
            match = item.get("match") if isinstance(item.get("match"), dict) else {}
            match = {key: [str(value) for value in match.get(key) or []] for key in ("names", "items", "grades") if match.get(key)}
            match = names_to_items(match, cleaned["name"])
            if "grades" in match:  # 규격에 없는 등급(예: '1급')은 빼고, 종목만 남으면 판정 못 하므로 뺀다
                match["grades"] = [grade for grade in match["grades"] if grade in GRADES]
                if not match["grades"]:
                    match.pop("grades")
                    match.pop("items", None)
            if not match:
                stats["items_dropped"] += 1
                continue
            cleaned["match"] = match
        if item["kind"] == "bonus":
            try:
                cleaned["points"] = float(item.get("points"))
            except (TypeError, ValueError):
                stats["items_dropped"] += 1
                continue
            if cleaned["points"].is_integer():
                cleaned["points"] = int(cleaned["points"])
            # '배점의 10%'처럼 퍼센트 가점 (11-19 주택도시보증공사 '필기 배점의 0.3%')
            cleaned["unit"] = "%" if ("%" in cleaned["name"] or str(item.get("unit")) == "%") else "점"
        items.append(cleaned)
        stats["items_kept"] += 1

    unit_notes = []
    for item in raw.get("unit_notes") or []:
        # '일반' 모집단위에 붙은 메모는 버린다: 붙이면 일반 모집 전체가 '애매'가 됨 (11-19 서부발전 '(일반)' 지역인재 메모)
        if (isinstance(item, dict) and item.get("pattern") and item.get("kind") in {"special", "condition"}
                and "일반" not in str(item["pattern"])):
            block = note(item)
            unit_notes.append({"pattern": str(item["pattern"]), "kind": item["kind"],
                               "text": str(item.get("text") or ""), "evidence": block["evidence"] if block else []})
    result = {
        "partial": bool(raw.get("_partial")),  # True면 답이 잘려서 앞부분 항목만 살린 것 (공통 조건 등 빠짐)
        "scope": str(raw.get("scope") or ""),
        "items": items,
        "bonus_rule": note(raw.get("bonus_rule")),
        "common_checks": [block for block in (note(item) for item in raw.get("common_checks") or []) if block],
        "region_note": note(raw.get("region_note")),
        "unit_notes": unit_notes,
    }
    return result, stats


def save(out: Path, pair: dict, model: str, result: dict) -> None:
    out.write_text(json.dumps({
        "pair_id": pair["pair_id"],
        "reviewed_at": date.today().isoformat(),
        "reviewer": f"AI 자동 추출({model}), 인용 원문 대조 통과분만 · 사람 확인 전",
        **result,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def cost(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICES.get(model, PRICES[DEFAULT_MODEL])
    return input_tokens / 1e6 * price_in + output_tokens / 1e6 * price_out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="자동 비교 기관의 지원 자격·가점 AI 추출 (T045)")
    parser.add_argument("--run", action="store_true", help="실제로 AI 호출 (없으면 비용 계산만)")
    parser.add_argument("--only", nargs="*", help="이 기관만 (이름)")
    parser.add_argument("--model", default=DEFAULT_MODEL, choices=sorted(PRICES))
    parser.add_argument("--max-cost", type=float, default=2.0, help="누적 비용 상한(달러)")
    parser.add_argument("--force", action="store_true", help="이미 뽑은 기관도 다시")
    parser.add_argument("--from-raw", action="store_true", help="AI를 부르지 않고 저장된 답 원본(raw/)으로 다시 정리")
    args = parser.parse_args(argv)

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key and args.from_raw:
        key = "from-raw"  # AI를 부르지 않음
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY가 없습니다. PowerShell에서 $env:ANTHROPIC_API_KEY = \"키\" 를 먼저 입력하세요.")
    client = AnthropicClient(key)
    pairs = all_pairs(ROOT)  # 30곳 전부 (핵심 3곳 포함, 11-19부터 같은 방법)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    usage_path = OUT_DIR / "usage.json"
    usage = json.loads(usage_path.read_text(encoding="utf-8")) if usage_path.exists() else []

    total_in = total_cost = 0.0
    planned = 0
    for pair in pairs:
        if args.only and pair["institution"] not in args.only:
            continue
        prefix = str(pair["pair_id"]).split("-", 1)[0]
        name = pair["institution"]
        out = OUT_DIR / f"{prefix}_requirements.json"
        if out.exists() and not args.force and not args.from_raw:
            saved = json.loads(out.read_text(encoding="utf-8"))
            saved_pair = saved.get("pair_id")
            if saved_pair == pair["pair_id"] and saved.get("items"):
                print(f"  {name}: 이미 뽑음 → 건너뜀 (--force면 다시)")
                continue
            print(f"  {name}: 저장된 추출이 비었거나 예전 공고({saved_pair}) 것 → 다시 뽑음")
        curr, bundle, units = pair_inputs(pair)
        if args.from_raw:
            raw_path = RAW_DIR / f"{prefix}.txt"
            if not raw_path.exists() or not bundle:
                continue
            try:
                raw = parse_result(raw_path.read_text(encoding="utf-8"))
            except AiPipelineError as exc:
                print(f"  {name}: {exc}")
                continue
            result, stats = clean_result(raw, bundle.get("all_text") or {}, units, bundle.get("source") == "ocr")
            save(out, pair, args.model, result)
            print(f"  {name}: (원본에서{', 잘린 답 앞부분만' if result['partial'] else ''}) 항목 {stats['items_kept']}개 저장 (버림 {stats['items_dropped']}) · "
                  f"인용 통과 {stats['quotes_kept']} / 버림 {stats['quotes_dropped']}")
            continue
        if not bundle:
            print(f"  {name}: 올해 공고문 PDF 없음 → 건너뜀 (그림·HWP 공고문)")
            continue
        prompt = user_prompt(pair, curr, bundle, units)
        try:
            tokens = client.count_tokens(model=args.model, system=SYSTEM, user=prompt)
        except ModelClientError as exc:
            raise SystemExit(f"토큰 세기 실패: {exc}") from None
        estimate = cost(args.model, tokens, OUTPUT_GUESS)
        planned += 1
        total_in += tokens

        if not args.run:
            print(f"  {name}: 입력 {tokens:,}토큰 → 예상 ${estimate:.3f}")
            total_cost += estimate
            continue
        if total_cost + estimate > args.max_cost:
            print(f"\n누적 비용이 상한 ${args.max_cost}를 넘을 것 같아 멈춤 (지금까지 ${total_cost:.3f})")
            break
        print(f"  {name}: 입력 {tokens:,}토큰 · AI가 읽는 중 (1~3분, 창을 건드리지 마세요)...", flush=True)
        try:
            # Sonnet 5.5는 기본으로 답하기 전에 '생각'하고, 그 토큰도 출력 한도·요금에 들어간다
            # (11-19 한전: 답 2천 토큰인데 출력 24,000으로 잘림, 한수원: 생각만 하다 빈 답). between_tools = 가장 낮은 생각 설정
            response = client.complete(model=args.model, system=SYSTEM, user=prompt, max_tokens=MAX_OUTPUT,
                                       thinking=THINKING.get(args.model))
        except Exception as exc:  # noqa: BLE001 - 한 기관 실패는 기록하고 계속
            print(f"  {name}: 실패 → {str(exc)[:150]}")
            continue
        spent = cost(args.model, response.input_tokens or tokens, response.output_tokens or 0)
        total_cost += spent
        # 받은 답 원본은 항상 남긴다 (정리 단계 문제는 --from-raw로 돈 안 쓰고 다시 처리)
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        (RAW_DIR / f"{prefix}.txt").write_text(response.text, encoding="utf-8")
        if response.stop_reason == "max_tokens":
            print(f"  {name}: 답이 출력 한도({MAX_OUTPUT:,}토큰)에 걸려 잘림 → 저장 안 함 · ${spent:.3f} (원본: {RAW_DIR.name}/{prefix}.txt)")
            continue
        try:
            raw = parse_result(response.text)
        except AiPipelineError as exc:
            print(f"  {name}: {exc} → 저장 안 함 · ${spent:.3f} (원본: {RAW_DIR.name}/{prefix}.txt)")
            continue
        result, stats = clean_result(raw, bundle.get("all_text") or {}, units, bundle.get("source") == "ocr")
        save(out, pair, args.model, result)
        if not result["items"]:
            print(f"  {name}: 주의 - 근거가 확인된 항목이 하나도 없음 (원본: {RAW_DIR.name}/{prefix}.txt)")
        usage.append({"date": date.today().isoformat(), "institution": name, "pair_id": pair["pair_id"],
                      "model": args.model, "input_tokens": response.input_tokens, "output_tokens": response.output_tokens,
                      "cost_usd": round(spent, 4), **stats})
        usage_path.write_text(json.dumps(usage, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {name}: 항목 {stats['items_kept']}개 저장 (버림 {stats['items_dropped']}) · "
              f"인용 통과 {stats['quotes_kept']} / 버림 {stats['quotes_dropped']} · ${spent:.3f}")

    if args.from_raw:
        print("\n원본으로 다시 정리 끝 (AI 호출 없음). 다음: .\\.venv\\Scripts\\python.exe tools\\build_auto_reports.py")
        return
    if args.run:
        print(f"\n실제 사용 ${total_cost:.3f} (기록: evaluation/ai_extracted/usage.json)")
        print("다음: .\\.venv\\Scripts\\python.exe tools\\build_auto_reports.py")
    else:
        print(f"\n대상 {planned}곳 · 입력 합계 {int(total_in):,}토큰 · 출력은 곳당 {OUTPUT_GUESS:,}토큰으로 가정")
        for model in sorted(PRICES):
            print(f"  {model}: 예상 약 ${cost(model, int(total_in), OUTPUT_GUESS * planned):.2f}")
        print("실제 추출: --run 을 붙여 실행 (먼저 --only 기관이름 으로 한 곳 시험 추천)")


if __name__ == "__main__":
    main()
