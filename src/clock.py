"""오늘 날짜는 한국 시간으로 (11-22 새벽 점검 4번: 배포 서버는 UTC라 매일 0~9시에 D-day가 하루 틀림)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def today_kst() -> date:
    return datetime.now(KST).date()


def now_kst() -> datetime:
    """한국 시각 (시간대 정보 없이) — 접수 마감 '17시' 비교용"""
    return datetime.now(KST).replace(tzinfo=None)
