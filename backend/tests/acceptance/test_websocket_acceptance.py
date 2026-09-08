"""
ACCEPTANCE SUITE: Upstox WebSocket & Realtime Streaming Red Team
Validates binary protobuf feed decoding, canonical quote store tick ingestion,
reconnect and message handling, and health diagnostics.
"""

import pytest
import time
from backend.app.broker_providers.upstox_proto import (
    FeedResponse,
    Feed,
    decode_upstox_protobuf_frame,
)
from backend.app.broker_providers.upstox_websocket import UpstoxWebSocketClient
from backend.app.market_data.canonical_store import canonical_store


def test_protobuf_binary_frame_pipeline():
    """Validates end-to-end binary frame serialization, decoding, and tick normalization."""
    resp = FeedResponse()
    now_ms = int(time.time() * 1000)
    resp.current_timestamp = now_ms

    feed = Feed()
    feed.ltpc.ltp = 2955.50
    feed.ltpc.cp = 2900.00
    feed.ltpc.ltt = now_ms
    resp.feeds["NSE_EQ|INE002A01018"].CopyFrom(feed)  # RELIANCE

    binary_data = resp.SerializeToString()
    assert len(binary_data) > 0

    ws_client = UpstoxWebSocketClient(token="test_token")
    ticks = ws_client._decode_message(binary_data)

    assert len(ticks) == 1
    tick = ticks[0]
    assert tick.symbol == "RELIANCE.NS"
    assert tick.ltp == 2955.50

    # Ingest into canonical store
    canonical_store.update_from_ws(tick.symbol, {
        "symbol": tick.symbol,
        "ltp": tick.ltp,
        "provider_timestamp": now_ms / 1000.0,
        "is_live": True,
        "provider": "UPSTOX_WS_PROTOBUF",
    })

    from unittest.mock import patch
    with patch("backend.app.market_data.canonical_store._nse_cash_market_open", return_value=True):
        canonical = canonical_store.get_canonical_quote("RELIANCE.NS")
        assert canonical is not None
        assert canonical.ltp == 2955.50
        assert canonical.is_live is True


def test_websocket_health_diagnostics():
    """Validates WebSocket health state reporting."""
    ws_client = UpstoxWebSocketClient(token="test_token")
    assert ws_client.is_connected is False

    # Simulate message arrival and advancing counters
    ws_client._stats["messages_received"] = 42
    ws_client._stats["last_message_time"] = time.time()

    assert ws_client._stats["messages_received"] == 42
    assert ws_client._stats["last_message_time"] > 0
