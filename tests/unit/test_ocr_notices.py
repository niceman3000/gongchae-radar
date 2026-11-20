"""그림·스캔 공고문 옮기기 (tools/ocr_notices.py) 규칙 테스트 — AI 호출 없음."""

from __future__ import annotations

import io
import json
from pathlib import Path

from PIL import Image, ImageDraw

from tools import ocr_notices as ocr
from tools.build_auto_reports import _bundle_text


def _lined_image(width: int, height: int) -> Image.Image:
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    for y in range(20, height, 40):
        draw.text((20, y), f"line {y}", fill="black")
    return image


def test_tiles_are_small_and_cut_between_lines() -> None:
    tiles = ocr.tiles_from_image(_lined_image(1800, 6000))
    assert all(tile.width == ocr.TILE_WIDTH for tile in tiles)
    assert all(tile.height <= ocr.TILE_HEIGHT + ocr.SEARCH_BAND // 2 for tile in tiles)
    assert sum(tile.height for tile in tiles) == round(6000 * ocr.TILE_WIDTH / 1800)
    # 자른 줄(조각 맨 아래 줄)에는 글자가 없다
    for tile in tiles[:-1]:
        bottom = tile.convert("L").crop((0, tile.height - 1, tile.width, tile.height))
        assert min(bottom.tobytes()) > 170


def test_small_image_is_not_enlarged() -> None:
    tiles = ocr.tiles_from_image(_lined_image(800, 500))
    assert [tile.size for tile in tiles] == [(800, 500)]


def test_scanned_pdf_page_becomes_images() -> None:
    buffer = io.BytesIO()
    _lined_image(900, 1270).save(buffer, "PDF")
    parts = ocr.pdf_parts(buffer.getvalue(), force_image=False)
    assert len(parts) == 1 and len(parts[0]["images"]) == 2


def test_kind_of_detects_file_types() -> None:
    assert ocr.kind_of(b"%PDF-1.7") == "pdf"
    assert ocr.kind_of(b"\x89PNG\r\n\x1a\n....") == "png"
    assert ocr.kind_of(b"\xff\xd8\xff\xe0") == "jpg"
    assert ocr.kind_of(b"\xd0\xcf\x11\xe0\xa1\xb1") == "hwp"
    assert ocr.kind_of(b"PK\x03\x04") == "zip"
    assert ocr.kind_of(b"<!DOCTYPE html>") == "unknown"


def test_hwp_paragraph_text_skips_control_codes() -> None:
    raw = "가점".encode("utf-16-le") + (11).to_bytes(2, "little") + b"\x00" * 14 + "표".encode("utf-16-le")
    assert ocr._para_text(raw) == "가점표"


def test_ocr_bundle_is_used_without_pdf(tmp_path: Path) -> None:
    (tmp_path / "stage2").mkdir()
    bundle = {"source": "ocr", "all_text": {"1": "토익 700점 이상"}}
    (tmp_path / "stage2" / "bundle_1.json").write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
    assert _bundle_text(tmp_path, "1", tmp_path / "data" / "pdf" / "1.pdf") == {"1": "토익 700점 이상"}


def test_hwp_private_symbols_do_not_break_saving(monkeypatch) -> None:
    """광해광업 HWP: 한글 전용 기호(서로게이트 두 글자)가 있어도 UTF-8로 저장된다."""
    monkeypatch.setattr(ocr, "_para_text", lambda raw: "가점\udb80\udeb1 10점")
    import olefile  # noqa: F401 - hwp_text가 쓰는지만 확인

    text = "가점\udb80\udeb1 10점".encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")
    cleaned = "".join(char for char in text if not (0xE000 <= ord(char) <= 0xF8FF or ord(char) >= 0xF0000))
    assert cleaned == "가점 10점"
    cleaned.encode("utf-8")


def test_long_image_tiles_become_separate_pages(tmp_path: Path, monkeypatch) -> None:
    """11-20 석유공사: 긴 그림 하나를 1쪽으로 두면 AI가 쪽수를 지어냄 → 그림 조각마다 한 쪽."""
    monkeypatch.setattr(ocr, "OCR_DIR", tmp_path / "ocr")
    monkeypatch.setattr(ocr, "STAGE2", tmp_path / "stage2")
    (tmp_path / "stage2").mkdir()
    folder = tmp_path / "ocr" / "9"
    folder.mkdir(parents=True)
    for name, text in (("t001_1", "가"), ("t001_2", "나"), ("t002_1", "스캔 위"), ("t002_2", "스캔 아래")):
        (folder / f"{name}.txt").write_text(text, encoding="utf-8")
    manifest = {"sn": "9", "institution": "시험", "side": "curr", "reason": "test", "pages": [
        {"page": 1, "from": "공고.png", "tiles": [{"file": "t001_1.png"}, {"file": "t001_2.png"}]},
        {"page": 2, "from": "스캔.pdf", "tiles": [{"file": "t002_1.png"}, {"file": "t002_2.png"}]},
    ]}
    ocr.write_bundle(manifest, "claude-haiku-5-5")
    bundle = json.loads((tmp_path / "stage2" / "bundle_9.json").read_text(encoding="utf-8"))
    assert bundle["all_text"] == {"1": "가", "2": "나", "3": "스캔 위\n스캔 아래"}
    assert bundle["page_from"]["2"] == "공고.png (조각 2/2)"
