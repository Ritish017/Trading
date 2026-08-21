import datetime
from enum import Enum
from typing import Dict, Any, Optional

IST_TZ = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

class MarketSessionState(str, Enum):
    PRE_OPEN = "PRE_OPEN"
    LIVE = "LIVE"
    POST_MARKET = "POST_MARKET"
    MARKET_CLOSED = "MARKET_CLOSED"
    UNAVAILABLE = "UNAVAILABLE"

class MarketSessionEngine:
    """
    Canonical NSE/BSE Market Session & Timing Engine.
    All times in Indian Standard Time (IST, UTC+05:30).
    Equities Trading Hours:
      - 09:00 - 09:08: Pre-open Order Entry
      - 09:08 - 09:15: Pre-open Order Matching & Discovery
      - 09:15 - 15:30: Regular Continuous Live Trading Session
      - 15:30 - 16:00: Post-market Closing Session
      - 16:00 - Next 09:00: Market Closed
    """

    @staticmethod
    def get_ist_now(timestamp: Optional[float] = None) -> datetime.datetime:
        if timestamp is not None:
            return datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc).astimezone(IST_TZ)
        return datetime.datetime.now(IST_TZ)

    @classmethod
    def get_market_session_state(cls, timestamp: Optional[float] = None) -> MarketSessionState:
        dt = cls.get_ist_now(timestamp)
        # Check weekend (5 = Saturday, 6 = Sunday)
        if dt.weekday() in (5, 6):
            return MarketSessionState.MARKET_CLOSED

        hour = dt.hour
        minute = dt.minute
        time_minutes = hour * 60 + minute

        pre_open_start = 9 * 60 # 09:00
        live_start = 9 * 60 + 15 # 09:15
        live_end = 15 * 60 + 30 # 15:30
        post_market_end = 16 * 60 # 16:00

        if pre_open_start <= time_minutes < live_start:
            return MarketSessionState.PRE_OPEN
        elif live_start <= time_minutes <= live_end:
            return MarketSessionState.LIVE
        elif live_end < time_minutes <= post_market_end:
            return MarketSessionState.POST_MARKET
        else:
            return MarketSessionState.MARKET_CLOSED

    @classmethod
    def is_valid_equity_candle_timestamp(cls, timestamp: float) -> bool:
        """
        Validates if a candle's timestamp falls within legitimate NSE trading hours.
        For example, a 15:33 live candle is invalid because regular session ended at 15:30 IST.
        """
        dt = cls.get_ist_now(timestamp)
        if dt.weekday() in (5, 6):
            return False
        time_minutes = dt.hour * 60 + dt.minute
        # 09:15 to 15:30
        return (9 * 60 + 15) <= time_minutes <= (15 * 60 + 30)

    @classmethod
    def get_session_info(cls, timestamp: Optional[float] = None) -> Dict[str, Any]:
        dt = cls.get_ist_now(timestamp)
        state = cls.get_market_session_state(timestamp)
        return {
            "session_state": state.value,
            "is_live_session": state == MarketSessionState.LIVE,
            "ist_time": dt.strftime("%Y-%m-%d %H:%M:%S IST"),
            "day_of_week": dt.strftime("%A"),
            "session_schedule": "09:15 - 15:30 IST (Mon - Fri)",
            "timezone": "Asia/Kolkata (IST, UTC+05:30)"
        }

market_session_engine = MarketSessionEngine()
