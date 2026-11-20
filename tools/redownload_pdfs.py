# -*- coding: utf-8 -*-
"""
공고문 PDF만 다시 받기 (API 호출 없음, 인증키 필요 없음)

이미 저장한 data/api/api_detail_<번호>.json에서 공고문 첨부 번호를 읽는다.
그 번호로 새 다운로드 주소(www.alio.go.kr/download/download.json?fileNo=...)에서 받는다.
- 첨부가 PDF면 그대로 data/pdf/<번호>.pdf로 저장
- 첨부가 ZIP이면 안에서 공고문 PDF를 꺼내 저장
- 이미 진짜 PDF가 있으면 건너뜀. 가짜(웹페이지) 파일은 지움
- 그림(PNG/JPG)·한글(HWP) 첨부는 PDF 원문 기능에서 빠짐(기록만)

실행: .\\.venv\\Scripts\\python.exe tools\\redownload_pdfs.py
그다음: .\\.venv\\Scripts\\python.exe tools\\build_auto_reports.py
"""
from __future__ import annotations

from difflib import SequenceMatcher
import io
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from collect_institutions import download_attachment, normalize_title  # noqa: E402

# ZIP 안에 공고문이 여러 개일 때: 일반 신입 공채 공고문을 고른다
MAIN_WORDS = re.compile(r"일반|신입|공채|대졸")
SIDE_WORDS = re.compile(r"별정|보훈|연구직|고졸|경력|장애|계약|기간제|특수|체험형")


def is_pdf(body: bytes) -> bool:
    return body[:5] == b"%PDF-"


def zip_name(info: zipfile.ZipInfo) -> str:
    """ZIP 안 한글 파일 이름 복원 (윈도우에서 만든 ZIP은 cp949)"""
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode("cp437").decode("cp949")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def zip_score(name: str, title: str) -> float:
    """ZIP 안 PDF 점수: 일반·신입·공채·대졸 +2, '일반' +1 더,
    별정·보훈·장애·연구직·고졸 등 하나당 -2(단 '일반'이 같이 있으면 감점 없음, 예: '(일반·보훈)'),
    '공고' +1, 공고 제목과 비슷할수록 +0~1"""
    score = 2.0 if MAIN_WORDS.search(name) else 0.0
    if "일반" in name:
        score += 1.0
    else:
        score -= 2.0 * len(SIDE_WORDS.findall(name))
    score += 1.0 if "공고" in name else 0.0
    score += SequenceMatcher(None, normalize_title(name), normalize_title(title)).ratio()
    return score


def pdf_from_zip(body: bytes, title: str = "") -> tuple[bytes | None, str]:
    """ZIP에서 공고문 PDF 고르기 (점수가 가장 높은 PDF). 후보 목록도 함께 돌려준다."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(body))
    except zipfile.BadZipFile:
        return None, "ZIP을 열 수 없음"
    pdfs = [info for info in archive.infolist() if zip_name(info).lower().endswith(".pdf")]
    if not pdfs:
        names = ", ".join(zip_name(info) for info in archive.infolist())[:150]
        return None, f"ZIP 안에 PDF 없음({names})"
    # 붙임 파일('…_붙임서류.pdf' 등)은 공고문 고르기 후보에서 빼고, 고른 공고문 뒤에 이어 붙인다
    attachments_all = [info for info in pdfs if "붙임" in Path(zip_name(info)).stem]
    candidates = [info for info in pdfs if info not in attachments_all] or pdfs
    ranked = sorted(candidates, key=lambda info: (zip_score(zip_name(info), title), info.file_size), reverse=True)
    chosen = ranked[0]
    data = archive.read(chosen)
    if not is_pdf(data):
        return None, f"ZIP 안 {zip_name(chosen)}이 PDF가 아님"
    stem = Path(zip_name(chosen)).stem
    attachments = [info for info in attachments_all if Path(zip_name(info)).stem.startswith(stem)]
    data = merge_pdfs([data] + [archive.read(info) for info in attachments])
    others = [Path(zip_name(info)).name for info in ranked[1:]]
    others += [Path(zip_name(info)).name for info in attachments_all if info not in attachments]
    note = Path(zip_name(chosen)).name
    if attachments:
        note += " + " + ", ".join(Path(zip_name(info)).name for info in attachments) + " 이어 붙임"
    if others:
        note += f" | 고르지 않은 파일: {', '.join(others)}"
    return data, note


def merge_pdfs(parts: list[bytes]) -> bytes:
    """PDF 여러 개를 순서대로 이어 붙인다 (11-20 도로공사: 공고문 + 붙임서류, 붙임 2에 자격증 목록).
    쪽 번호는 공고문 쪽 다음부터 이어진다. pypdfium2는 pdfplumber와 같이 설치돼 있다."""
    parts = [part for part in parts if is_pdf(part)]
    if len(parts) <= 1:
        return parts[0] if parts else b""
    import pypdfium2 as pdfium

    merged = pdfium.PdfDocument(parts[0])
    for part in parts[1:]:
        merged.import_pages(pdfium.PdfDocument(part))
    out = io.BytesIO()
    merged.save(out)
    return out.getvalue()


def notice_file(sn: str) -> tuple[dict | None, str]:
    path = ROOT / f"data/api/api_detail_{sn}.json"
    if not path.exists():
        return None, ""
    data = json.loads(path.read_text(encoding="utf-8"))
    item = data["result"][0] if isinstance(data.get("result"), list) else data.get("result")
    files = [file for file in item.get("files") or [] if file.get("atchFileType") == "A"]
    return (files[0] if files else None), str(item.get("recrutPbancTtl") or "")


def fetch(sn: str) -> str:
    """번호 하나 처리 → 결과 한 줄"""
    pdf = ROOT / f"data/pdf/{sn}.pdf"
    file, title = notice_file(sn)
    if not file:
        return "공고문 첨부 없음"
    name = str(file.get("atchFileNm", ""))
    lower = name.lower()
    # ZIP 첨부는 고르는 기준이 바뀔 수 있어 매번 다시 꺼낸다(몇 개뿐이라 금방 끝남)
    if not lower.endswith(".zip") and pdf.exists() and is_pdf(pdf.read_bytes()):
        return "이미 진짜 PDF 있음"
    if pdf.exists() and not is_pdf(pdf.read_bytes()):
        pdf.unlink()  # 가짜(웹페이지) 파일
    if not (lower.endswith(".pdf") or lower.endswith(".zip")):
        return f"PDF 아님({name}) → 원문 기능 제외"
    try:
        body = download_attachment(file["url"])
    except Exception as exc:  # noqa: BLE001
        return f"실패: {exc}"
    if lower.endswith(".zip"):
        data, note = pdf_from_zip(body, title) if body[:2] == b"PK" else (None, f"ZIP 대신 다른 내용({len(body):,}바이트)")
        if not data:
            return f"실패: {note}"
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(data)
        return f"저장(ZIP에서 꺼냄: {note}, {len(data):,}바이트)"
    if not is_pdf(body):
        return f"실패: PDF 대신 다른 내용({len(body):,}바이트)"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(body)
    return f"저장({len(body):,}바이트)"


def main() -> None:
    pairs = json.loads((ROOT / "config/auto_pairs.json").read_text(encoding="utf-8"))["pairs"]
    saved = failed = skipped = 0
    for pair in pairs:
        for side, key in (("작년", "prev_api"), ("올해", "curr_api")):
            sn = Path(pair[key]).stem.rsplit("_", 1)[-1]
            result = fetch(sn)
            print(f"{pair['institution']} {side} {sn}: {result}")
            if result.startswith("저장") or result.startswith("이미"):
                saved += 1
            elif result.startswith("실패"):
                failed += 1
            else:
                skipped += 1
    print(f"\n진짜 PDF {saved}개 / 실패 {failed}개 / PDF 아닌 첨부라 제외 {skipped}개")
    print("다음: .\\.venv\\Scripts\\python.exe tools\\build_auto_reports.py")


if __name__ == "__main__":
    main()
