from src.report_builder import build_report, normalize_unit_name


def api_item(sn, title, start, end, pdf_url):
    return {
        "recrutPblntSn": int(sn),
        "recrutPbancTtl": title,
        "pbancBgngYmd": start,
        "pbancEndYmd": end,
        "files": [
            {
                "atchFileType": "A",
                "atchFileNm": f"{sn}.pdf",
                "url": pdf_url,
            }
        ],
    }


def pair_config():
    return {
        "pair_id": "sample-2025-2026",
        "pair_name": "샘플 공고",
        "institution": "샘플기관",
        "track_focus": ["전기"],
        "prev_sn": "100",
        "curr_sn": "200",
        "prev_pdf": "data/pdf/100.pdf",
        "curr_pdf": "data/pdf/200.pdf",
    }


def stage1_result():
    return {
        "prev": {"sn": 100, "title": "2025 공고", "period": "20250101~20250131"},
        "curr": {"sn": 200, "title": "2026 공고", "period": "20260101~20260131"},
        "changes": [
            {"field": "채용인원", "type": "number", "prev": 10, "curr": 20},
            {
                "field": "근무지역",
                "type": "list",
                "removed": ["서울"],
                "added": ["부산"],
            },
            {
                "field": "응시자격",
                "type": "text",
                "prev": "기존 조건",
                "curr": "변경 조건",
            },
        ],
        "competition_in_api": {"prev": False, "curr": False},
    }


def test_build_report_maps_stage1_candidates_without_claiming_confirmation():
    report = build_report(
        pair_config(),
        stage1_result(),
        api_item("100", "2025 공고", "20250101", "20250131", "https://example/100.pdf"),
        api_item("200", "2026 공고", "20260101", "20260131", "https://example/200.pdf"),
        checked_at="2026-11-17",
    )

    assert report["pair_id"] == "sample-2025-2026"
    assert report["prev"]["sn"] == "100"
    assert report["curr"]["source_url"] == "https://example/200.pdf"
    assert [change["importance"] for change in report["changes"]] == [1, 2, 2]
    assert all(change["status"] == "review_required" for change in report["changes"])
    assert all(change["evidence"] == [] for change in report["changes"])


def test_reviewed_evidence_is_rechecked_before_confirmation():
    reviewed = {
        "changes": {
            "stage1-001": [
                {"side": "prev", "page": 2, "quote": "총 10명"},
                {"side": "curr", "page": 2, "quote": "총 20명"},
            ],
            "stage1-002": [
                {"side": "prev", "page": 3, "quote": "존재하지 않는 문장"},
                {"side": "curr", "page": 3, "quote": "부산"},
            ],
        }
    }

    report = build_report(
        pair_config(),
        stage1_result(),
        api_item("100", "2025 공고", "20250101", "20250131", "https://example/100.pdf"),
        api_item("200", "2026 공고", "20260101", "20260131", "https://example/200.pdf"),
        reviewed_evidence=reviewed,
        prev_all_text={"2": "채용예정인원 총 10명", "3": "서울"},
        curr_all_text={"2": "채용예정인원 총 20명", "3": "부산"},
        checked_at="2026-11-17",
    )

    headcount = next(item for item in report["changes"] if item["id"] == "stage1-001")
    region = next(item for item in report["changes"] if item["id"] == "stage1-002")
    assert headcount["status"] == "confirmed"
    assert all(item["verified"] for item in headcount["evidence"])
    assert region["status"] == "review_required"
    assert [item["verified"] for item in region["evidence"]] == [False, True]


def test_text_classification_is_merged_by_original_sentences():
    classifications = [
        {
            "field": "응시자격",
            "prev": "기존 조건",
            "curr": "변경 조건",
            "label": "실질 변경",
            "confidence": "높음",
            "one_line": "지원 조건이 변경됨",
        }
    ]

    report = build_report(
        pair_config(),
        stage1_result(),
        api_item("100", "2025 공고", "20250101", "20250131", "https://example/100.pdf"),
        api_item("200", "2026 공고", "20260101", "20260131", "https://example/200.pdf"),
        text_classifications=classifications,
        checked_at="2026-11-17",
    )

    text_change = next(item for item in report["changes"] if item["change_type"] == "text")
    assert text_change["ai_label"] == "실질 변경"
    assert text_change["confidence"] == "high"
    assert text_change["title"] == "지원 조건이 변경됨"


def test_stage2_units_and_verified_evidence_are_normalized():
    prev_extract = {
        "units": [
            {
                "unit_name": "배전(일반)",
                "headcount_total": {
                    "value": 10,
                    "evidence": {"page": 3, "quote": "배전 10명", "verified": "쪽 일치"},
                },
                "headcount_by_region": [],
                "required_qualifications": [],
                "certificate_bonus": [],
            }
        ]
    }
    curr_extract = {
        "units": [
            {
                "unit_name": "배전",
                "headcount_total": {
                    "value": 15,
                    "evidence": {"page": 4, "quote": "배전 15명", "verified": "쪽 일치"},
                },
                "headcount_by_region": [],
                "required_qualifications": [],
                "certificate_bonus": [],
            }
        ]
    }

    report = build_report(
        pair_config(),
        stage1_result(),
        api_item("100", "2025 공고", "20250101", "20250131", "https://example/100.pdf"),
        api_item("200", "2026 공고", "20260101", "20260131", "https://example/200.pdf"),
        prev_extract=prev_extract,
        curr_extract=curr_extract,
        checked_at="2026-11-17",
    )

    unit = report["units"][0]
    assert unit["normalized_name"] == "배전"
    assert unit["headcount_prev"] == 10
    assert unit["headcount_curr"] == 15
    assert {item["side"] for item in unit["evidence"]} == {"prev", "curr"}
    assert all(item["verified"] is True for item in unit["evidence"])


def test_normalize_unit_name_removes_only_comparison_suffixes():
    assert normalize_unit_name("배전(일반)") == "배전"
    assert normalize_unit_name("전기(신입_대졸수준)_일반") == "전기(신입_대졸수준)"
