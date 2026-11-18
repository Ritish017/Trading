"""
APEX MCX Trading Session Engine
===============================
Authoritative evaluator for Multi Commodity Exchange (MCX) trading session hours:
- Trade Days: Monday through Friday (excluding statutory exchange holidays).
- Morning Session: 09:00 to 17:00 IST.
- Evening Session: 17:00 to 23:30 IST (extended to 23:55 IST during US Daylight Saving Time).
- Closed: Weekends (Saturday & Sunday) and statutory holidays.
"""

import datetime
from typing import Optional, Tuple

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

# 2026 MCX Trading Holidays (Indian Calendar)
MCX_HOLIDAYS_2026 = {
    "2026-01-26",  # Republic Day
    "2026-03-03",  # Holi (Evening session only)
    "2026-03-20",  # Id-Ul-Fitr
    "2026-04-03",  # Good Friday
    "2026-04-14",  # Dr. Ambedkar Jayanti
    "2026-05-01",  # Maharashtra Day
    "2026-05-27",  # Bakri Id
    "2026-08-15",  # Independence Day
    "2026-10-02",  # Mahatma Gandhi Jayanti
    "2026-10-20",  # Dussehra
    "2026-11-09",  # Diwali Laxmi Pujan (Diwali Muhurat Trading)
    "2026-11-10",  # Diwali Balipratipada
    "2026-12-25",  # Christmas
}


class MCXSessionEngine:
    """Evaluates whether the MCX commodity market is actively trading."""

    @staticmethod
    def now_ist() -> datetime.datetime:
        return datetime.datetime.now(IST)

    @staticmethod
    def is_daylight_saving_us(dt: datetime.datetime) -> bool:
        """
        US Daylight Saving Time begins second Sunday in March and ends first Sunday in November.
        During US DST, MCX evening session closes at 23:30 IST.
        During US Standard Time (winter), MCX evening session closes at 23:55 IST.
        """
        month = dt.month
        if 3 < month < 11:
            return True
        if month < 3 or month > 11:
            return False
        # March: second Sunday
        if month == 3:
            first_day = datetime.datetime(dt.year, 3, 1, tzinfo=dt.tzinfo)
            first_sun = 1 + (6 - first_day.weekday()) % 7
            second_sun = first_sun + 7
            return dt.day >= second_sun
        # November: first Sunday
        if month == 11:
            first_day = datetime.datetime(dt.year, 11, 1, tzinfo=dt.tzinfo)
            first_sun = 1 + (6 - first_day.weekday()) % 7
            return dt.day < first_sun
        return False

    def get_session_times(self, dt: Optional[datetime.datetime] = None) -> Tuple[datetime.time, datetime.time]:
        if dt is None:
            dt = self.now_ist()
        start_time = datetime.time(9, 0, 0)
        # 23:30 during DST, 23:55 during winter
        close_minute = 30 if self.is_daylight_saving_us(dt) else 55
        close_time = datetime.time(23, close_minute, 0)
        return start_time, close_time

    def is_mcx_trading_session(self, dt: Optional[datetime.datetime] = None) -> bool:
        """Returns True if the current time falls within active MCX trading hours."""
        if dt is None:
            dt = self.now_ist()
        elif dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        else:
            dt = dt.astimezone(IST)

        # 1. Weekday check (0 = Mon, 4 = Fri, 5 = Sat, 6 = Sun)
        if dt.weekday() >= 5:
            return False

        # 2. Statutory holiday check
        date_str = dt.strftime("%Y-%m-%d")
        if date_str in MCX_HOLIDAYS_2026:
            return False

        # 3. Time bounds check
        start_time, close_time = self.get_session_times(dt)
        current_time = dt.time()

        return start_time <= current_time <= close_time

    def get_session_status_label(self, dt: Optional[datetime.datetime] = None) -> str:
        """Returns 'MCX LIVE' or 'MCX CLOSED'."""
        return "MCX LIVE" if self.is_mcx_trading_session(dt) else "MCX CLOSED"


# Global singleton instance
mcx_session_engine = MCXSessionEngine()
