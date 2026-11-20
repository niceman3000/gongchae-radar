"""그림 공고에서 AI가 쪽수를 틀리게 적은 인용 고치기 (tools/extract_requirements.py, 11-20)."""

from tools.extract_requirements import checked_evidence

PAGES = {"1": "채용 공고", "2": "전기기사 10점", "3": "학력 제한 없음", "4": "학력 제한 없음"}


def test_wrong_page_is_dropped_without_fix() -> None:
    kept, dropped = checked_evidence([{"page": 8, "quote": "전기기사 10점"}], PAGES)
    assert kept == [] and dropped == 1


def test_wrong_page_is_fixed_when_quote_is_on_one_page() -> None:
    kept, dropped = checked_evidence([{"page": 8, "quote": "전기기사 10점"}], PAGES, fix_pages=True)
    assert kept == [{"side": "curr", "page": 2, "quote": "전기기사 10점"}] and dropped == 0


def test_quote_on_several_pages_or_nowhere_is_still_dropped() -> None:
    kept, dropped = checked_evidence(
        [{"page": 8, "quote": "학력 제한 없음"}, {"page": 1, "quote": "없는 문장"}], PAGES, fix_pages=True)
    assert kept == [] and dropped == 2
