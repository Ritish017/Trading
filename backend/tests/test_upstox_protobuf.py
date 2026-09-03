import pytest
import time
from backend.app.broker_providers.upstox_proto import (
    FeedResponse,
    Feed,
    LTPC,
    FullFeed,
    MarketFullFeed,
    MarketOHLC,
    ExtendedFeedDetails,
    decode_upstox_protobuf_frame,
)
from backend.app.broker_providers.upstox_websocket import UpstoxWebSocketClient


def test_protobuf_feed_response_serialization_and_decoding():
    """Verify that FeedResponse serializes to binary and decodes faithfully."""
    resp = FeedResponse()
    resp.current_timestamp = int(time.time() * 1000)

    # Populate an equity LTPC feed for NSE_EQ|INE002A01018 (RELIANCE)
    feed1 = Feed()
    feed1.ltpc.ltp = 2950.45
    feed1.ltpc.cp = 2900.00
    feed1.ltpc.ltt = int(time.time() * 1000)
    resp.feeds["NSE_EQ|INE002A01018"].CopyFrom(feed1)

    # Populate a FullFeed for NSE_INDEX|Nifty 50
    feed2 = Feed()
    feed2.full_feed.market_full_feed.ltpc.ltp = 22450.00
    feed2.full_feed.market_full_feed.ltpc.cp = 22400.00
    feed2.full_feed.market_full_feed.ohlc.open = 22410.00
    feed2.full_feed.market_full_feed.ohlc.high = 22480.00
    feed2.full_feed.market_full_feed.ohlc.low = 22390.00
    feed2.full_feed.market_full_feed.ohlc.close = 22450.00
    feed2.full_feed.market_full_feed.efd.v = 15400000
    resp.feeds["NSE_INDEX|Nifty 50"].CopyFrom(feed2)

    binary_payload = resp.SerializeToString()
    assert len(binary_payload) > 0

    decoded = decode_upstox_protobuf_frame(binary_payload)
    assert decoded is not None
    assert "feeds" in decoded
    assert "NSE_EQ|INE002A01018" in decoded["feeds"]
    assert "NSE_INDEX|Nifty 50" in decoded["feeds"]

    reliance_data = decoded["feeds"]["NSE_EQ|INE002A01018"]
    assert reliance_data["ltpc"]["ltp"] == 2950.45
    assert reliance_data["ltpc"]["cp"] == 2900.00

    nifty_data = decoded["feeds"]["NSE_INDEX|Nifty 50"]
    assert nifty_data["ff"]["marketFF"]["ltpc"]["ltp"] == 22450.00
    assert nifty_data["ff"]["marketFF"]["ohlc"]["high"] == 22480.00
    assert nifty_data["ff"]["marketFF"]["v"] == 15400000


def test_upstox_websocket_client_decodes_binary_protobuf_frame():
    """Verify UpstoxWebSocketClient parses binary protobuf frames into NormalizedTicks."""
    resp = FeedResponse()
    resp.current_timestamp = int(time.time() * 1000)

    feed = Feed()
    feed.ltpc.ltp = 3850.50
    feed.ltpc.cp = 3800.00
    resp.feeds["NSE_EQ|INE467B01029"].CopyFrom(feed)  # TCS

    binary_payload = resp.SerializeToString()

    ws_client = UpstoxWebSocketClient(token="test-token")
    ticks = ws_client._decode_message(binary_payload)

    assert len(ticks) == 1
    tick = ticks[0]
    assert tick.symbol == "TCS.NS"
    assert tick.ltp == 3850.50
    assert tick.previous_close == 3800.00
    assert tick.change == 50.50
