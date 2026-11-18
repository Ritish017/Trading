"""
APEX MCX Trading Session Engine
===============================
Authoritative evaluator for Multi Commodity Exchange (MCX) trading session hours:
- Trade Days: Monday through Friday (excluding statutory exchange holidays).
- Morning Session: 09:00 to 17:00 IST.
- Evening Session: 17:00 to 23:30 IST (extendable to 23:55 IST during US daylight savings / winter schedule).
- Closed: Weekends (Saturday & Sunday) and statutory exchange holidays.
"""

import datetime
from typing import Optional, Tuple, Dict, Any

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

# 2026 MCX Statutory Trading Holidays (Indian Calendar)
MCX_HOLIDAYS_2026: Dict[str, str] = {
    "2026-01-26": "Republic Day",
    "2026-03-03": "Holi",
    "2026-03-20": "Id-Ul-Fitr",
    "2026-04-03": "Good Friday",
    "2026-04-14": "Dr. Ambedkar Jayanti",
    "2026-05-01": "Maharashtra Day",
    "2026-05-27": "Bakri Id",
    "2026-08-15": "Independence Day",
    "2026-10-02": "Mahatma Gandhi Jayanti",
    "2026-10-20": "Dussehra",
    "2026-11-09": "Diwali Laxmi Pujan",
    "2026-11-10": "Diwali Balipratipada",
    "2026-12-25": "Christmas",
}


class MCXSessionEngine:
    """Evaluates whether the MCX commodity market is actively trading."""

    @staticmethod
    def now_ist() -> datetime.datetime:
        """Returns the current timestamp localized to Indian Standard Time (IST)."""
        return datetime.datetime.now(IST)

    @staticmethod
    def is_daylight_saving_us(dt: datetime.datetime) -> bool:
        """
        US Daylight Saving Time begins second Sunday in March and ends first Sunday in November.
        During US DST (summer), MCX evening session closes at 23:30 IST.
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

    def get_session_times(
        self,
        dt: Optional[datetime.datetime] = None,
        extended_session: Optional[bool] = None,
    ) -> Tuple[datetime.time, datetime.time]:
        """
        Returns the (start_time, close_time) for the MCX trading session.
        Start time is consistently 09:00:00 IST.
        Close time is 23:30:00 IST during US DST, or 23:55:00 IST during US Standard Time.
        """
        if dt is None:
            dt = self.now_ist()
        start_time = datetime.time(9, 0, 0)

        if extended_session is not None:
            close_minute = 55 if extended_session else 30
        else:
            # 23:30 during DST, 23:55 during winter standard time
            close_minute = 30 if self.is_daylight_saving_us(dt) else 55

        close_time = datetime.time(23, close_minute, 0)
        return start_time, close_time

    def is_mcx_trading_session_open(
        self,
        dt: Optional[datetime.datetime] = None,
        extended_session: Optional[bool] = None,
    ) -> bool:
        """
        Authoritative evaluator: returns True if the specified time (or current IST time)
        falls within active MCX trading session hours (09:00 to 23:30/23:55 IST, Mon-Fri, non-holiday).
        """
        if dt is None:
            dt = self.now_ist()
        elif dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        else:
            dt = dt.astimezone(IST)

        # 1. Weekday check (0 = Mon, 4 = Fri, 5 = Sat, 6 = Sun)
        if dt.weekday() >= 5:
            return False

        # 2. Statutory exchange holiday check
        date_str = dt.strftime("%Y-%m-%d")
        if date_str in MCX_HOLIDAYS_2026:
            return False

        # 3. Time bounds check
        start_time, close_time = self.get_session_times(dt, extended_session=extended_session)
        current_time = dt.time()

        return start_time <= current_time <= close_time

    def is_mcx_trading_session(
        self,
        dt: Optional[datetime.datetime] = None,
        extended_session: Optional[bool] = None,
    ) -> bool:
        """Alias for is_mcx_trading_session_open for backwards compatibility."""
        return self.is_mcx_trading_session_open(dt, extended_session=extended_session)

    def get_session_status_label(self, dt: Optional[datetime.datetime] = None) -> str:
        """Returns 'MCX LIVE' or 'MCX CLOSED'."""
        return "MCX LIVE" if self.is_mcx_trading_session_open(dt) else "MCX CLOSED"

    def get_mcx_session_info(
        self,
        dt: Optional[datetime.datetime] = None,
        extended_session: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Returns comprehensive diagnostic metadata about current or requested MCX session."""
        if dt is None:
            dt = self.now_ist()
        elif dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        else:
            dt = dt.astimezone(IST)

        is_open = self.is_mcx_trading_session_open(dt, extended_session=extended_session)
        start_time, close_time = self.get_session_times(dt, extended_session=extended_session)
        date_str = dt.strftime("%Y-%m-%d")
        is_weekend = dt.weekday() >= 5
        is_holiday = date_str in MCX_HOLIDAYS_2026
        holiday_name = MCX_HOLIDAYS_2026.get(date_str)
        is_dst = self.is_daylight_saving_us(dt)

        return {
            "is_open": is_open,
            "session_status": "MCX LIVE" if is_open else "MCX CLOSED",
            "market_status": "LIVE" if is_open else "CLOSED",
            "current_time": dt.isoformat(),
            "current_time_ist": dt.strftime("%Y-%m-%d %H:%M:%S IST"),
            "trading_day": date_str,
            "weekday": dt.strftime("%A"),
            "is_weekend": is_weekend,
            "is_holiday": is_holiday,
            "holiday_name": holiday_name,
            "start_time": start_time.strftime("%H:%M:%S"),
            "close_time": close_time.strftime("%H:%M:%S"),
            "is_dst": is_dst,
        }


# Global singleton instance
mcx_session_engine = MCXSessionEngine()


# Module-level convenience functions
def is_mcx_trading_session_open(
    dt: Optional[datetime.datetime] = None,
    extended_session: Optional[bool] = None,
) -> bool:
    """Evaluates whether MCX trading session is currently open."""
    return mcx_session_engine.is_mcx_trading_session_open(dt, extended_session=extended_session)


def get_mcx_session_info(
    dt: Optional[datetime.datetime] = None,
    extended_session: Optional[bool] = None,
) -> Dict[str, Any]:
    """Returns comprehensive diagnostic metadata about current or requested MCX session."""
    return mcx_session_engine.get_mcx_session_info(dt, extended_session=extended_session)
