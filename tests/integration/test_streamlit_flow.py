from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[2]
DETAIL_PAGE = "app/pages/detail.py"
CONDITION = {"tracks": ["전기"], "track": "전기", "region": "부산·울산", "certificates": ["전기기사"]}
KEPCO = "kepco-2025-2026-h2"


def _app():
    return AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=15).run()


def _open_detail(pair_id=KEPCO, condition=CONDITION):
    """③ 공고 비교 (11-21 저녁 절충안: 메뉴 4개, 이동은 switch_page, 공고는 session_state로 넘김)"""
    app = _app()
    if condition:
        app.session_state["user_condition"] = dict(condition)
    app.session_state["selected_pair_id"] = pair_id
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
    """한전 공고 비교: 기관 선택 → 공고 띠 → 판정 3줄 → 달라진 점 5줄 → 일정 → 원문 대조(접힘)"""
    app = _open_detail()

    assert not app.exception
    text = _text(app)
    assert "2026년도 하반기 4직급 대졸수준 신입사원 채용공고" in text
    assert "나는 지원할 수 있나" in text and "조건 맞음" in text
    assert "토익 700점 이상" in text                                   # 판정 2줄째: 이유·토익·내 가점
    assert "전기기사: 배전(일반) 10점, 송변전(일반) 10점" in text  # 한전 (AI 추출, 정답지와 같은 값)
    assert any(item.label.startswith("자세히: 공통 조건 · 모집단위별 판정 · 근거") for item in app.expander)
    assert "작년 공고: 2025년도 하반기 대졸수준 (2025.09 공고)" in text  # 연도만 쓰지 않음
    assert "421명 → 490명 (+69명)" in text                         # 완료 확인 4
    assert "전기(배전·송변전) 서류 15배수 → 10배수" in text
    assert "청년청렴 Auditor" in text and 's-new">새로' in text
    assert "올해 일정" in text
    assert "공고문에 물어보기" not in [item.label for item in app.text_input]  # 질문 구역은 상세에서 뺌
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


def test_dongseo_detail_follows_spec_checks():
    """인원 '비교 어려움', 가점 '같음(30% 그대로)', 요약에 '신설' 없음, 일정 5칸, 원문 대조 접힘"""
    app = _open_detail(_pair("한국동서발전"))

    assert not app.exception
    text = _text(app)
    table = text[text.index('<table class="s-table">'):text.index("</table>", text.index('<table class="s-table">'))]
    assert 's-hard">비교 어려움' in table and "고졸 전형이 새로 들어가" in table
    assert "30% 그대로" in table and 's-same">같음' in table
    assert "신설" not in table
    assert text[text.index('class="timeline"'):].count('class="t-name"') == 5
    assert app.toggle[0].value is False


def test_user_can_pick_any_company_even_without_condition():
    """완료 확인 4: 결과에 없던 기관(강원랜드)도 기관 선택 상자로 비교"""
    app = _open_detail(condition=None)
    app.selectbox[0].set_value(_pair("강원랜드")).run()

    assert not app.exception
    text = _text(app)
    assert "강원랜드" in text and "421명 → 490명" not in text
    assert "조건을 넣으면" in text


def test_flow_conditions_matches_detail_qa_without_personal_data(monkeypatch):
    """완료 확인 1~3·5: 조건 입력 → 맞춤 공고(바뀐 점 없음, 동서발전 맨 위) → 공고 비교(동서발전 선택) → 질문(같은 공고)"""
    monkeypatch.setenv("GONGCHAE_IGNORE_SECRETS", "1")
    app = _app()
    assert not app.exception
    assert any("예시로 먼저 해 보세요" in item.value for item in app.markdown)  # 예시는 안내 상자
    # 입력 칸은 직렬·지역·자격증 세 개뿐이고 이름·연락처 같은 입력은 없다
    assert len(app.text_input) == 0 and len(app.number_input) == 0
    assert [item.label.split(" (")[0] for item in app.multiselect] == ["희망 직렬", "근무 지역", "보유 자격증"]

    app.multiselect[0].set_value(["전기"])
    app.multiselect[1].set_value(["부산", "울산"])
    app.multiselect[2].set_value(["전기기사"])
    [button for button in app.button if button.label == "공고 찾기"][0].click().run()

    assert not app.exception
    text = _text(app)
    assert "내 조건에 맞는 공고" in text and "전기 직렬 공고 <b>" in text
    assert "바뀐 점" not in text                                          # 목록은 판정 이유만
    assert text.index("한국동서발전") < text.index("한전KPS")             # 접수 중 맨 위
    more = [button for button in app.button if button.label.startswith("지난 공고")]
    if more:
        more[0].click().run()
    assert "작년엔 9월 9일 접수 시작" in _text(app)                         # 한전 지난 공고
    downloads = app.get("download_button")
    assert len(downloads) == 1 and "PDF" in downloads[0].proto.label     # T047

    dongseo = _pair("한국동서발전")
    [button for button in app.button if button.key == f"go-{dongseo}"][0].click().run()
    assert not app.exception
    assert app.selectbox[0].value == dongseo                              # 새로고침 없이 공고 비교, 동서발전 선택

    [button for button in app.button if button.label == "이 공고에 물어보기 ›"][0].click().run()
    assert not app.exception
    assert app.selectbox[0].value == dongseo                              # 질문 화면도 같은 공고


def test_second_example_card_goes_to_matches_with_open_notice():
    """예시 카드를 누르면 바로 맞춤 공고. 두 번째 예시(자격증 없음)도 접수 중이 0건이 아님"""
    app = _app()
    [button for button in app.button if button.key == "example-2"][0].click().run()

    assert not app.exception
    assert "지금 접수 중 <b>1</b>건" in _text(app)


def _open_qa_page(pair_id=KEPCO):
    app = _app()
    app.session_state["selected_pair_id"] = pair_id
    return app.switch_page("app/pages/qa.py").run()


def test_qa_without_api_key_shows_original_excerpts(monkeypatch):
    """T030: 키 없이 실행하면 AI 답 대신 원문 발췌를 보여준다."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GONGCHAE_IGNORE_SECRETS", "1")  # PC의 .streamlit/secrets.toml 키도 쓰지 않게 (안 그러면 실제 AI 호출)
    app = _open_qa_page()

    assert not app.exception
    app.text_input(key="qa_question").set_value("토익 몇 점 필요해?")
    [button for button in app.button if button.label == "물어보기"][0].click().run()

    assert not app.exception
    assert any("AI 답변을 만들 수 없어요" in item.value for item in app.warning)
    assert any("원문 발췌" in item.label for item in app.expander)


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
    app = _app()
    app.switch_page("app/pages/matches.py").run()

    assert not app.exception
    assert any("먼저 희망 직렬·지역·자격증을 입력해 주세요" in item.value for item in app.warning)
