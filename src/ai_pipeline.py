"""공고 PDF 구조화와 문구 분류를 수행하는 테스트 가능한 AI 파이프라인."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any, Mapping, Protocol

from src.build_bundle import build as build_bundle
from src.evidence import check_evidence
from src.model_client import ModelResponse
from src.report_builder import build_from_files, load_json


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXTRACT_MODEL = "claude-sonnet-5"
DEFAULT_CLASSIFY_MODEL = "claude-haiku-4-5"


class AiPipelineError(RuntimeError):
    """AI 결과가 없거나 계약을 지키지 못했을 때 발생한다."""


class ModelClient(Protocol):
    usage: list[dict[str, object]]

    def complete(
        self, *, model: str, system: str, user: str, max_tokens: int
    ) -> ModelResponse: ...


EXTRACT_SYSTEM = """너는 공공기관 채용공고문을 구조화하는 도구다.
1. 제공된 공고문 안의 사실만 사용하고 추측하지 않는다.
2. 모든 값에 해당 PDF 쪽수(page)와 그 쪽에서 그대로 복사한 짧은 문장(quote)을 붙인다.
3. 찾을 수 없으면 null 또는 빈 배열을 사용한다.
4. 숫자, 지원자격, 자격증 가점, 전형 배점과 배수만 추출한다.
5. JSON 객체 하나만 출력한다.

형식:
{"units":[{"unit_name":"","track":"","headcount_total":{"value":0,"evidence":{"page":1,"quote":""}},
"headcount_by_region":[{"region":"","value":0,"evidence":{"page":1,"quote":""}}],
"required_qualifications":[{"item":"","evidence":{"page":1,"quote":""}}],
"certificate_bonus":[{"certificate":"","points":0,"stage":"","evidence":{"page":1,"quote":""}}],
"stages":[{"stage":"","components":[{"name":"","points":0}],"pass_multiple":"","pass_rule":"",
"evidence":{"page":1,"quote":""}}]}],"notice_level":{"schedule":[],"advance_notices":[]}}"""

CLASSIFY_SYSTEM = """너는 작년과 올해 채용공고 문구의 차이를 취업준비생에게 설명한다.
각 입력에 대해 label은 '실질 변경' 또는 '표현 변경', who_is_affected는 영향받는 지원자,
one_line은 전문용어를 풀어 쓴 60자 이내 설명, confidence는 '높음' 또는 '낮음'으로 작성한다.
입력에 없는 사실은 추가하지 않는다. JSON 배열 하나만 출력한다."""


def parse_json_response(text: str, expected: type) -> Any:
    decoder = json.JSONDecoder()
    for match in re.finditer(r"[\[{]", text):
        try:
            value, _ = decoder.raw_decode(text[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(value, expected):
            return value
    raise AiPipelineError("AI 응답에서 올바른 JSON을 찾지 못했습니다.")


def pages_prompt(bundle: Mapping[str, Any]) -> str:
    sections = []
    for page in bundle.get("pages") or []:
        page_number = page["page"]
        sections.append(f"=== {page_number}쪽 ===\n{page.get('text') or ''}")
        tables = str(page.get("tables") or "").strip()
        if tables:
            sections.append(f"--- {page_number}쪽 표 ---\n{tables}")
    return "[공고문]\n" + "\n".join(sections)


def verify_evidence_tree(value: Any, all_text: Mapping[str, str]) -> tuple[Any, dict[str, int]]:
    checked = deepcopy(value)
    stats: Counter[str] = Counter()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            evidence = node.get("evidence")
            if isinstance(evidence, dict) and evidence.get("quote"):
                valid, reason = check_evidence(evidence, all_text)
                evidence["verified"] = valid
                evidence["verification"] = "쪽 일치" if valid else reason
                stats["verified" if valid else "rejected"] += 1
            for item in node.values():
                walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(checked)
    return checked, dict(stats)


def extract_notice(
    bundle: Mapping[str, Any], client: ModelClient, *, model: str = DEFAULT_EXTRACT_MODEL
) -> dict[str, Any]:
    response = client.complete(
        model=model,
        system=EXTRACT_SYSTEM,
        user=pages_prompt(bundle),
        max_tokens=8000,
    )
    extracted = parse_json_response(response.text, dict)
    if not isinstance(extracted.get("units"), list):
        raise AiPipelineError("AI 추출 결과에 units 배열이 없습니다.")
    checked, stats = verify_evidence_tree(extracted, bundle.get("all_text") or {})
    checked["_meta"] = {
        "model": model,
        "sent_pages": list(bundle.get("sent_pages") or []),
        "evidence_check": stats,
    }
    return checked


def classify_text_changes(
    changes: list[Mapping[str, Any]],
    client: ModelClient,
    *,
    model: str = DEFAULT_CLASSIFY_MODEL,
) -> list[dict[str, Any]]:
    text_changes = [item for item in changes if item.get("type") == "text"]
    if not text_changes:
        return []
    payload = [
        {"id": index, "field": item.get("field"), "prev": item.get("prev"), "curr": item.get("curr")}
        for index, item in enumerate(text_changes)
    ]
    response = client.complete(
        model=model,
        system=CLASSIFY_SYSTEM,
        user=json.dumps(payload, ensure_ascii=False),
        max_tokens=2500,
    )
    output = parse_json_response(response.text, list)
    merged = []
    for item in output:
        if not isinstance(item, dict) or not isinstance(item.get("id"), int):
            continue
        index = item["id"]
        if index < 0 or index >= len(payload):
            continue
        if item.get("label") not in {"실질 변경", "표현 변경"}:
            continue
        if item.get("confidence") not in {"높음", "낮음"}:
            item["confidence"] = "낮음"
        merged.append({**item, **{key: payload[index][key] for key in ("field", "prev", "curr")}})
    return merged


def _find_stage1(stage1: Mapping[str, Any], prev_sn: str, curr_sn: str) -> Mapping[str, Any]:
    for result in stage1.values():
        if str((result.get("prev") or {}).get("sn")) == prev_sn and str(
            (result.get("curr") or {}).get("sn")
        ) == curr_sn:
            return result
    raise AiPipelineError(f"stage1 결과에서 {prev_sn}-{curr_sn} 공고쌍을 찾지 못했습니다.")


def run_pair(
    pair_id: str,
    client: ModelClient,
    *,
    root: Path = ROOT,
    extract_model: str = DEFAULT_EXTRACT_MODEL,
    classify_model: str = DEFAULT_CLASSIFY_MODEL,
) -> list[Path]:
    config_path = root / "config" / "demo_pairs.json"
    config = load_json(config_path)
    pair = next((item for item in config["pairs"] if item["pair_id"] == pair_id), None)
    if pair is None:
        raise AiPipelineError(f"설정에서 공고쌍을 찾지 못했습니다: {pair_id}")

    stage2_dir = root / "stage2"
    stage2_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for sn, pdf_key in ((str(pair["prev_sn"]), "prev_pdf"), (str(pair["curr_sn"]), "curr_pdf")):
        bundle_path = stage2_dir / f"bundle_{sn}.json"
        if bundle_path.exists():
            bundle = load_json(bundle_path)
        else:
            bundle = build_bundle(str(root / pair[pdf_key]))
            bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
            written.append(bundle_path)
        extracted = extract_notice(bundle, client, model=extract_model)
        extract_path = stage2_dir / f"extract_{sn}.json"
        extract_path.write_text(json.dumps(extracted, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(extract_path)

    stage1 = load_json(root / "results" / "stage1_result.json")
    stage1_pair = _find_stage1(stage1, str(pair["prev_sn"]), str(pair["curr_sn"]))
    classifications = classify_text_changes(
        list(stage1_pair.get("changes") or []), client, model=classify_model
    )
    prefix = str(pair_id).split("-", 1)[0]
    class_path = stage2_dir / f"text_class_{prefix}.json"
    class_path.write_text(json.dumps(classifications, ensure_ascii=False, indent=2), encoding="utf-8")
    written.append(class_path)

    usage_path = stage2_dir / f"usage_{prefix}.json"
    usage_path.write_text(json.dumps(client.usage, ensure_ascii=False, indent=2), encoding="utf-8")
    written.append(usage_path)

    written.extend(build_from_files(config_path=config_path, pair_id=pair_id))
    return written
