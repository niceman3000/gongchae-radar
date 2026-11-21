"""오늘 날짜는 한국 시간으로 (11-22 새벽 점검 4번: 배포 서버는 UTC라 매일 0~9시에 D-day가 하루 틀림)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def today_kst() -> date:
    return datetime.now(KST).date()
