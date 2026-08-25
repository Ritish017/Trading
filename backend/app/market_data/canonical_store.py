"""Canonical, provenance-preserving live market quote store."""
import datetime as dt
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def _nse_cash_market_open(now: Optional[dt.datetime] = None) -> bool:
    now = now.astimezone(IST) if now is not None else dt.datetime.now(IST)
    if now.weekday() >= 5:
        return False
    return dt.time(9, 15) <= now.time() <= dt.time(15, 30)


@dataclass
class CanonicalQuote:
    symbol: str
    instrument_key: str
    exchange: str
    ltp: float
    previous_close: Optional[float]
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    volume: Optional[int]
    bid: Optional[float]
    ask: Optional[float]
    provider: str
    provider_mode: str
    provider_timestamp: float
    received_timestamp: float
    price_domain: str = "RAW_EXCHANGE_PRICE"
    adjustment_status: str = "RAW_EXCHANGE_PRICE"
    last_rest_ltp: Optional[float] = None
    last_rest_ts: Optional[float] = None
    last_ws_ltp: Optional[float] = None
    last_ws_ts: Optional[float] = None
    canonical_source: str = "REST"
    quote_sequence_id: int = 0

    @property
    def data_age_seconds(self) -> float:
        return max(0.0, time.time() - self.provider_timestamp)

    @property
    def market_session_open(self) -> bool:
        return _nse_cash_market_open()

    @property
    def is_live(self) -> bool:
        return self.provider_mode == "AUTHENTIC_LIVE" and self.data_age_seconds <= 120 and self.market_session_open

    @property
    def is_stale(self) -> bool:
        return self.data_age_seconds > 120

    @property
    def market_data_status(self) -> str:
        if self.provider_mode == "SIMULATED":
            return "SIMULATED"
        if self.provider_mode == "UNAVAILABLE":
            return "UNAVAILABLE"
        if self.provider_mode != "AUTHENTIC_LIVE":
            return "UNAVAILABLE"
        if not self.market_session_open:
            return "MARKET_CLOSED"
        age = self.data_age_seconds
        if age <= 120:
            return "LIVE"
        if age <= 600:
            return "RECENT"
        if age <= 3600:
            return "STALE"
        return "EXPIRED"

    def to_api_dict(self) -> Dict[str, Any]:
        change = None
        change_pct = None
        if self.previous_close and self.previous_close > 0:
            change = round(self.ltp - self.previous_close, 2)
            change_pct = round(change / self.previous_close * 100, 2)
        return {
            "symbol": self.symbol,
            "instrument_key": self.instrument_key,
            "exchange": self.exchange,
            "ltp": self.ltp,
            "previous_close": self.previous_close,
            "change": change,
            "change_percent": change_pct,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "volume": self.volume,
            "bid": self.bid,
            "ask": self.ask,
            "provider": self.provider,
            "provider_mode": self.provider_mode,
            "provider_timestamp": self.provider_timestamp,
            "received_timestamp": self.received_timestamp,
            "data_age_seconds": round(self.data_age_seconds, 1),
            "market_data_status": self.market_data_status,
            "market_session_open": self.market_session_open,
            "canonical_source": self.canonical_source,
            "quote_sequence_id": self.quote_sequence_id,
            "is_live": self.is_live,
            "is_stale": self.is_stale,
            "price_domain": self.price_domain,
            "adjustment_status": self.adjustment_status,
            "last_rest_ltp": self.last_rest_ltp,
            "last_rest_ts": self.last_rest_ts,
            "last_ws_ltp": self.last_ws_ltp,
            "last_ws_ts": self.last_ws_ts,
        }


class CanonicalQuoteStore:
    """Thread-safe REST/WS reconciliation store isolated by canonical symbol."""
    def __init__(self):
        self._lock = threading.RLock()
        self._rest: Dict[str, Dict[str, Any]] = {}
        self._ws: Dict[str, Dict[str, Any]] = {}
        self._canonical: Dict[str, CanonicalQuote] = {}
        self._seq: Dict[str, int] = {}

    def _next_seq(self, symbol: str) -> int:
        self._seq[symbol] = self._seq.get(symbol, 0) + 1
        return self._seq[symbol]

    @staticmethod
    def _valid_identity(raw: Dict[str, Any]) -> bool:
        symbol = str(raw.get("symbol") or "").strip()
        if not symbol:
            return False
        key = str(raw.get("instrument_key") or symbol).strip()
        provider_key = raw.get("provider_instrument_key") or raw.get("instrument_token")
        if provider_key is not None and str(provider_key).replace(":", "|") != key.replace(":", "|"):
            return False
        provider_symbol = raw.get("provider_symbol")
        if provider_symbol is not None:
            normalized = str(provider_symbol).upper().replace(".NS", "")
            expected = symbol.upper().replace(".NS", "")
            if normalized != expected:
                return False
        return True

    def _accept(self, raw: Dict[str, Any]) -> bool:
        return bool(self._valid_identity(raw) and raw.get("ltp") is not None and float(raw.get("ltp")) > 0)

    def update_from_rest(self, raw: Dict[str, Any]) -> Optional[CanonicalQuote]:
        if not self._accept(raw):
            logger.warning("[CANONICAL] rejected REST observation with invalid identity/provenance: %s", raw.get("symbol"))
            return None
        symbol = str(raw["symbol"])
        with self._lock:
            self._rest[symbol] = raw
            return self._reconcile(symbol)

    def update_from_ws(self, raw: Dict[str, Any]) -> Optional[CanonicalQuote]:
        if not self._accept(raw):
            logger.warning("[CANONICAL] rejected WS observation with invalid identity/provenance: %s", raw.get("symbol"))
            return None
        symbol = str(raw["symbol"])
        with self._lock:
            self._ws[symbol] = raw
            return self._reconcile(symbol)

    def _reconcile(self, symbol: str) -> Optional[CanonicalQuote]:
        rest, ws = self._rest.get(symbol), self._ws.get(symbol)
        if not rest and not ws:
            return None
        if rest and ws:
            rts = float(rest.get("provider_timestamp") or rest.get("timestamp") or 0)
            wts = float(ws.get("provider_timestamp") or ws.get("timestamp") or 0)
            winner, source_name = (ws, "WS") if wts >= rts else (rest, "REST")
            if abs(float(rest["ltp"]) - float(ws["ltp"])) >= 0.01:
                logger.debug("[CANONICAL] %s REST=%s WS=%s winner=%s", symbol, rest["ltp"], ws["ltp"], source_name)
        else:
            winner, source_name = (ws, "WS") if ws else (rest, "REST")
        if not self._accept(winner):
            return None
        prov_ts = float(winner.get("provider_timestamp") or winner.get("timestamp") or 0)
        recv_ts = float(winner.get("received_timestamp") or time.time())
        if prov_ts <= 0:
            return None
        mode = winner.get("provider_mode", "AUTHENTIC_LIVE")
        canonical = CanonicalQuote(
            symbol=symbol,
            instrument_key=str(winner.get("instrument_key") or winner.get("symbol") or symbol),
            exchange=str(winner.get("exchange", "NSE")),
            ltp=float(winner["ltp"]),
            previous_close=float(winner["previous_close"]) if winner.get("previous_close") is not None else None,
            open=float(winner["open"]) if winner.get("open") is not None else None,
            high=float(winner["high"]) if winner.get("high") is not None else None,
            low=float(winner["low"]) if winner.get("low") is not None else None,
            volume=int(winner["volume"]) if winner.get("volume") is not None else None,
            bid=float(winner["bid"]) if winner.get("bid") is not None else None,
            ask=float(winner["ask"]) if winner.get("ask") is not None else None,
            provider=str(winner.get("provider", winner.get("source", "UNKNOWN"))),
            provider_mode=str(mode),
            provider_timestamp=prov_ts,
            received_timestamp=recv_ts,
            price_domain=str(winner.get("price_domain", "RAW_EXCHANGE_PRICE")),
            adjustment_status=str(winner.get("adjustment_status", "RAW_EXCHANGE_PRICE")),
            last_rest_ltp=float(rest["ltp"]) if rest else None,
            last_rest_ts=float(rest.get("provider_timestamp") or rest.get("timestamp") or 0) if rest else None,
            last_ws_ltp=float(ws["ltp"]) if ws else None,
            last_ws_ts=float(ws.get("provider_timestamp") or ws.get("timestamp") or 0) if ws else None,
            canonical_source=source_name,
            quote_sequence_id=self._next_seq(symbol),
        )
        if canonical.provider_mode == "AUTHENTIC_LIVE":
            canonical.price_domain = "RAW_EXCHANGE_PRICE"
            canonical.adjustment_status = "RAW_EXCHANGE_PRICE"
        self._canonical[symbol] = canonical
        return canonical

    def get_canonical_quote(self, symbol: str) -> Optional[CanonicalQuote]:
        with self._lock:
            return self._canonical.get(symbol)

    def get_all_canonical(self) -> Dict[str, CanonicalQuote]:
        with self._lock:
            return dict(self._canonical)

    def get_subscribed_symbols(self) -> list:
        with self._lock:
            return list(set(self._rest) | set(self._ws))

    def clear_symbol(self, symbol: str):
        with self._lock:
            self._rest.pop(symbol, None); self._ws.pop(symbol, None); self._canonical.pop(symbol, None)

    def get_diagnostic(self, symbol: str, authenticated: bool, connected: bool) -> Dict[str, Any]:
        canonical = self.get_canonical_quote(symbol)
        if canonical is None:
            return {"symbol": symbol, "provider": "UPSTOX", "provider_mode": "UNAVAILABLE", "authenticated": authenticated, "connected": connected, "data_available": False, "raw_ltp": None, "provider_timestamp": None, "received_timestamp": None, "data_age_seconds": None, "market_data_status": "UNAVAILABLE", "integrity": "NO_DATA"}
        integrity = "PASS"
        if canonical.provider_mode == "SIMULATED": integrity = "SIMULATED_NOT_LIVE"
        elif not authenticated or not connected: integrity = "PROVIDER_NOT_CONNECTED"
        elif canonical.is_stale: integrity = "STALE"
        elif canonical.ltp <= 0: integrity = "INVALID_LTP"
        return {"symbol": symbol, "instrument_key": canonical.instrument_key, "provider": canonical.provider, "provider_mode": canonical.provider_mode, "authenticated": authenticated, "connected": connected, "data_available": True, "raw_ltp": canonical.ltp, "provider_timestamp": canonical.provider_timestamp, "received_timestamp": canonical.received_timestamp, "data_age_seconds": round(canonical.data_age_seconds, 1), "market_data_status": canonical.market_data_status, "canonical_source": canonical.canonical_source, "quote_sequence_id": canonical.quote_sequence_id, "is_live": canonical.is_live, "is_stale": canonical.is_stale, "price_domain": canonical.price_domain, "adjustment_status": canonical.adjustment_status, "integrity": integrity}


canonical_store = CanonicalQuoteStore()
