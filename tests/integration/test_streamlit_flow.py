from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[2]


def test_kepco_report_opens_with_verified_changes_and_evidence():
    app = AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=10).run()

    assert not app.exception
    assert any("공채레이더" in item.value for item in app.markdown)
    assert any("한국전력공사 채용공고 비교" in item.value for item in app.markdown)
    assert any("지원 대상 기업: 한국전력공사" in item.value for item in app.markdown)
    assert any("현재 지원 공고 (2026)" in item.value for item in app.markdown)
    assert any("비교 기준 공고 (2025)" in item.value for item in app.markdown)
    assert any("2026년도 하반기" in item.value for item in app.markdown)
    assert any("2025년도 하반기" in item.value for item in app.markdown)
    assert any("13건" in item.value for item in app.metric)
    assert any("421" in item.value and "490" in item.value for item in app.markdown)
    assert len(app.expander) >= 2


def test_review_required_candidates_are_hidden_by_default():
    app = AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=10).run()

    visible_text = " ".join(item.value for item in app.markdown)
    assert "전남광주" not in visible_text
    assert len(app.toggle) == 1
