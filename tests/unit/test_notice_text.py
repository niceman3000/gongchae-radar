from src.notice_info import build_notice_info, parse_benefits
from src.notice_text import describe_change, is_list_like, split_items


def _change(change_type, prev, curr, category="가점"):
    return {"category": category, "change_type": change_type, "prev_value": prev, "curr_value": curr}


def test_split_items_keeps_commas_inside_parentheses():
    text = "- 장애인, 체험형인턴 사회형평전형(장애인, 취업지원대상자) 수료자, 양성평등"

    assert split_items(text) == ["장애인", "체험형인턴 사회형평전형(장애인, 취업지원대상자) 수료자", "양성평등"]


def test_long_sentence_with_commas_is_not_a_list():
    sentence = (
        "※ 단, 공무원채용시스템(구, 통합채용포털)에 등록된 인정 외국어(TOEIC, TOEFL(iBT), TEPS)의 경우, "
        "공무원채용시스템(구, 통합채용포털)에서 인정하는 유효기간을 적용"
    )

    assert not is_list_like(sentence)


def test_list_change_title_names_the_added_benefit_target():
    prev = "- 장애인, 취업지원대상자, 기초생활수급자, 체험형인턴 사회형평전형(장애인, 취업지원대상자) 수료자"
    curr = prev + ", 체험형인턴 우수인턴"

    title, impact = describe_change(_change("text", prev, curr))

    assert title == "우대 대상 추가: 체험형인턴 우수인턴"
    assert "나머지 4개 대상은 작년과 같아요" in impact
    assert "가점표" in impact


def test_subject_benefit_change_shows_number_difference():
    title, impact = describe_change(
        _change("number", "10. 당사 채용형 인턴 수료자 : 서류전형(1단계) 배점의 5% 가점",
                "10. 당사 채용형 인턴 수료자: 서류전형(1단계) 배점의 10% 가점")
    )

    assert title == "당사 채용형 인턴 수료자 혜택 변경: 5% → 10%"
    assert impact == "2026 혜택: 서류전형(1단계) 배점의 10% 가점"


def test_short_fragment_change_is_named_in_title():
    title, _ = describe_change(
        _change("text", "○ 한전 발명특허대전 입상자", "○ 한전 발명기술혁신대전 입상자")
    )

    assert title == "우대사항 문구: ‘발명특허대전’ → ‘발명기술혁신대전’"


def test_parse_benefits_attaches_sub_lines_and_notes():
    text = "\n".join([
        "○ 비수도권 및 본사 이전지역인재",
        "- 비수도권 : 1차전형 1% 가점",
        "- 이전지역 : 1차전형 3% 가점",
        "○ 한전 체험형인턴 : 인턴근무 평가 성적에 따라 2차전형 3%~5% 가점",
        "※ '24년 체험형인턴 수료자부터 적용",
    ])

    items = parse_benefits(text)

    assert items[0]["name"] == "비수도권 및 본사 이전지역인재"
    assert items[0]["benefit"] == "비수도권: 1차전형 1% 가점 / 이전지역: 1차전형 3% 가점"
    assert items[1]["notes"] == ["'24년 체험형인턴 수료자부터 적용"]


def test_notice_info_marks_new_and_changed_benefits_and_collects_rules():
    prev = {
        "prefCn": "1. 장애인 : 서류전형(1단계) 10% 가점\n2. 양성평등 채용목표제 시행",
        "aplyQlfcCn": "- 유효성적 : '23.08.08. 이후 응시한 성적",
    }
    curr = {
        "pbancBgngYmd": "20260722",
        "pbancEndYmd": "20260806",
        "prefCn": "1. 장애인 : 서류전형(면제) 10% 가점\n2. 양성평등 채용목표제 시행\n3. 우수인턴 : 필기 5점",
        "aplyQlfcCn": "- 유효성적 : '24.08.07. 이후 응시한 성적",
    }

    info = build_notice_info(prev, curr)

    assert info["period"] == {"start": "2026.07.22", "end": "2026.08.06"}
    assert [item["change"] for item in info["benefits"]] == ["changed", "same", "new"]
    assert info["rules"] == [{"topic": "어학성적", "text": "유효성적 : '24.08.07. 이후 응시한 성적"}]


def test_list_change_says_which_selection_track_the_list_belongs_to():
    prev = "- 장애인, 취업지원대상자, 기초생활수급자"
    curr = "- 장애인, 취업지원대상자, 기초생활수급자, 체험형인턴 우수인턴"
    notice_info = {
        "benefits": [
            {"section": "사회형평, 보훈특별", "name": name}
            for name in ["장애인", "취업지원대상자", "기초생활수급자", "체험형인턴 우수인턴"]
        ]
    }

    title, impact = describe_change(_change("text", prev, curr), notice_info)

    assert title == "우대 대상(사회형평, 보훈특별 전형) 추가: 체험형인턴 우수인턴"
    assert impact.startswith("이 줄은 사회형평, 보훈특별 전형에서 가점을 받는 대상 목록이에요.")
    assert "체험형인턴 우수인턴이(가) 목록에 들어가" in impact
