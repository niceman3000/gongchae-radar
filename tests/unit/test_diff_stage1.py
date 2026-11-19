from src.diff_stage1 import classify_pair, compare


def test_standalone_dan_and_punctuation_only_change_is_expression():
    previous = "불인정(TOEFL은 국외응시 성적가능)"
    current = "불인정(단, TOEFL은 국외응시 성적가능)"

    kind, details = classify_pair(previous, current)

    assert kind == "expression"
    assert details == {}


def test_number_change_is_never_filtered_as_expression():
    kind, details = classify_pair("서류전형 10점", "단, 서류전형 20점")

    assert kind == "number"
    assert details["prev_numbers"] == ["10점"]
    assert details["curr_numbers"] == ["20점"]


def test_meaningful_word_change_remains_text_candidate():
    kind, _ = classify_pair("지원 가능", "지원 불가능")

    assert kind == "text"


def test_compare_counts_expression_change_without_showing_it():
    previous = {
        "recrutPblntSn": 1,
        "recrutPbancTtl": "이전 공고",
        "recrutNope": 10,
        "aplyQlfcCn": "불인정(TOEFL은 국외응시 성적가능)",
        "steps": [],
        "files": [],
    }
    current = {
        "recrutPblntSn": 2,
        "recrutPbancTtl": "현재 공고",
        "recrutNope": 10,
        "aplyQlfcCn": "불인정(단, TOEFL은 국외응시 성적가능)",
        "steps": [],
        "files": [],
    }

    result = compare(previous, current)

    assert result["changes"] == []
    assert result["expression_only_lines"] == 1


def test_registered_same_meaning_phrases_are_expression_only():
    military_prev = "- 병역법 제76조에 따라 병역의무 불이행자에 해당하지 않는 자(현역의 경우, 2차 전형 면접 시작일 전일까지 전역 가능한 자 포함)"
    military_curr = "- 병역법 제76조에 따라 병역의무 불이행자에 해당하지 않는 자(병역대상자는 2차 전형 면접 시작일 전일까지 전역 가능한 자 포함)"
    age_prev = "다. 연령 : 제한없음(단, 당사 규정은 만 60세임)"
    age_curr = "다. 연령 : 제한없음(단, 당사 정년은 만 60세임)"

    assert classify_pair(military_prev, military_curr)[0] == "expression"
    assert classify_pair(age_prev, age_curr)[0] == "expression"


def test_same_meaning_table_does_not_hide_number_change():
    kind, _ = classify_pair("연령 : 제한없음(단, 당사 규정은 만 60세임)", "연령 : 제한없음(단, 당사 정년은 만 65세임)")

    assert kind != "expression"
