from src.change_groups import changed_words, display_units, find_change_groups
from src.evidence import validate_report_semantics


def _change(change_id, change_type, prev, curr, category="전형", status="review_required"):
    return {
        "id": change_id,
        "importance": 2,
        "category": category,
        "title": change_id,
        "change_type": change_type,
        "prev_value": prev,
        "curr_value": curr,
        "status": status,
        "evidence": [],
    }


# 한수원 2025→2026: 자기소개서가 사전평가에서 빠진 변경 하나가 후보 3개로 쪼개졌던 사례
KHNP_SELF_INTRO = [
    _change(
        "stage1-004",
        "text",
        "* 사전평가 : 자기소개서(적/부), 외국어성적(100점), 자격·면허 가점(1~10점), 일반가점(2~10점)/"
        "지역모집, 장애인, 취업지원대상자, 기초생활수급자, 북한이탈주민, 다문화가족의 자녀, "
        "자립준비청년에 해당하는 인원은 자기소개서 적부 평가만 시행",
        "* 사전평가 : 외국어성적(100점), 자격·면허 가점(1~10점), 일반가점(2~10점)/"
        "지역모집, 장애인, 취업지원대상자, 기초생활수급자, 북한이탈주민, 다문화가족의 자녀, "
        "자립준비청년에 해당하는 인원은 응시자격 적격 시, 1차 전형 사전평가 면제",
    ),
    _change("stage1-005", "removed", "※ 자기소개서 적격 판정 인원에 한해 필기시험 시행", None),
    _change("stage1-006", "added", None, "※ 응시자격 적격자 1차 전형(사전평가) 면제"),
]


def test_khnp_self_introduction_candidates_become_one_group():
    groups = find_change_groups(KHNP_SELF_INTRO)

    assert len(groups) == 1
    assert groups[0]["id"] == "group-stage1-004"
    assert groups[0]["member_ids"] == ["stage1-004", "stage1-005", "stage1-006"]
    assert "자기소개서" in groups[0]["shared_terms"]


def test_only_changed_words_count_not_unchanged_context():
    # 두 문장 모두 '외국어성적'을 담고 있지만 바뀐 낱말이 아니므로 묶음 근거가 아니다.
    words = changed_words(KHNP_SELF_INTRO[0])

    assert "자기소개서" in words
    assert "외국어성적" not in words


def test_unrelated_changes_in_same_category_stay_separate():
    changes = [
        _change("a", "text", "○ 직무(역량)면접(60점), 경험(인성)면접(40점)", "○ 직무면접(50점), 경험면접(50점)"),
        _change("b", "text", "※ 장애인 전형 전원 합격", "※ 장애인 및 보훈 전형 전원 합격"),
        _change("c", "removed", "다. 인성검사", None),
    ]

    assert find_change_groups(changes) == []


def test_changes_in_different_categories_are_never_grouped():
    changes = [
        _change("a", "added", None, "○ 보훈 분야는 「국가유공자법」에서 정한 취업지원대상자만 지원 가능", category="자격"),
        _change("b", "added", None, "○ 보훈 분야의 경우 「국가유공자법」에서 정한 취업지원대상자가 아닌 자", category="결격사유"),
    ]

    assert find_change_groups(changes) == []


def test_single_generic_short_word_is_not_enough():
    changes = [
        _change("a", "text", "서류전형(1단계)", "서류전형(면제)", category="가점"),
        _change("b", "removed", "※ 전문자격증 보유자는 서류전형 면제", None, category="가점"),
    ]

    assert find_change_groups(changes) == []


def test_display_unit_is_confirmed_only_when_every_member_is_confirmed():
    changes = [
        _change("x1", "added", None, "○ 한전 청년청렴 Auditor 우수활동자 : 1차전형 10% 가점", "가점", "confirmed"),
        _change("x2", "added", None, "※ '25년도 선정 우수활동자부터 적용", "가점", "confirmed"),
        _change("y", "text", "이전 문구", "새 문구", "가점", "confirmed"),
    ]
    groups = find_change_groups(changes)
    units = display_units(changes, groups)

    assert [unit["kind"] for unit in units] == ["group", "single"]
    assert units[0]["status"] == "confirmed"

    changes[1]["status"] = "review_required"
    assert display_units(changes, groups)[0]["status"] == "review_required"


def test_report_semantics_reject_group_with_unknown_member():
    report = {
        "prev": {"sn": "1"},
        "curr": {"sn": "2"},
        "changes": [_change("stage1-001", "text", "가", "나")],
        "change_groups": [
            {"id": "group-x", "category": "전형", "member_ids": ["stage1-001", "stage1-999"], "shared_terms": []}
        ],
    }

    errors = validate_report_semantics(report)

    assert any("stage1-999" in error for error in errors)
