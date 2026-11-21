from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[2]
DETAIL_PAGE = "app/pages/detail.py"
CONDITION = {"t": "전기", "r": "부산·울산", "c": "전기기사"}
KEPCO = "kepco-2025-2026-h2"


def _app(**params):
    app = AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=15)
    for key, value in params.items():
        app.query_params[key] = value
    return app


def _open_detail(pair_id=KEPCO, **params):
    """화면 2. 공고 상세 (11-21 구조 개편: 공고 줄 링크가 주소창 조건·공고로 연다)"""
    app = _app(**{**CONDITION, "p": pair_id, **params}).run()
    return app.switch_page(DETAIL_PAGE).run()


def _text(app):
    return " ".join(item.value for item in app.markdown)


def _pair(institution):
    import json

    for path in (ROOT / "data" / "reports").glob("*.json"):
        report = json.loads(path.read_text(encoding="utf-8"))
        if report["institution"] == institution:
            return report["pair_id"]
    raise KeyError(institution)


def test_kepco_detail_shows_verdict_five_rows_and_schedule():
    """한전 상세: 판정 → 작년과 달라진 점 5줄 → 일정 → 질문 → 원문 대조(접힘)"""
    app = _open_detail()

    assert not app.exception
    text = _text(app)
    assert "2026년도 하반기 4직급 대졸수준 신입사원 채용공고" in text
    assert "나는 지원할 수 있나" in text and "조건 맞음" in text
    assert "전기기사: 배전(일반) 10점, 송변전(일반) 10점" in text  # 한전 (AI 추출, 정답지와 같은 값)
    assert "작년 공고: 2025년도 하반기 대졸수준 (2025.09 공고)" in text  # 연도만 쓰지 않음
    assert "421명 → 490명 (+69명)" in text                         # 완료 확인 4
    assert "전기(배전·송변전) 서류 15배수 → 10배수" in text
    assert "청년청렴 Auditor" in text and 's-new">새로' in text
    assert "올해 일정" in text and "공고문에 물어보기" in text
    assert len(app.selectbox[0].options) == 30
    assert app.toggle and app.toggle[0].value is False                # 원문 대조는 접힘
    assert "자동으로 정리했어요" in " ".join(item.value for item in app.caption)


def test_raw_comparison_keeps_cards_when_opened():
    """원문 대조를 펼치면 예전 카드 모양 그대로 (증감 색, 바뀐 조각 제목, 범례는 한 번)"""
    app = _open_detail()
    app.toggle[0].set_value(True).run()

    assert not app.exception
    text = _text(app)
    assert "인원: 421명 → 490명" in text and '<span class="up">(+69명)</span>' in text
    assert "전기(배전, 송변전) 10배수 신설" in text
    assert 'class="diff-added"' in text
    assert text.count('class="c-legend"') == 1
    assert "공식 공고 원문" in " ".join(item.value for item in app.subheader) or "공식 공고 원문" in text


def test_dongseo_detail_follows_spec_checks():
    """완료 확인 3: 인원 '비교 어려움', 가점 '같음(30% 그대로)', 요약에 '신설' 없음, 일정 5칸, 원문 대조 접힘"""
    app = _open_detail(_pair("한국동서발전"))

    assert not app.exception
    text = _text(app)
    table = text[text.index('<table class="s-table">'):text.index("</table>", text.index('<table class="s-table">'))]
    assert 's-hard">비교 어려움' in table and "고졸 전형이 새로 들어가" in table
    assert "30% 그대로" in table and 's-same">같음' in table
    assert "신설" not in table
    schedule = text[text.index('<table class="t-table">'):]
    assert schedule.count('class="t-name"') == 5
    assert app.toggle[0].value is False


def test_user_can_switch_company():
    app = _open_detail()
    app.selectbox[0].set_value("khnp-2025-2026-round3").run()

    assert not app.exception
    text = _text(app)
    assert "2026년도 제3차 신입사원(대졸수준) 선발" in text
    assert "421명 → 490명" not in text  # 다른 기관 내용이 섞이지 않음
    assert "139명 → 229명 (+90명)" in text


def test_search_flow_without_personal_data():
    """화면 1: 조건 입력과 결과가 한 화면. 공고 줄은 상세로 가는 링크"""
    app = _app().run()

    assert not app.exception
    assert any("내 조건으로 공고 찾기" in item.value for item in app.markdown)
    # 입력 칸은 직렬·지역·자격증 세 개뿐이고 이름·연락처 같은 입력은 없다
    assert len(app.text_input) == 0 and len(app.number_input) == 0
    assert [item.label.split(" (")[0] for item in app.multiselect] == ["직렬", "근무 지역", "보유 자격증"]

    app.multiselect[0].set_value(["전기"])
    app.multiselect[1].set_value(["부산", "울산"])
    app.multiselect[2].set_value(["전기기사"])
    [button for button in app.button if button.label == "찾기"][0].click().run()

    assert not app.exception
    text = _text(app)
    assert "전기 직렬 공고 <b>" in text and "지금 접수 중" in text
    assert 'href="detail?' in text                                       # 줄을 누르면 상세
    dongseo = text[text.index("한국동서발전"):]
    assert "바뀐 점:" in dongseo[:1500]                                    # 완료 확인 1
    more = [button for button in app.button if button.label.startswith("지난 공고")]
    if more:
        more[0].click().run()
    text = _text(app)
    assert "작년엔 9월 9일 접수 시작" in text                               # 한전 지난 공고
    assert "자세히 보기" not in " ".join(item.label for item in app.expander)
    downloads = app.get("download_button")
    assert len(downloads) == 1 and "PDF" in downloads[0].proto.label     # T047


def test_second_example_has_open_notice():
    """완료 확인 2: 두 번째 예시(자격증 없음)도 접수 중이 0건이 아님"""
    app = _app().run()
    [button for button in app.button if button.label == "전기·부산·울산·자격증 없음"][0].click().run()

    assert not app.exception
    assert "지금 접수 중 <b>1</b>건" in _text(app)


def test_qa_without_api_key_shows_original_excerpts(monkeypatch):
    """T030: 키 없이 실행하면 AI 답 대신 원문 발췌. 질문은 상세 화면 안의 한 구역"""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GONGCHAE_IGNORE_SECRETS", "1")  # PC의 .streamlit/secrets.toml 키도 쓰지 않게 (안 그러면 실제 AI 호출)
    app = _open_detail()

    assert not app.exception
    app.text_input(key="qa_question").set_value("토익 몇 점 필요해?")
    [button for button in app.button if button.label == "물어보기"][0].click().run()

    assert not app.exception
    assert any("AI 답변을 만들 수 없어요" in item.value for item in app.warning)
    assert any("원문 발췌" in item.label for item in app.expander)


def test_qa_question_not_in_notice_is_not_found_without_ai(monkeypatch):
    """T030: 공고문에 없는 질문은 AI를 부르지 않고 '공고문에 명시 없음'."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    app = _open_detail()
    app.text_input(key="qa_question").set_value("기숙사 제공돼?")
    [button for button in app.button if button.label == "물어보기"][0].click().run()

    assert not app.exception
    assert any("공고문에 명시 없음" in item.value for item in app.info)
    used = app.session_state["qa_used"] if "qa_used" in app.session_state else 0
    assert used == 0  # AI를 부르지 않았으니 질문 횟수도 안 셈


def test_search_without_condition_shows_only_inputs():
    app = _app().run()

    assert not app.exception
    assert "직렬 공고 <b>" not in _text(app)
    assert any("이름·연락처는 받지 않아요" in item.value for item in app.markdown)
