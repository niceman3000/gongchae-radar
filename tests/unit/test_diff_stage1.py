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
