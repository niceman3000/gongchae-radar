# -*- coding: utf-8 -*-
"""
공기업 30곳 공고 수집 (tasks.md T042, 표준 라이브러리만 사용)

하는 일
  1. config/institutions.json의 기관마다 기관코드(pblntInstCd)를 목록 API에서 이름으로 찾아 채운다
  2. 기관마다 최근 공고 중 '신입 + 정규직'만 남긴다
  3. 가장 최근 공고(올해)와, 그보다 약 1년 앞선 제목이 가장 비슷한 공고(작년)를 짝짓는다
  4. 두 공고의 상세 JSON과 공고문 PDF를 data/api, data/pdf에 저장한다 (HWP면 건너뛰고 기록)
  5. config/auto_pairs.json(짝 목록)과 data/api/collect_log.json(기관별 결과)을 쓴다

실행 (프로젝트 최상위 폴더, PowerShell)
  $env:JOB_API_KEY = "data.go.kr 일반 인증키(Decoding)"
  .\\.venv\\Scripts\\python.exe tools\\collect_institutions.py
  # 일부만: --only 한국도로공사 한국가스공사   / PDF 없이: --skip-download

그다음
  .\\.venv\\Scripts\\python.exe tools\\build_auto_reports.py

인증키는 화면·파일에 남기지 않는다. data.go.kr 개발계정은 하루 1,000회까지라 기본 호출 상한을 900회로 둔다
(예상 사용량 약 300회: 기관코드 찾기 최대 150회 + 기관별 목록·상세 27곳 × 약 4회). 핵심 3곳(tier=verified)은 config/demo_pairs.json을 그대로 쓰므로 건너뛴다.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
import json
import os
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

BASE = "http://apis.data.go.kr/1051000/recruitment"
ROOT = Path(__file__).resolve().parent.parent
ROWS = 100
PREV_WINDOW = (300, 430)      # 작년 공고: 올해 공고 접수 시작일보다 300~430일 앞
WIDE_WINDOW = (270, 560)      # 위 범위에 없으면 넓혀서 다시 찾는다 (같은 해 상·하반기끼리는 짝짓지 않게 270일부터)
RECENT_DAYS = 800             # 기관별 공고는 최근 약 2년치만 본다


# ---------------------------------------------------------------- API
class ApiClient:
    """정부 채용정보 API 호출. 호출 수를 세고 인증키를 오류 메시지에서 가린다."""

    def __init__(self, key: str, max_calls: int = 900) -> None:
        self.key = key
        self.max_calls = max_calls
        self.calls = 0

    def get(self, path: str, **params) -> dict:
        if self.calls >= self.max_calls:
            raise RuntimeError(f"API 호출 상한 {self.max_calls}회에 도달했습니다. --max-calls로 늘릴 수 있습니다.")
        self.calls += 1
        query = {"serviceKey": self.key, "resultType": "json", **params}
        url = f"{BASE}/{path}?" + urllib.parse.urlencode(query)
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - 인증키를 가리기 위해 모두 받는다
            raise RuntimeError(str(exc).replace(self.key, "***")) from None
        if str(data.get("resultCode")) != "200":
            raise RuntimeError(f"API 오류 {data.get('resultCode')}: {data.get('resultMsg')}")
        return data

    def download(self, url: str) -> bytes:
        return download_attachment(url)


# 2026-11-19: 옛 주소(opendata.alio.go.kr/recruit/downloadAtchFile)는 사이트 첫 화면으로 튕긴다.
# 잡알리오 공고 페이지의 첨부 링크는 www.alio.go.kr/download/download.json?fileNo=<같은 번호> 이다.
NEW_DOWNLOAD = "https://www.alio.go.kr/download/download.json?fileNo={no}"
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def attachment_urls(url: str) -> list[str]:
    """API가 준 첨부 주소 → 시도할 주소 목록 (새 주소 먼저, 옛 주소는 마지막)"""
    match = re.search(r"recrutAtchFileNo=(\d+)", url or "")
    urls = [NEW_DOWNLOAD.format(no=match.group(1))] if match else []
    return urls + [url]


def download_attachment(url: str) -> bytes:
    """첨부파일 내려받기. 진짜 PDF를 주는 주소가 나오면 그 내용을, 아니면 마지막으로 받은 내용을 돌려준다."""
    body = b""
    for candidate in attachment_urls(url):
        request = urllib.request.Request(candidate, headers={
            "User-Agent": BROWSER_UA, "Referer": "https://job.alio.go.kr/", "Accept": "*/*"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
        except Exception:  # noqa: BLE001 - 다음 주소로
            continue
        if body[:5] == b"%PDF-" or body[:2] == b"PK":
            return body
    return body


# ---------------------------------------------------------------- 규칙 (테스트 대상)
def normalize_name(name: str) -> str:
    """기관 이름 비교용: 공백·괄호·'주식회사' 제거"""
    text = re.sub(r"\(주\)|㈜|주식회사", "", name or "")
    return re.sub(r"[^\w]", "", text).lower()


def institution_matches(inst_nm: str, institution: dict) -> bool:
    names = [institution["name"], *institution.get("aliases", [])]
    return normalize_name(inst_nm) in {normalize_name(name) for name in names}


def normalize_title(title: str) -> str:
    """제목 비교용: 연도·차수 같은 숫자를 지운다. 상·하반기와 대졸·고졸 같은 말은 남긴다."""
    text = re.sub(r"\d+", " ", title or "")
    text = re.sub(r"년도|년|제\s*차|차\b", " ", text)
    return re.sub(r"\s+", "", text)


def parse_ymd(value) -> date | None:
    text = str(value or "")
    if re.fullmatch(r"\d{8}", text):
        return datetime.strptime(text, "%Y%m%d").date()
    return None


# 제목에 이런 말이 있으면 신입 공채가 아니다 (2026-11-19 첫 수집에서 잡힌 단기노무원·일용원·기간제 등)
EXCLUDE_TITLE = re.compile(
    r"기간제|계약직|일용|단기|노무|대체|육아휴직|인턴|위촉|무기계약|공무직|촉탁|시니어|도우미|"
    r"전문임기|별정직|청원경찰|특수직|수탁|후생|경력직|임원|비상임|감사|사외이사"
)


def hire_types(item: dict) -> set[str]:
    return {value.strip() for value in str(item.get("hireTypeNmLst") or "").split(",") if value.strip()}


# 대상자만 지원하는 특별전형 공고는 제외. 단 '일반'이 같이 있으면 공채로 남긴다
# (예: '(일반/보훈)', '일반전형 및 장애인 제한경쟁')
SPECIAL_ONLY_TITLE = re.compile(r"\(보훈\)|보훈\s*특별|사회형평|장애인\s*(제한|전용)|상생가치형")
# 제외어가 있어도 이런 말이 같이 있으면 공채로 본다 (예: '일반직(신입, 경력), 연구직 및 별정직 채용')
MAIN_HIRE_TITLE = re.compile(r"신입|공개\s*채용|공채|대졸|고졸|일반직|신규\s*채용|채용형")
# 공기업 공채는 '청년인턴(채용형)'(인턴 후 정규직 전환)으로 등록되는 경우가 많다 (도로공사·코레일·LH·조폐공사 등)
MAIN_HIRE_TYPES = {"정규직", "청년인턴(채용형)"}
MIN_SIZE_RATIO = 0.3  # 작년 공고는 인원이 올해의 30% 이상인 것을 우선


def is_target(item: dict) -> bool:
    """신입 공채만: 고용형태에 '정규직' 또는 '청년인턴(채용형)'이 있고(비정규직·체험형만은 X),
    대체인력 공고·특별전형 전용·제외어 공고는 빼되 제목에 공채를 뜻하는 말이 있으면 남긴다"""
    title = str(item.get("recrutPbancTtl") or "")
    main_words = bool(MAIN_HIRE_TITLE.search(title))
    return (
        "신입" in str(item.get("recrutSeNm") or "")
        and bool(hire_types(item) & MAIN_HIRE_TYPES)
        and (str(item.get("replmprYn") or "N").upper() != "Y" or main_words)
        and not (SPECIAL_ONLY_TITLE.search(title) and "일반" not in title)
        and (not EXCLUDE_TITLE.search(title) or main_words)
    )


def headcount(item: dict) -> int:
    try:
        return int(item.get("recrutNope") or 0)
    except (TypeError, ValueError):
        return 0


def pick_pair(notices: list[dict]) -> tuple[dict | None, dict | None, str | None]:
    """(올해, 작년, 짝이 없을 때 사유). 올해 = 접수 시작일이 가장 늦은 공고."""
    dated = [item for item in notices if parse_ymd(item.get("pbancBgngYmd"))]
    if not dated:
        return None, None, "신입·정규직 공고 없음"
    # 올해 공고 = 가장 최근 공고일로부터 1년 안의 공고 중, 그 안에서 가장 큰 공채 인원의 절반 이상인
    #            공고 가운데 가장 최근 것 (작은 공고는 건너뛰고, 큰 공채 중에서는 최신을 고른다)
    latest = max(parse_ymd(item["pbancBgngYmd"]) for item in dated)
    recent = [item for item in dated if (latest - parse_ymd(item["pbancBgngYmd"])).days <= 365]
    biggest = max(headcount(item) for item in recent)
    large = [item for item in recent if headcount(item) >= biggest / 2] or recent
    curr = max(large, key=lambda item: (parse_ymd(item["pbancBgngYmd"]), headcount(item)))
    curr_day = parse_ymd(curr["pbancBgngYmd"])
    title = normalize_title(curr.get("recrutPbancTtl"))

    def size_ok(item: dict) -> bool:
        return headcount(item) >= MIN_SIZE_RATIO * headcount(curr)

    # 인원 규모가 비슷한 공고를 먼저 1년 전후에서, 다음 넓은 기간에서 찾고, 그래도 없으면 규모와 상관없이 찾는다
    for low, high, need_size in ((*PREV_WINDOW, True), (*WIDE_WINDOW, True), (*PREV_WINDOW, False), (*WIDE_WINDOW, False)):
        candidates = [
            item for item in dated
            if item is not curr and low <= (curr_day - parse_ymd(item["pbancBgngYmd"])).days <= high
            and (size_ok(item) or not need_size)
        ]
        if candidates:
            # 작년 공고 = 제목이 비슷하고(가중 2) 인원 규모가 올해와 비슷한(가중 1) 공고
            def score(item: dict) -> tuple:
                similarity = SequenceMatcher(None, title, normalize_title(item.get("recrutPbancTtl"))).ratio()
                size = min(headcount(item), headcount(curr)) / max(headcount(item), headcount(curr), 1)
                return (2 * similarity + size, -abs((curr_day - parse_ymd(item["pbancBgngYmd"])).days - 365))

            prev = max(candidates, key=score)
            return curr, prev, None
    return curr, None, "약 1년 전 비교 공고 없음"


# ---------------------------------------------------------------- 수집 단계
def resolve_codes(client: ApiClient, institutions: list[dict], max_pages: int, log=print) -> None:
    """기관코드가 없는 기관을 목록 API의 최신 공고부터 넘기며 이름으로 찾는다."""
    missing = [item for item in institutions if not item.get("pblntInstCd")]
    page = 1
    while missing and page <= max_pages:
        result = client.get("list", pageNo=page, numOfRows=ROWS).get("result") or []
        if not result:
            break
        for notice in result:
            for item in list(missing):
                if institution_matches(str(notice.get("instNm") or ""), item):
                    item["pblntInstCd"] = notice.get("pblntInstCd")
                    missing.remove(item)
                    log(f"  기관코드 찾음: {item['name']} = {item['pblntInstCd']} (목록 {page}쪽)")
        page += 1
    for item in missing:
        log(f"  기관코드 못 찾음: {item['name']} (최근 {max_pages * ROWS}건 안에 공고 없음)")


def list_notices(client: ApiClient, code: str, today: date, max_pages: int = 30, reuse: bool = False) -> list[dict]:
    """기관의 최근 공고(마감 포함). 오래된 공고만 나오는 쪽에 이르면 멈춘다.

    받은 목록 원본은 data/api/list_<기관코드>.json에 저장한다. reuse=True면 API 대신 그 파일을 쓴다
    (고르는 규칙만 바꿔 다시 돌릴 때 API 호출을 아끼기 위해).
    """
    cutoff = today - timedelta(days=RECENT_DAYS)
    cache = ROOT / f"data/api/list_{code}.json"
    if reuse and cache.exists():
        output = json.loads(cache.read_text(encoding="utf-8"))
        days = [day for day in (parse_ymd(item.get("pbancBgngYmd")) for item in output) if day]
        # 저장된 목록이 2년 전까지 닿았거나 끝까지 받은 목록이면 그대로 쓴다. 중간에 잘린 목록이면 다시 받는다.
        if (days and min(days) < cutoff) or len(output) % ROWS != 0:
            return [item for item in output if (parse_ymd(item.get("pbancBgngYmd")) or cutoff) >= cutoff]
    output = []
    for page in range(1, max_pages + 1):
        result = client.get("list", pageNo=page, numOfRows=ROWS, pblntInstCd=code).get("result") or []
        if not result:
            break
        output.extend(result)
        days = [parse_ymd(item.get("pbancBgngYmd")) for item in result]
        if all(day is None or day < cutoff for day in days):
            break
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
    return [item for item in output if (parse_ymd(item.get("pbancBgngYmd")) or cutoff) >= cutoff]


def save_detail(client: ApiClient, sn: str, download: bool) -> tuple[dict, str | None]:
    """상세 JSON 저장, 공고문 PDF 저장. (상세, PDF를 못 받은 사유)"""
    data = client.get("detail", sn=sn)
    (ROOT / "data/api").mkdir(parents=True, exist_ok=True)
    (ROOT / f"data/api/api_detail_{sn}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    item = data["result"][0] if isinstance(data.get("result"), list) else data.get("result")
    notices = [file for file in item.get("files") or [] if file.get("atchFileType") == "A"]
    if not notices:
        return item, f"공고문 첨부 없음: {item.get('nonatchRsn') or '사유 미기재'}"
    file = notices[0]
    if not str(file.get("atchFileNm", "")).lower().endswith(".pdf"):
        return item, f"공고문이 PDF가 아님({file.get('atchFileNm')}) → PDF 원문 기능 제외"
    if not download:
        return item, "PDF 내려받기 건너뜀(--skip-download)"
    pdf = ROOT / f"data/pdf/{sn}.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    if pdf.exists() and pdf.read_bytes()[:5] == b"%PDF-":
        return item, None
    try:
        body = client.download(file["url"])
    except Exception as exc:  # noqa: BLE001 - 다운로드 실패는 기록만 하고 계속
        return item, f"PDF 다운로드 실패: {exc}"
    if body[:5] != b"%PDF-":
        # 2026-11-19: 사이트가 PDF 대신 '청년 일자리 지원 서비스' 웹페이지(8,333바이트)를 준 적이 있다
        if pdf.exists():
            pdf.unlink()
        return item, f"PDF 다운로드 실패: PDF 대신 다른 내용({len(body):,}바이트)을 받음"
    pdf.write_bytes(body)
    return item, None


def make_pair(institution: dict, prev: dict, curr: dict, collected_at: str) -> dict:
    code = str(institution["pblntInstCd"]).lower()
    prev_sn, curr_sn = str(prev["recrutPblntSn"]), str(curr["recrutPblntSn"])
    return {
        "pair_id": f"{code}-{prev_sn}-{curr_sn}",
        "pair_name": f"{institution['name']} · {str(curr.get('recrutPbancTtl') or '')[:40]}",
        "institution": institution["name"],
        "category": institution["category"],
        "tier": "auto",
        "track_focus": ["전체"],
        "prev_sn": prev_sn,
        "curr_sn": curr_sn,
        "prev_api": f"data/api/api_detail_{prev_sn}.json",
        "curr_api": f"data/api/api_detail_{curr_sn}.json",
        "prev_pdf": f"data/pdf/{prev_sn}.pdf",
        "curr_pdf": f"data/pdf/{curr_sn}.pdf",
        "collected_at": collected_at,
    }


def collect(client: ApiClient, institutions: list[dict], *, only: list[str] | None = None,
            download: bool = True, max_pages: int = 150, today: date | None = None,
            reuse_lists: bool = False, log=print) -> dict:
    today = today or date.today()
    targets = [item for item in institutions if item.get("tier") != "verified"]
    if only:
        targets = [item for item in targets if item["name"] in only]
    log(f"대상 {len(targets)}곳")
    resolve_codes(client, targets, max_pages, log)

    pairs, skipped, details = [], [], []
    for institution in targets:
        name = institution["name"]
        row = {"institution": name, "category": institution["category"], "pblntInstCd": institution.get("pblntInstCd")}
        if not institution.get("pblntInstCd"):
            skipped.append({**row, "reason": "기관코드 못 찾음"})
            continue
        try:
            notices = [item for item in list_notices(client, institution["pblntInstCd"], today, reuse=reuse_lists)
                       if is_target(item)]
            curr, prev, reason = pick_pair(notices)
            row["target_notices"] = len(notices)
            if not curr or not prev:
                skipped.append({**row, "reason": reason, "curr_sn": (curr or {}).get("recrutPblntSn")})
                log(f"  {name}: 건너뜀 - {reason}")
                continue
            pdf_notes = {}
            for side, notice in (("prev", prev), ("curr", curr)):
                _, note = save_detail(client, str(notice["recrutPblntSn"]), download)
                if note:
                    pdf_notes[side] = note
            pair = make_pair(institution, prev, curr, today.isoformat())
            if pdf_notes:
                pair["pdf_notes"] = pdf_notes
            pairs.append(pair)
            details.append({**row, "prev": pair["prev_sn"], "curr": pair["curr_sn"], "pdf_notes": pdf_notes,
                            "prev_title": prev.get("recrutPbancTtl"), "curr_title": curr.get("recrutPbancTtl"),
                            "prev_headcount": headcount(prev), "curr_headcount": headcount(curr)})
            log(f"  {name}: {pair['prev_sn']} → {pair['curr_sn']} ({headcount(curr)}명) {curr.get('recrutPbancTtl')}"
                + (f" ({'; '.join(pdf_notes.values())})" if pdf_notes else ""))
        except RuntimeError as exc:
            skipped.append({**row, "reason": f"API 오류: {exc}"})
            log(f"  {name}: API 오류 - {exc}")
    return {"pairs": pairs, "skipped": skipped, "details": details, "api_calls": client.calls}


# ---------------------------------------------------------------- 실행
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="공기업 30곳 공고 수집 (T042)")
    parser.add_argument("--only", nargs="*", help="이 기관만 수집 (이름)")
    parser.add_argument("--skip-download", action="store_true", help="공고문 PDF는 받지 않음")
    parser.add_argument("--max-pages", type=int, default=150, help="기관코드 찾을 때 넘길 목록 쪽 수 (쪽당 100건)")
    parser.add_argument("--reuse-lists", action="store_true",
                        help="저장해 둔 목록(data/api/list_*.json)으로 다시 고르기 (목록 API 호출 안 함)")
    parser.add_argument("--max-calls", type=int, default=900,
                        help="API 호출 상한 (data.go.kr 개발계정은 하루 1,000회)")
    args = parser.parse_args(argv)

    key = os.environ.get("JOB_API_KEY", "").strip()
    if not key:
        raise SystemExit("JOB_API_KEY 환경변수가 없습니다. 파일 맨 위의 실행 방법을 보세요.")

    config_path = ROOT / "config/institutions.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    client = ApiClient(key, args.max_calls)
    result = collect(client, config["institutions"], only=args.only, download=not args.skip_download,
                     max_pages=args.max_pages, reuse_lists=args.reuse_lists)

    # 찾은 기관코드를 명단 파일에 저장 (다음 실행부터 다시 찾지 않음)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    pairs_path = ROOT / "config/auto_pairs.json"
    old = json.loads(pairs_path.read_text(encoding="utf-8")) if pairs_path.exists() else {"pairs": []}
    merged = {pair["institution"]: pair for pair in old.get("pairs", [])}
    for row in result["skipped"]:
        if not str(row.get("reason", "")).startswith("API 오류"):
            merged.pop(row["institution"], None)  # 새 규칙으로 짝이 없으면 예전 짝도 버린다
    merged.update({pair["institution"]: pair for pair in result["pairs"]})
    pairs_path.write_text(
        json.dumps({"schema_version": "1.0.0", "pairs": list(merged.values())}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    log_path = ROOT / "data/api/collect_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps({"collected_at": date.today().isoformat(), **result}, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"\n짝 {len(result['pairs'])}곳 저장 → config/auto_pairs.json (누적 {len(merged)}곳)")
    print(f"건너뜀 {len(result['skipped'])}곳, API 호출 {result['api_calls']}회 → data/api/collect_log.json")
    print("다음: .\\.venv\\Scripts\\python.exe tools\\build_auto_reports.py")


if __name__ == "__main__":
    sys.exit(main())
