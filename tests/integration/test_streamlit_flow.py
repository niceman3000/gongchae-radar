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
    assert any("숫자로 보는 핵심 변화" in item.value for item in app.subheader)
    assert any("전체 채용인원" in item.label and item.value == "490명" for item in app.metric)
    assert len(app.dataframe) == 1
    assert len(app.download_button) == 2
    assert len(app.selectbox[0].options) == 3
    assert app.selectbox[1].options == ["선택 안 함", "현재 공고 (2026)", "비교 공고 (2025)"]
    assert len(app.expander) >= 2

    app.selectbox[1].set_value("현재 공고 (2026)").run()
    assert not app.exception


def test_review_required_candidates_are_hidden_by_default():
    app = AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=10).run()

    visible_text = " ".join(item.value for item in app.markdown)
    assert "전남광주" not in visible_text
    assert len(app.toggle) == 1

    app.toggle[0].set_value(True).run()
    visible_text = " ".join(item.value for item in app.markdown)
    assert "API 직무 목록에서 ‘기계’ 항목이 빠짐" in visible_text
    assert "NCS는 직무 분류표입니다" in visible_text


def test_user_can_switch_company_without_treating_candidates_as_confirmed():
    app = AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=10).run()

    app.selectbox[0].set_value("khnp-2025-2026-round3").run()

    assert not app.exception
    assert any("한국수력원자력 채용공고 비교" in item.value for item in app.markdown)
    assert any("0건" in item.value for item in app.metric)
    assert any("PDF 원문 대조가 아직 끝나지 않았습니다" in item.value for item in app.warning)

    app.toggle[0].set_value(True).run()
    visible_text = " ".join(item.value for item in app.markdown)
    assert "전체 채용인원 증가: 421명 → 490명" not in visible_text
