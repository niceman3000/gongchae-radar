# -*- coding: utf-8 -*-
"""
그림(PNG·JPG)·스캔 PDF·한글(HWP) 공고문을 글자로 옮기기 (11-20)

왜: 공항공사·석유공사·인천공항·SR·강원랜드·한전KDN·마사회 등은 공고문이 그림 파일이거나
    스캔 PDF라서 PDF 글자 읽기(pdfplumber)로 글자가 안 나온다 → 지원 자격 뽑기·질문 기능이 안 됐다.
어떻게:
  1) (무료) 공고문 첨부를 받아 data/ocr/<공고번호>/ 에 저장하고, 그림을 AI가 읽기 좋은 크기로 자른다.
     - 긴 그림은 가로 1200px로 줄이고, 세로 약 950px마다 '빈 줄(글자 없는 가로줄)'에서 자른다 → 글자가 잘리지 않게
     - 스캔 PDF는 쪽마다 그림으로 바꿔 위·아래로 자른다 (1쪽 = 1쪽 그대로)
     - 글자가 있는 PDF(붙임 자격증 점수표 등)는 AI 없이 글자를 그대로 읽는다
     - 한글(HWP) 파일은 AI 없이 파일 안의 글자를 그대로 꺼낸다 (olefile 필요: pip install olefile)
     - 비용만 계산해서 보여준다 (그림 크기로 입력 토큰 계산 + 출력 토큰 추정)
  2) (유료, --run) 잘린 그림마다 Claude에게 "보이는 글자를 그대로 옮겨 적기"를 시킨다.
     결과는 조각마다 .txt로 저장(중간에 멈춰도 이어서 함) → stage2/bundle_<번호>.json (source="ocr")
     이후 지원 자격 뽑기(extract_requirements.py)·질문 기능은 이 글자를 '원문'으로 쓴다.
     주의: 인용 대조는 'AI가 옮겨 적은 글자'와 하는 것이다(그림 원본과의 대조 아님) → 화면에 표시

실행 (프로젝트 최상위 폴더, PowerShell)
  1) 준비 + 비용 계산 (돈 안 듦):   .\\.venv\\Scripts\\python.exe tools\\ocr_notices.py
  2) 실행:                          .\\.venv\\Scripts\\python.exe tools\\ocr_notices.py --run
     한 곳만:  --only 한국석유공사      올해 공고만: --side curr      모델: --model claude-haiku-5-5
  그다음:
     .\\.venv\\Scripts\\python.exe tools\\extract_requirements.py --run --only 한국석유공사 ...
     .\\.venv\\Scripts\\python.exe tools\\build_auto_reports.py
"""
from __future__ import annotations

import argparse
import base64
from datetime import date
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import urllib.request
import zipfile
import zlib

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from collect_institutions import BROWSER_UA, attachment_urls  # noqa: E402
from redownload_pdfs import zip_name, zip_score  # noqa: E402

OCR_DIR = ROOT / "data" / "ocr"
STAGE2 = ROOT / "stage2"
DEFAULT_MODEL = "claude-sonnet-5-5"
PRICES = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}  # 달러/100만 토큰 (입력, 출력)
THINKING = {"claude-sonnet-5-5": {"type": "between_tools"}}
TILE_WIDTH = 1200        # 그림 가로 (이보다 크면 줄임, 작으면 그대로)
TILE_HEIGHT = 950        # 조각 세로 목표 → 1200x950 = 114만 화소 (AI가 줄이지 않는 크기 안)
SEARCH_BAND = 250        # 자를 줄을 찾는 범위 (목표 위쪽 250px 안에서 가장 하얀 줄)
OUTPUT_GUESS = 1100      # 비용 계산 때 가정하는 조각 하나 출력 토큰
PROMPT_TOKENS = 350      # 지시문 토큰 (대략)
MAX_OUTPUT = 6000
TEXT_PAGE_MIN = 200      # PDF 한 쪽 글자가 이보다 많으면 글자 PDF로 보고 AI 없이 읽는다
SCAN_AVG_MAX = 100       # 묶음의 쪽당 평균 글자가 이보다 적으면 스캔 PDF로 본다

# 강제로 그림으로 읽을 공고 (PDF에 글자는 있지만 중요한 표가 그림)
FORCE = {"293232": "한국마사회 올해: 가점·자격 표가 그림"}
# 공고문 말고 같이 읽을 첨부 (자격증 가점표, 지역인재 기준, 세부 전형 방법 등)
EXTRA_WORDS = re.compile(r"가점|자격증|점수표|전형\s*방법|환산|우대|지역\s*인재")
SKIP_WORDS = re.compile(r"입사\s*지원|지원서|직무\s*기술|직무\s*설명|자기\s*소개|반환|결격|피해자|FAQ|증빙")

SYSTEM = """너는 채용공고문 그림을 글자로 옮겨 적는 도구다. 규칙
1. 그림에 보이는 글자를 위에서 아래로, 보이는 그대로 옮겨 적는다. 고치기·요약·설명·번역 금지.
2. 표는 한 행을 한 줄로 '| 칸 | 칸 | 칸 |' 형식으로 적는다. 합쳐진 칸은 내용을 한 번만 적는다.
3. 번호·기호(○, -, ※, ①, 가., 1)) 와 숫자·점수·날짜는 반드시 그대로 적는다.
4. 읽을 수 없는 글자는 [?]로 적는다. 글자가 없는 그림(로고·사진)은 건너뛴다.
5. 그림 가장자리에서 잘린 줄은 보이는 만큼만 적는다.
6. 옮겨 적은 글만 출력한다. 앞뒤 설명, 코드블록 표시 없이."""


# ------------------------------------------------------------------ 대상 고르기
def all_pairs() -> list[dict]:
    from tools.build_auto_reports import all_pairs as pairs  # 30곳 (핵심 3곳 포함)

    return pairs(ROOT)


def is_pdf(body: bytes) -> bool:
    return body[:5] == b"%PDF-"


def kind_of(body: bytes) -> str:
    if is_pdf(body):
        return "pdf"
    if body[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if body[:3] == b"\xff\xd8\xff":
        return "jpg"
    if body[:4] == b"\xd0\xcf\x11\xe0":
        return "hwp"  # 한글 97 이후 형식(OLE)
    if body[:2] == b"PK":
        return "zip"  # ZIP 또는 한글 HWPX
    return "unknown"


def bundle_info(sn: str) -> dict | None:
    path = STAGE2 / f"bundle_{sn}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def target_reason(sn: str, pdf: Path) -> str | None:
    """이 공고를 그림으로 읽어야 하는 이유 (없으면 None)"""
    if sn in FORCE:
        return FORCE[sn]
    if not pdf.exists() or not is_pdf(pdf.read_bytes()[:5]):
        return "공고문이 PDF가 아님(그림·한글·ZIP)"
    bundle = bundle_info(sn)
    if bundle and bundle.get("source") not in ("ocr", "hwp"):
        texts = list((bundle.get("all_text") or {}).values())
        avg = sum(len(text.strip()) for text in texts) / max(1, len(texts))
        if avg < SCAN_AVG_MAX:
            return f"스캔 PDF(쪽당 글자 {avg:.0f}자)"
    return None


def targets(only: list[str] | None, side_filter: str | None) -> list[dict]:
    out = []
    for pair in all_pairs():
        if only and pair["institution"] not in only:
            continue
        for side in ("prev", "curr"):
            if side_filter and side != side_filter:
                continue
            sn = str(pair[f"{side}_sn"])
            pdf = ROOT / pair[f"{side}_pdf"]
            bundle = bundle_info(sn)
            done = bool(bundle and bundle.get("source") in ("ocr", "hwp"))
            reason = target_reason(sn, pdf) if not done else (bundle.get("ocr_reason") or "이미 옮김")
            if reason:
                out.append({"institution": pair["institution"], "side": side, "sn": sn, "pdf": pdf,
                            "reason": reason, "done": done})
    return out


# ------------------------------------------------------------------ 받기
def api_files(sn: str) -> list[dict]:
    path = ROOT / f"data/api/api_detail_{sn}.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    item = data["result"][0] if isinstance(data.get("result"), list) else data.get("result")
    return list(item.get("files") or [])


def download_any(url: str) -> bytes:
    """첨부 받기: PDF·그림·한글·ZIP 중 하나가 오면 그 내용 (collect_institutions.download_attachment는 PDF·ZIP만 받음)"""
    last = b""
    for candidate in attachment_urls(url):
        request = urllib.request.Request(candidate, headers={
            "User-Agent": BROWSER_UA, "Referer": "https://job.alio.go.kr/", "Accept": "*/*"})
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                last = response.read()
        except Exception:  # noqa: BLE001 - 다음 주소로
            continue
        if kind_of(last) != "unknown":
            return last
    return last


def safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", name).strip() or "file"


def raw_files(target: dict, log=print) -> list[tuple[str, bytes]]:
    """(파일 이름, 내용) 목록: 공고문 먼저, 그다음 같이 읽을 첨부. 받은 파일은 raw/에 저장해 다시 받지 않는다."""
    sn = target["sn"]
    raw_dir = OCR_DIR / sn / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    out: list[tuple[str, bytes]] = []
    pdf = target["pdf"]
    files = api_files(sn)
    main_from_pdf = pdf.exists() and is_pdf(pdf.read_bytes()[:5])
    if main_from_pdf:  # 스캔 PDF·강제 대상: 이미 받은 PDF를 쓴다
        out.append((pdf.name, pdf.read_bytes()))
    wanted = []
    for file in files:
        name = str(file.get("atchFileNm") or "")
        if file.get("atchFileType") == "A" and not main_from_pdf:
            wanted.append(file)
        elif file.get("atchFileType") != "A" and EXTRA_WORDS.search(name) and not SKIP_WORDS.search(name):
            wanted.append(file)
    for file in wanted:
        name = safe_name(str(file.get("atchFileNm") or f"{file.get('recrutAtchFileNo')}"))
        cached = raw_dir / name
        if cached.exists() and kind_of(cached.read_bytes()[:8]) != "unknown":
            body = cached.read_bytes()
        else:
            body = download_any(str(file.get("url") or ""))
            if kind_of(body) == "unknown":
                log(f"    받기 실패: {name} ({len(body):,}바이트, 웹페이지 등)")
                continue
            cached.write_bytes(body)
        out.append((name, body))
    return out


# ------------------------------------------------------------------ 한글(HWP) 글자 꺼내기
def hwp_text(body: bytes) -> str:
    """HWP 5.x(OLE) 파일의 본문 글자. 표는 칸마다 줄로 나온다."""
    try:
        import olefile
    except ImportError as exc:
        raise RuntimeError("한글 파일을 읽으려면 먼저: .\\.venv\\Scripts\\python.exe -m pip install olefile") from exc
    ole = olefile.OleFileIO(io.BytesIO(body))
    header = ole.openstream("FileHeader").read()
    compressed = bool(header[36] & 1)
    sections = sorted((entry for entry in ole.listdir() if entry[0] == "BodyText"),
                      key=lambda entry: int(re.sub(r"\D", "", entry[1]) or 0))
    lines = []
    for entry in sections:
        data = ole.openstream(entry).read()
        if compressed:
            data = zlib.decompress(data, -15)
        pos = 0
        while pos + 4 <= len(data):
            head = int.from_bytes(data[pos:pos + 4], "little")
            tag, size = head & 0x3FF, (head >> 20) & 0xFFF
            pos += 4
            if size == 0xFFF:
                size = int.from_bytes(data[pos:pos + 4], "little")
                pos += 4
            if tag == 67:  # HWPTAG_PARA_TEXT
                lines.append(_para_text(data[pos:pos + size]))
            pos += size
    text = "\n".join(line for line in lines if line.strip())
    # 11-20 광해광업: 한글 전용 기호가 두 글자(서로게이트)로 나뉘어 들어와 저장할 때 오류 → 한 글자로 합치고,
    # 화면에 안 보이는 한글 전용 기호(사용자 정의 영역 글자)는 뺀다
    text = text.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")
    return "".join(char for char in text if not (0xE000 <= ord(char) <= 0xF8FF or ord(char) >= 0xF0000))


def _para_text(raw: bytes) -> str:
    chars, i = [], 0
    while i + 1 < len(raw):
        code = int.from_bytes(raw[i:i + 2], "little")
        if code >= 32:
            chars.append(chr(code))
            i += 2
        elif code in (10, 13):
            chars.append("\n")
            i += 2
        elif code == 9:  # 탭(인라인 제어, 8글자 자리)
            chars.append("\t")
            i += 16
        elif code in (0, 24, 25, 26, 27, 28, 29, 30, 31):
            if code == 30 or code == 31:
                chars.append(" ")
            i += 2
        else:  # 확장·인라인 제어 문자 (표·그림 위치 등): 8글자 자리를 건너뜀
            i += 16
    return "".join(chars)


def hwpx_text(body: bytes) -> str:
    archive = zipfile.ZipFile(io.BytesIO(body))
    names = sorted(name for name in archive.namelist() if re.match(r"Contents/section\d+\.xml", name))
    lines = []
    for name in names:
        xml = archive.read(name).decode("utf-8", "replace")
        for para in re.findall(r"<hp:p[ >].*?</hp:p>", xml, re.S):
            text = "".join(re.findall(r"<hp:t[^>]*>(.*?)</hp:t>", para, re.S))
            text = re.sub(r"<[^>]+>", "", text)
            if text.strip():
                lines.append(text)
    return "\n".join(lines)


# ------------------------------------------------------------------ 그림 자르기
def _ink_rows(gray, top: int, bottom: int) -> list[int]:
    """각 가로줄의 진한 점 개수"""
    width = gray.width
    band = gray.crop((0, top, width, bottom)).point(lambda value: 255 if value < 170 else 0)
    data = band.tobytes()
    return [data[row * width:(row + 1) * width].count(255) for row in range(bottom - top)]


def tiles_from_image(image) -> list:
    """긴 그림 → 가로 TILE_WIDTH 이하, 세로 약 TILE_HEIGHT 조각들. 글자 없는 가로줄에서 자른다."""
    image = image.convert("RGB")
    if image.width > TILE_WIDTH:
        image = image.resize((TILE_WIDTH, round(image.height * TILE_WIDTH / image.width)))
    gray = image.convert("L")
    tiles, top = [], 0
    height = image.height
    while top < height:
        if height - top <= TILE_HEIGHT + SEARCH_BAND // 2:
            cut = height
        else:
            low = top + TILE_HEIGHT - SEARCH_BAND
            ink = _ink_rows(gray, low, top + TILE_HEIGHT)
            best = min(ink)
            # 가장 하얀 줄 중 아래쪽(조각을 크게)
            cut = low + max(index for index, value in enumerate(ink) if value == best)
        tiles.append(image.crop((0, top, image.width, cut)))
        top = cut
    return tiles


def pdf_parts(body: bytes, force_image: bool) -> list[dict]:
    """PDF → 쪽마다 {'text': ...} (글자 PDF) 또는 {'images': [...]} (스캔)"""
    import pdfplumber
    import pypdfium2 as pdfium

    from src.build_bundle import table_text

    parts = []
    document = pdfium.PdfDocument(body)
    with pdfplumber.open(io.BytesIO(body)) as pdf:
        for index, page in enumerate(pdf.pages):
            page = page.dedupe_chars()
            text = (page.extract_text() or "").replace("\x00", " ")
            # 강제 대상(마사회)도 큰 그림이 없는 쪽은 글자 그대로 읽는다 (11-20: 34쪽 전부 그림으로 읽으면 $1 → 그림 있는 쪽만)
            big_image = any((image.get("width", 0) * image.get("height", 0)) > 0.1 * page.width * page.height
                            for image in page.images)
            if len(text.strip()) >= TEXT_PAGE_MIN and not (force_image and big_image):
                parts.append({"text": text + "\n" + table_text(page.extract_tables() or [])})
                continue
            pdf_page = document[index]
            width_pt = pdf_page.get_width()
            bitmap = pdf_page.render(scale=TILE_WIDTH / width_pt)
            parts.append({"images": tiles_from_image(bitmap.to_pil())})
    return parts


def file_parts(name: str, body: bytes, force_image: bool, log=print, depth: int = 0) -> list[dict]:
    """파일 하나 → 쪽 목록"""
    from PIL import Image

    kind = kind_of(body)
    if kind == "pdf":
        return pdf_parts(body, force_image)
    if kind in ("png", "jpg"):
        return [{"images": tiles_from_image(Image.open(io.BytesIO(body)))}]
    if kind == "hwp":
        return [{"text": hwp_text(body), "hwp": True}]
    if kind == "zip":
        archive = zipfile.ZipFile(io.BytesIO(body))
        if any(re.match(r"Contents/section\d+\.xml", entry) for entry in archive.namelist()):
            return [{"text": hwpx_text(body), "hwp": True}]
        if depth:
            return []
        members = [info for info in archive.infolist() if not info.is_dir()
                   and re.search(r"\.(pdf|png|jpe?g|hwpx?)$", zip_name(info), re.I)
                   and not SKIP_WORDS.search(Path(zip_name(info)).name)]
        if not members:
            log(f"    {name}: ZIP 안에 읽을 파일 없음")
            return []
        ranked = sorted(members, key=lambda info: (zip_score(zip_name(info), name), info.file_size), reverse=True)
        main = ranked[0]
        chosen = [main] + [info for info in ranked[1:] if EXTRA_WORDS.search(Path(zip_name(info)).name)
                           or "붙임" in Path(zip_name(info)).stem]
        log(f"    {name}: ZIP에서 {', '.join(Path(zip_name(info)).name for info in chosen)}")
        parts = []
        for info in chosen:
            for part in file_parts(zip_name(info), archive.read(info), force_image, log, depth + 1):
                part.setdefault("from", f"{name} › {Path(zip_name(info)).name}")
                parts.append(part)
        return parts
    log(f"    {name}: 읽을 수 없는 형식")
    return []


def prepare(target: dict, log=print) -> dict:
    """받고 자르기 → data/ocr/<번호>/manifest.json. 조각 그림은 t<쪽>_<조각>.png"""
    sn = target["sn"]
    folder = OCR_DIR / sn
    folder.mkdir(parents=True, exist_ok=True)
    force_image = sn in FORCE
    pages = []
    for name, body in raw_files(target, log):
        for part in file_parts(name, body, force_image, log):
            number = len(pages) + 1
            entry = {"page": number, "from": part.get("from", name)}
            if "images" in part:
                entry["tiles"] = []
                for tile_index, tile in enumerate(part["images"], 1):
                    tile_name = f"t{number:03d}_{tile_index}.png"
                    tile.save(folder / tile_name, optimize=True)
                    entry["tiles"].append({"file": tile_name, "width": tile.width, "height": tile.height})
            else:
                text_name = f"text{number:03d}.txt"
                (folder / text_name).write_text(part["text"], encoding="utf-8")
                entry["text_file"] = text_name
                entry["kind"] = "hwp" if part.get("hwp") else "pdf_text"
            pages.append(entry)
    manifest = {"sn": sn, "institution": target["institution"], "side": target["side"],
                "reason": target["reason"], "pages": pages}
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def tile_tokens(tile: dict) -> int:
    return math.ceil(tile["width"] * tile["height"] / 750) + PROMPT_TOKENS


def estimate(manifest: dict, model: str) -> tuple[int, int, float]:
    """(조각 수, 아직 안 옮긴 조각 수, 비용 $)"""
    price_in, price_out = PRICES[model]
    tiles = [tile for page in manifest["pages"] for tile in page.get("tiles", [])]
    todo = [tile for tile in tiles if not (OCR_DIR / manifest["sn"] / (tile["file"][:-4] + ".txt")).exists()]
    cost = sum(tile_tokens(tile) * price_in + OUTPUT_GUESS * price_out for tile in todo) / 1_000_000
    return len(tiles), len(todo), cost


# ------------------------------------------------------------------ 옮겨 적기 (유료)
def ocr_tile(client, model: str, path: Path) -> tuple[str, float, str | None]:
    image = base64.b64encode(path.read_bytes()).decode("ascii")
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image}},
               {"type": "text", "text": "이 그림(채용공고문의 한 부분)에 보이는 글자를 규칙대로 옮겨 적어라."}]
    response = client.complete(model=model, system=SYSTEM, user=content, max_tokens=MAX_OUTPUT,
                               thinking=THINKING.get(model))
    price_in, price_out = PRICES[model]
    cost = ((response.input_tokens or 0) * price_in + (response.output_tokens or 0) * price_out) / 1_000_000
    return response.text, cost, response.stop_reason


def write_bundle(manifest: dict, model: str | None) -> Path | None:
    """조각 글자가 다 모였으면 stage2/bundle_<번호>.json 만들기 (build_bundle과 같은 모양 + source 표시)"""
    folder = OCR_DIR / manifest["sn"]
    all_text, pages, kinds, page_from = {}, [], set(), {}

    def add(text: str, source: str) -> None:
        number = len(pages) + 1
        all_text[str(number)] = text
        pages.append({"page": number, "text": text, "tables": ""})
        page_from[str(number)] = source

    for page in manifest["pages"]:
        if "tiles" in page:
            texts = []
            for tile in page["tiles"]:
                txt = folder / (tile["file"][:-4] + ".txt")
                if not txt.exists():
                    return None
                texts.append(txt.read_text(encoding="utf-8"))
            kinds.add("ocr")
            # 11-20: 긴 그림 공고(PNG·JPG) 하나를 1쪽으로 두면 AI가 쪽수를 지어내 인용이 다 버려졌다(석유공사 8·29쪽).
            # 그림 파일은 조각 하나를 한 쪽으로 센다. 스캔 PDF는 PDF 쪽 그대로(위·아래 조각을 합침).
            if re.search(r"\.(png|jpe?g)$", page["from"], re.I) and len(texts) > 1:
                for index, text in enumerate(texts, 1):
                    add(text, f"{page['from']} (조각 {index}/{len(texts)})")
            else:
                add("\n".join(texts), page["from"])
        else:
            kinds.add(page.get("kind", "pdf_text"))
            add((folder / page["text_file"]).read_text(encoding="utf-8"), page["from"])
    if not pages:
        return None
    source = "ocr" if "ocr" in kinds else "hwp" if "hwp" in kinds else "attach"
    bundle = {
        "pdf": "", "source": source, "ocr_model": model if source == "ocr" else None,
        "ocr_reason": manifest["reason"], "made_at": date.today().isoformat(),
        "page_from": page_from,
        "total_pages": len(pages), "sent_pages": [page["page"] for page in pages],
        "pages": pages, "all_text": all_text,
    }
    path = STAGE2 / f"bundle_{manifest['sn']}.json"
    path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="그림·스캔·한글 공고문을 글자로 옮기기")
    parser.add_argument("--run", action="store_true", help="실제로 AI에게 옮겨 적기 시킴 (돈 듦)")
    parser.add_argument("--only", nargs="*", help="이 기관만 (이름)")
    parser.add_argument("--side", choices=["prev", "curr"], help="작년(prev) 또는 올해(curr)만")
    parser.add_argument("--model", default=os.environ.get("OCR_MODEL", DEFAULT_MODEL), choices=sorted(PRICES))
    parser.add_argument("--max-cost", type=float, default=1.5, help="이번 실행 비용 한도 $ (기본 1.5)")
    parser.add_argument("--redo", action="store_true", help="이미 옮긴 공고도 다시 준비")
    parser.add_argument("--rebundle", action="store_true",
                        help="AI 호출·다운로드 없이, 이미 옮긴 글자로 stage2 묶음만 다시 만들기 (쪽 나누기 규칙이 바뀌었을 때)")
    args = parser.parse_args(argv)

    if args.rebundle:
        for path in sorted(OCR_DIR.glob("*/manifest.json")):
            manifest = json.loads(path.read_text(encoding="utf-8"))
            old = bundle_info(manifest["sn"]) or {}
            out = write_bundle(manifest, old.get("ocr_model") or args.model)
            pages = len((bundle_info(manifest["sn"]) or {}).get("all_text") or {}) if out else 0
            print(f"- {manifest['institution']} {manifest['sn']}: {'묶음 ' + str(pages) + '쪽' if out else '조각이 덜 끝남 → 건너뜀'}")
        return

    found = targets(args.only, args.side)
    if not found:
        print("그림·스캔·한글 공고가 없습니다.")
        return
    print(f"모델 {args.model} · 대상 {len(found)}개\n")
    manifests, total = [], 0.0
    for target in found:
        if target["done"] and not args.redo:
            print(f"- {target['institution']} {target['side']} {target['sn']}: 이미 옮김 → 건너뜀 (--redo면 다시)")
            continue
        print(f"- {target['institution']} {'작년' if target['side'] == 'prev' else '올해'} {target['sn']}: {target['reason']}")
        try:
            manifest = prepare(target)
        except Exception as exc:  # noqa: BLE001 - 한 곳이 실패해도 나머지는 진행
            print(f"    준비 실패: {exc}")
            continue
        n_tiles, n_todo, cost = estimate(manifest, args.model)
        text_pages = sum(1 for page in manifest["pages"] if "text_file" in page)
        print(f"    {len(manifest['pages'])}쪽 (그림 조각 {n_tiles}개 중 남은 {n_todo}개, 글자로 바로 읽은 쪽 {text_pages}개)"
              f" · 예상 ${cost:.3f}")
        if n_tiles == 0:
            path = write_bundle(manifest, None)
            print(f"    AI 없이 완료 → {path.name if path else '내용 없음'}")
            continue
        manifests.append(manifest)
        total += cost
    other = "claude-haiku-5-5" if args.model != "claude-haiku-5-5" else DEFAULT_MODEL
    total_other = sum(estimate(manifest, other)[2] for manifest in manifests)
    print(f"\n예상 비용 합계: ${total:.2f} ({args.model}) / 참고 ${total_other:.2f} ({other})")
    print(f"그림 조각은 data/ocr/<공고번호>/ 에서 열어 볼 수 있어요.")
    if not args.run:
        print("실제로 하려면 --run 을 붙여 다시 실행 (출력 토큰은 추정이라 실제와 다를 수 있음)")
        return

    from src.model_client import AnthropicClient

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY 환경변수가 없습니다. (이 PowerShell 창에서 $env:ANTHROPIC_API_KEY = \"키\")")
    client = AnthropicClient(key)
    spent = 0.0
    usage_path = OCR_DIR / "usage.json"
    usage = json.loads(usage_path.read_text(encoding="utf-8")) if usage_path.exists() else []
    for manifest in manifests:
        folder = OCR_DIR / manifest["sn"]
        print(f"\n{manifest['institution']} {manifest['sn']} 옮겨 적는 중")
        for page in manifest["pages"]:
            for tile in page.get("tiles", []):
                txt = folder / (tile["file"][:-4] + ".txt")
                if txt.exists():
                    continue
                if spent >= args.max_cost:
                    print(f"비용 한도 ${args.max_cost} 도달 → 멈춤. 다시 실행하면 이어서 해요.")
                    usage_path.write_text(json.dumps(usage, ensure_ascii=False, indent=2), encoding="utf-8")
                    return
                try:
                    text, cost, stop = ocr_tile(client, args.model, folder / tile["file"])
                except Exception as exc:  # noqa: BLE001
                    print(f"  {tile['file']} 실패: {exc}")
                    continue
                spent += cost
                if stop == "max_tokens":
                    text += "\n[잘림: 출력 한도]"
                    print(f"  {tile['file']}: 출력 한도에 걸려 일부만 옮김")
                txt.write_text(text, encoding="utf-8")
                usage.append({"sn": manifest["sn"], "tile": tile["file"], "model": args.model,
                              "cost": round(cost, 5), "date": date.today().isoformat()})
                print(f"  {page['page']}쪽 {tile['file']} {len(text):,}자 ${cost:.4f} (누적 ${spent:.3f})")
        path = write_bundle(manifest, args.model)
        print(f"  → {path.name if path else '조각이 덜 끝남'}")
    usage_path.write_text(json.dumps(usage, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n끝. 이번 비용 ${spent:.3f} (기록: data/ocr/usage.json)")
    print("다음: extract_requirements.py --run --only <기관들> → build_auto_reports.py")


if __name__ == "__main__":
    main()
