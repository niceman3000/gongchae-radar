from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[2]
REPORT_PAGE = "app/pages/report.py"


def _open_report_page():
    """첫 화면은 '내 조건 입력'이므로 비교 화면 테스트는 페이지를 바꿔서 연다."""
    return AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=10).run().switch_page(REPORT_PAGE).run()


def test_kepco_report_opens_with_candidates_and_notice():
    """11-19부터 30곳 모두 같은 자동 과정: 손으로 쓴 제목·확정 건수 없이 후보와 안내를 보여준다."""
    app = _open_report_page()

    assert not app.exception
    assert any("한국전력공사 채용공고 비교" in item.value for item in app.markdown)
    assert any("올해 공고 (2026)" in item.value for item in app.markdown)
    assert any("작년 공고 (2025)" in item.value for item in app.markdown)
    assert any("자동으로 정리했어요" in item.value for item in app.caption)
    assert any("작년과 달라진 점" in item.value for item in app.markdown)  # 11-21 예시 3: 숫자 상자 대신 제목에 건수
    assert not app.metric
    assert any("이번 공고 한눈에 보기" in item.value for item in app.subheader)
    assert any("접수기간:** 2026.09.02 ~ 2026.09.16" in item.value for item in app.markdown)
    assert any("421" in item.value and "490" in item.value for item in app.markdown)
    assert len(app.selectbox[0].options) == 30
    assert app.selectbox[1].options == ["선택 안 함", "올해 공고 (2026)", "작년 공고 (2025)"]

    app.selectbox[1].set_value("올해 공고 (2026)").run()
    assert not app.exception


def test_candidates_are_shown_with_one_notice_and_minor_changes_folded():
    """11-21 팀원 점검 6·7·13·15번: 안내는 한 번, 숫자 변경은 증감과 함께, 이름만 바뀐 건 접어 둠"""
    app = _open_report_page()

    assert not app.toggle
    assert sum("코드로 비교해 찾은 후보" in item.value for item in app.caption) == 1
    visible_text = " ".join(item.value for item in app.markdown)
    assert "인원: 421명 → 490명" in visible_text and '<span class="up">(+69명)</span>' in visible_text
    assert "뽑는 인원이 늘었어요 (69명)" in visible_text
    assert "전기(배전, 송변전) 10배수 신설" in visible_text  # 13번: 바뀐 조각으로 제목
    assert "추가 확인 중" not in visible_text
    labels = [tab.label for tab in app.tabs]  # 11-21 예시 3: 전체 / 사소한 변경 탭
    assert any(label.startswith("전체 ") for label in labels)
    assert any(label.startswith("사소한 변경 ") for label in labels)


def test_user_can_switch_company():
    app = _open_report_page()

    app.selectbox[0].set_value("khnp-2025-2026-round3").run()
    more = [button for button in app.button if button.label.startswith("나머지 변경")]  # 전체 탭은 6건 먼저 (예시 3)
    if more:
        more[0].click().run()

    assert not app.exception
    assert any("한국수력원자력 채용공고 비교" in item.value for item in app.markdown)
    visible_text = " ".join(item.value for item in app.markdown)
    assert "421명 → 490명" not in visible_text  # 다른 기관 내용이 섞이지 않음
    assert "자기소개서" in visible_text
    assert "체험형인턴 우수인턴" in visible_text
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
    assert any("조건 맞는 공고 <b>" in item.value for item in app.markdown)
    assert any("지금 접수 중" in item.value for item in app.markdown)  # 11-21 예시 1: 접수 중 먼저
    more = [button for button in app.button if button.label.startswith("지난 공고")]  # 지난 공고는 3건 먼저
    if more:
        more[0].click().run()
    text = " ".join(item.value for item in app.markdown)
    assert "지원 가능" in text
    assert "전기기사: 배전(일반) 10점, 송변전(일반) 10점" in text  # 한전 (AI 추출, 정답지와 같은 값)
    assert "판정에 쓴 공고 근거" in text and '<td class="d-page">올해' in text  # 예시 2: 쪽 | 원문 표
    # T047: 결과를 PDF로 받기 버튼
    downloads = app.get("download_button")
    assert len(downloads) == 1 and "PDF" in downloads[0].proto.label

    [button for button in app.button if button.key == "open-kepco-2025-2026-h2"][0].click().run()
    assert not app.exception
    assert any("한국전력공사 채용공고 비교" in item.value for item in app.markdown)


def _open_qa_page(pair_id="kepco-2025-2026-h2"):
    app = AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=10).run()
    app.session_state["selected_pair_id"] = pair_id
    return app.switch_page("app/pages/qa.py").run()


def test_qa_without_api_key_shows_original_excerpts(monkeypatch):
    """T030: 키 없이 실행하면 AI 답 대신 원문 발췌를 보여주고 다른 화면은 그대로 열린다."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GONGCHAE_IGNORE_SECRETS", "1")  # PC의 .streamlit/secrets.toml 키도 쓰지 않게 (안 그러면 실제 AI 호출)
    app = _open_qa_page()

    assert not app.exception
    assert any("공고문에 물어보기" in item.value for item in app.markdown)
    app.text_input(key="qa_question").set_value("토익 몇 점 필요해?")
    [button for button in app.button if button.label == "물어보기"][0].click().run()

    assert not app.exception
    assert any("AI 답변을 만들 수 없어요" in item.value for item in app.warning)
    assert any("원문 발췌" in item.label for item in app.expander)

    app.switch_page("app/pages/report.py").run()
    assert not app.exception


def test_qa_question_not_in_notice_is_not_found_without_ai(monkeypatch):
    """T030: 공고문에 없는 질문은 AI를 부르지 않고 '공고문에 명시 없음'."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    app = _open_qa_page()
    app.text_input(key="qa_question").set_value("기숙사 제공돼?")
    [button for button in app.button if button.label == "물어보기"][0].click().run()

    assert not app.exception
    assert any("공고문에 명시 없음" in item.value for item in app.info)
    used = app.session_state["qa_used"] if "qa_used" in app.session_state else 0
    assert used == 0  # AI를 부르지 않았으니 질문 횟수도 안 셈


def test_matches_page_without_condition_asks_for_input():
    app = AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=10).run()
    app.switch_page("app/pages/matches.py").run()

    assert not app.exception
    assert any("먼저 희망 직렬·지역·자격증을 입력해 주세요" in item.value for item in app.warning)

