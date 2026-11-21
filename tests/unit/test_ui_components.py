from app.ui_components import concise_change_title, diff_side_html


def test_long_uncurated_title_becomes_short_and_explanatory():
    change = {
        "id": "stage1-999",
        "category": "전형",
        "title": "전형방법: " + "매우 긴 원문 " * 20,
    }

    title, impact = concise_change_title(change, "sample-pair")

    assert title == "전형방법 문구 변경"
    assert impact is None  # 규칙으로 쓸 수 없는 의미는 빈 문구 대신 숨김 (11-21 팀원 점검 6번)
    assert len(title) < 30


def test_number_change_shows_delta_and_meaning():
    """11-21 팀원 점검 15번: '421 → 490'에 증감과 의미 한 줄"""
    from app.ui_components import concise_change_title

    title, impact = concise_change_title(
        {"id": "x", "category": "인원", "change_type": "number", "prev_value": "421", "curr_value": "490", "title": "채용인원"},
        "sample-pair",
    )
    assert title == "인원: 421명 → 490명 (+69명)"
    assert impact == "뽑는 인원이 늘었어요 (69명)"
    title, impact = concise_change_title(
        {"id": "y", "category": "전형", "change_type": "number", "title": "전형",
         "prev_value": "사무 : 50배수, 기술 : 15배수", "curr_value": "사무 : 50배수, 전기 : 10배수"},
        "sample-pair",
    )
    assert title == "전형 기준: 15배수 → 10배수"
    assert impact.startswith("서류 통과 인원이 줄어요")


def test_diff_highlights_removed_and_added_text():
    previous = "사전평가에서 자기소개서 적부 평가만 시행"
    current = "사전평가에서 응시자격 적격 시 전체 사전평가 면제"

    previous_html = diff_side_html(previous, current, "prev")
    current_html = diff_side_html(previous, current, "curr")

    assert 'class="diff-removed"' in previous_html
    assert 'class="diff-added"' in current_html
    assert "자기소개서" in previous_html
    assert "응시자격" in current_html
