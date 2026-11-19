from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[2]
REPORT_PAGE = "app/pages/report.py"


def _open_report_page():
    """첫 화면은 '내 조건 입력'이므로 비교 화면 테스트는 페이지를 바꿔서 연다."""
    return AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=10).run().switch_page(REPORT_PAGE).run()


def test_kepco_report_opens_with_verified_changes_and_evidence():
    app = _open_report_page()

    assert not app.exception
    assert any("공채레이더" in item.value for item in app.markdown)
    assert any("한국전력공사 채용공고 비교" in item.value for item in app.markdown)
    assert any("지원 대상 기업: 한국전력공사" in item.value for item in app.markdown)
    assert any("현재 지원 공고 (2026)" in item.value for item in app.markdown)
    assert any("비교 기준 공고 (2025)" in item.value for item in app.markdown)
    assert any("2026년도 하반기" in item.value for item in app.markdown)
    assert any("2025년도 하반기" in item.value for item in app.markdown)
    # 원문 확인 13건 중 청렴 Auditor 가점(017)과 적용연도(018)는 같은 변경이라 카드 1장으로 세고,
    # 어학성적 응시일 기준(009)은 날짜만 바뀐 항목이라 '이번 공고 한눈에 보기'로 옮긴다.
    assert any("11건" in item.value for item in app.metric)
    assert any("이번 공고 한눈에 보기" in item.value for item in app.subheader)
    assert any("접수기간:** 2026.09.02 ~ 2026.09.16" in item.value for item in app.markdown)
    assert any("청년청렴 Auditor 우수활동자 가점 신설" in item.value for item in app.markdown)
    assert any("421" in item.value and "490" in item.value for item in app.markdown)
    assert any("숫자로 보는 핵심 변화" in item.value for item in app.subheader)
    assert any("공고 전체 선발인원" in item.label and item.value == "490명" for item in app.metric)
    # 기준일·유효기간, 우대사항, 전형별 구성, 직렬별 인원
    assert len(app.dataframe) == 4
    assert len(app.download_button) == 2
    assert len(app.selectbox[0].options) == 3
    assert app.selectbox[1].options == ["선택 안 함", "현재 공고 (2026)", "비교 공고 (2025)"]
    assert len(app.expander) >= 2

    app.selectbox[1].set_value("현재 공고 (2026)").run()
    assert not app.exception


def test_review_required_candidates_are_hidden_by_default():
    app = _open_report_page()

    visible_text = " ".join(item.value for item in app.markdown)
    assert "전남광주" not in visible_text
    assert len(app.toggle) == 1

    app.toggle[0].set_value(True).run()
    visible_text = " ".join(item.value for item in app.markdown)
    assert "API 직무 목록에서 ‘기계’ 항목이 빠짐" in visible_text
    assert "NCS는 직무 분류표입니다" in visible_text


def test_user_can_switch_company_without_treating_candidates_as_confirmed():
    app = _open_report_page()

    app.selectbox[0].set_value("khnp-2025-2026-round3").run()

    assert not app.exception
    assert any("한국수력원자력 채용공고 비교" in item.value for item in app.markdown)
    assert any("0건" in item.value for item in app.metric)
    assert any("PDF 원문 대조가 아직 끝나지 않았습니다" in item.value for item in app.warning)
    visible_text = " ".join(item.value for item in app.markdown)
    assert "2025: 총 139명" in visible_text
    assert "일반전형 120명" in visible_text
    assert "2026: 총 229명" in visible_text
    assert "보훈특별전형 20명" in visible_text

    app.toggle[0].set_value(True).run()
    visible_text = " ".join(item.value for item in app.markdown)
    assert "전체 채용인원 증가: 421명 → 490명" not in visible_text
    assert "자기소개서 제출 시점 변경: 입사지원 시 → 면접 대상자만" in visible_text
    assert "관련 문구 3개를 묶음" in " ".join(item.value for item in app.caption)
    assert "우대 대상 추가: 체험형인턴 우수인턴 (필기 가점 5점)" in visible_text
    assert "일반전형 가점 대상 목록" in visible_text
    assert any("새로 들어감" in item.value and "체험형인턴 우수인턴" in item.value for item in app.markdown)
    assert 'class="diff-removed"' in visible_text
    assert 'class="diff-added"' in visible_text


def test_conditions_to_matches_to_report_flow_without_personal_data():
    app = AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=10).run()

    assert not app.exception
    assert any("내 조건으로 공고 찾기" in item.value for item in app.markdown)
    # 입력 칸은 직렬·지역·자격증 세 개뿐이고 이름·연락처 같은 입력은 없다
    assert len(app.text_input) == 0
    assert len(app.number_input) == 0
    assert [item.label.split(" (")[0] for item in list(app.selectbox) + list(app.multiselect)] == [
        "희망 직렬", "희망 근무 지역", "보유 자격증"
    ]

    app.selectbox[0].set_value("전기")
    app.multiselect[0].set_value(["부산", "울산"])
    app.multiselect[1].set_value(["전기기사"])
    [button for button in app.button if button.label == "공고 찾기"][0].click().run()

    assert not app.exception
    assert any("내 조건에 맞는 공고" in item.value for item in app.markdown)
    assert any(item.value == "조건에 맞는 공고 2건" for item in app.subheader)
    assert any(item.value == "희망 지역에 근무지가 없는 공고 1건" for item in app.subheader)
    text = " ".join(item.value for item in app.markdown)
    assert "지원 가능" in text
    assert "전기기사: 배전(일반) 10점, 송변전(일반) 10점" in text
    assert "작년 대비 대표 변경:** 전체 채용인원 증가: 421명 → 490명 (원문 확인)" in text

    [button for button in app.button if button.key == "open-kepco-2025-2026-h2"][0].click().run()
    assert not app.exception
    assert any("한국전력공사 채용공고 비교" in item.value for item in app.markdown)


def test_matches_page_without_condition_asks_for_input():
    app = AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=10).run()
    app.switch_page("app/pages/matches.py").run()

    assert not app.exception
    assert any("먼저 희망 직렬·지역·자격증을 입력해 주세요" in item.value for item in app.warning)

