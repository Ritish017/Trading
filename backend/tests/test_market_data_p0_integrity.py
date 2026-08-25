import datetime as dt
from zoneinfo import ZoneInfo

from backend.app.broker_providers.upstox_client import UpstoxRESTClient
from backend.app.market_data.canonical_store import CanonicalQuoteStore


def test_upstox_response_identity_never_uses_arbitrary_first_value():
    body = {"NSE_EQ|RELIANCE": {"last_price": 3000}}
    assert UpstoxRESTClient._quote_body_for_instrument(body, "NSE_EQ|HDFCBANK") is None
    assert UpstoxRESTClient._quote_body_for_instrument(body, "NSE_EQ|RELIANCE") == body["NSE_EQ|RELIANCE"]


def test_canonical_rejects_instrument_token_mismatch():
    store = CanonicalQuoteStore()
    raw = {"symbol": "HDFCBANK.NS", "instrument_key": "NSE_EQ|HDFCBANK", "provider_instrument_key": "NSE_EQ|RELIANCE", "ltp": 100, "provider": "UPSTOX", "provider_mode": "AUTHENTIC_LIVE", "provider_timestamp": 1000, "received_timestamp": 1000}
    assert store.update_from_rest(raw) is None


def test_canonical_is_symbol_isolated():
    store = CanonicalQuoteStore()
    base = {"instrument_key": "NSE_EQ|HDFCBANK", "provider": "UPSTOX", "provider_mode": "AUTHENTIC_LIVE", "provider_timestamp": 1000, "received_timestamp": 1000}
    a = dict(base, symbol="HDFCBANK.NS", ltp=100)
    b = dict(base, symbol="RELIANCE.NS", instrument_key="NSE_EQ|RELIANCE", ltp=200)
    assert store.update_from_rest(a).ltp == 100
    assert store.update_from_rest(b).ltp == 200
    assert store.get_canonical_quote("HDFCBANK.NS").ltp == 100
    assert store.get_canonical_quote("RELIANCE.NS").ltp == 200


def test_live_quote_is_not_marked_live_outside_nse_session(monkeypatch):
    store = CanonicalQuoteStore()
    fake_now = dt.datetime(2026, 8, 22, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    monkeypatch.setattr(dt, "datetime", type("FakeDateTime", (), {"now": staticmethod(lambda tz=None: fake_now), "time": dt.datetime.time}))
    raw = {"symbol": "HDFCBANK.NS", "instrument_key": "NSE_EQ|HDFCBANK", "ltp": 100, "provider": "UPSTOX", "provider_mode": "AUTHENTIC_LIVE", "provider_timestamp": fake_now.timestamp(), "received_timestamp": fake_now.timestamp()}
    q = store.update_from_rest(raw)
    assert q.market_data_status == "MARKET_CLOSED"
    assert q.is_live is False


def test_live_quote_forces_raw_unadjusted_domain():
    store = CanonicalQuoteStore()
    raw = {"symbol": "HDFCBANK.NS", "instrument_key": "NSE_EQ|HDFCBANK", "ltp": 100, "provider": "UPSTOX", "provider_mode": "AUTHENTIC_LIVE", "provider_timestamp": 1000, "received_timestamp": 1000, "price_domain": "CORPORATE_ACTION_ADJUSTED", "adjustment_status": "ADJUSTED"}
    q = store.update_from_rest(raw)
    assert q.price_domain == "RAW_EXCHANGE_PRICE"
    assert q.adjustment_status == "RAW_EXCHANGE_PRICE"
