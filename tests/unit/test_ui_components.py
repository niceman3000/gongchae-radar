from app.ui_components import concise_change_title, diff_side_html


def test_long_uncurated_title_becomes_short_and_explanatory():
    change = {
        "id": "stage1-999",
        "category": "전형",
        "title": "전형방법: " + "매우 긴 원문 " * 20,
    }

    title, impact = concise_change_title(change, "sample-pair")

    assert title == "전형방법 세부 기준 변경"
    assert "빨간색" in impact
    assert len(title) < 30


def test_diff_highlights_removed_and_added_text():
    previous = "사전평가에서 자기소개서 적부 평가만 시행"
    current = "사전평가에서 응시자격 적격 시 전체 사전평가 면제"

    previous_html = diff_side_html(previous, current, "prev")
    current_html = diff_side_html(previous, current, "curr")

    assert 'class="diff-removed"' in previous_html
    assert 'class="diff-added"' in current_html
    assert "자기소개서" in previous_html
    assert "응시자격" in current_html
