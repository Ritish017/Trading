import logging
import asyncio
import json
import time
import struct
from typing import Callable, Awaitable, List, Optional, Set
import websockets
from backend.app.broker_providers.base import NormalizedTick
from backend.app.market.instruments import get_instrument_key, get_symbol_from_key

logger = logging.getLogger(__name__)

class UpstoxWebSocketClient:
    """
    Managed WebSocket client for Upstox Market Data Feed V3.
    Connects to authorized WS endpoint, subscribes to instruments, decodes ticks, and manages reconnects.
    """

    def __init__(self, token: str, get_ws_url_fn: Callable[[], Awaitable[str]]):
        self.token = token
        self.get_ws_url_fn = get_ws_url_fn
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.subscribed_keys: Set[str] = set()
        self.callback: Optional[Callable[[NormalizedTick], Awaitable[None]]] = None
        self.is_connected: bool = False
        self._running: bool = False
        self._loop_task: Optional[asyncio.Task] = None
        self.reconnect_count: int = 0
        self.last_tick_time: Optional[float] = None

    async def start(self, callback: Callable[[NormalizedTick], Awaitable[None]]) -> bool:
        self.callback = callback
        self._running = True
        self._loop_task = asyncio.create_task(self._connect_and_listen())
        # Wait up to 5 seconds to confirm connection
        for _ in range(50):
            if self.is_connected:
                return True
            await asyncio.sleep(0.1)
        return self.is_connected

    async def stop(self):
        self._running = False
        self.is_connected = False
        if self.ws:
            await self.ws.close()
            self.ws = None
        if self._loop_task:
            self._loop_task.cancel()
            self._loop_task = None
        logger.info("[UPSTOX WS] WebSocket client stopped gracefully.")

    async def subscribe(self, symbols: List[str]):
        keys = [get_instrument_key(s) for s in symbols if get_instrument_key(s)]
        self.subscribed_keys.update(keys)
        if self.ws and self.is_connected and keys:
            await self._send_subscription(keys, mode="full")

    async def unsubscribe(self, symbols: List[str]):
        keys = [get_instrument_key(s) for s in symbols if get_instrument_key(s)]
        self.subscribed_keys.difference_update(keys)
        if self.ws and self.is_connected and keys:
            payload = {
                "guid": f"unsub_{int(time.time())}",
                "method": "unsub",
                "data": {
                    "mode": "full",
                    "instrumentKeys": list(keys)
                }
            }
            try:
                await self.ws.send(json.dumps(payload))
            except Exception as e:
                logger.error(f"[UPSTOX WS] Unsubscribe send failed: {e}")

    async def _send_subscription(self, keys: List[str], mode: str = "full"):
        if not self.ws or not keys:
            return
        payload = {
            "guid": f"sub_{int(time.time())}",
            "method": "sub",
            "data": {
                "mode": mode,
                "instrumentKeys": list(keys)
            }
        }
        try:
            logger.info(f"[UPSTOX WS] Subscribing to {len(keys)} instruments (mode: {mode})...")
            await self.ws.send(json.dumps(payload))
        except Exception as e:
            logger.error(f"[UPSTOX WS] Subscription send failed: {str(e)}")

    async def _connect_and_listen(self):
        backoff = 1.0
        while self._running:
            try:
                logger.info("[UPSTOX WS] Authorizing and fetching WebSocket URL...")
                ws_url = await self.get_ws_url_fn()
                logger.info("[UPSTOX WS] Connecting to Upstox Market Data Feed V3...")
                
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
                    self.ws = ws
                    self.is_connected = True
                    self.reconnect_count += 1
                    backoff = 1.0
                    logger.info("[UPSTOX WS] Connected successfully.")

                    # Resubscribe existing instrument keys
                    if self.subscribed_keys:
                        await self._send_subscription(list(self.subscribed_keys), mode="full")

                    async for message in ws:
                        if not self._running:
                            break
                        try:
                            ticks = self._decode_message(message)
                            if ticks:
                                self.last_tick_time = time.time()
                                for tick in ticks:
                                    if self.callback:
                                        await self.callback(tick)
                        except Exception as decode_err:
                            logger.debug(f"[UPSTOX WS] Message decode error: {decode_err}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.is_connected = False
                logger.warning(f"[UPSTOX WS] Connection disconnected/failed: {str(e)}. Reconnecting in {backoff:.1f}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)

        self.is_connected = False

    def _decode_message(self, message: str | bytes) -> List[NormalizedTick]:
        """
        Decodes incoming Upstox V3 WebSocket messages.
        Honest decoding: Handles text JSON cleanly.
        If binary protobuf format is encountered without the compiled protobuf schema,
        truthfully logs degraded state rather than faking decoding.
        """
        ticks = []

        # 1. Text JSON Frame handling
        if isinstance(message, str):
            try:
                data = json.loads(message)
                feeds = data.get("feeds", {}) or data.get("data", {})
                for inst_key, feed in feeds.items():
                    tick = self._parse_feed_dict(inst_key, feed)
                    if tick:
                        ticks.append(tick)
            except Exception as e:
                logger.debug(f"[UPSTOX WS] Text JSON parse error: {e}")
            return ticks

        # 2. Binary Frame handling
        if isinstance(message, bytes):
            # Check if bytes are UTF-8 encoded text JSON
            try:
                text_content = message.decode('utf-8')
                if text_content.startswith('{'):
                    data = json.loads(text_content)
                    feeds = data.get("feeds", {}) or data.get("data", {})
                    for inst_key, feed in feeds.items():
                        tick = self._parse_feed_dict(inst_key, feed)
                        if tick:
                            ticks.append(tick)
                    return ticks
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass

            # Binary Protobuf stream without compiled proto file in repo
            logger.warning(
                "[UPSTOX WS DEGRADED] Received binary protobuf feed (%d bytes). "
                "Protobuf schema compilation file is not packaged in repository; binary stream cannot be decoded without schema.",
                len(message)
            )

        return ticks

    def _parse_feed_dict(self, inst_key: str, feed: dict) -> Optional[NormalizedTick]:
        symbol = get_symbol_from_key(inst_key)
        ff = feed.get("ff", {}) or feed.get("fullFeed", {})
        ltpc = ff.get("marketFF", {}).get("ltpc", {}) or feed.get("ltpc", {}) or feed.get("sf", {})
        
        ltp = float(ltpc.get("ltp", 0.0) or ltpc.get("last_price", 0.0) or 0.0)
        if ltp <= 0:
            return None

        cp_raw = ltpc.get("cp") or ltpc.get("close")
        prev_close = float(cp_raw) if cp_raw is not None and float(cp_raw) > 0 else None
        
        if prev_close is not None and prev_close > 0:
            change = round(ltp - prev_close, 2)
            change_pct = round((change / prev_close) * 100.0, 2)
        else:
            change = None
            change_pct = None

        ohlc = ff.get("marketFF", {}).get("ohlc", {}) or {}
        raw_open = ohlc.get("open")
        raw_high = ohlc.get("high")
        raw_low = ohlc.get("low")
        raw_close = ohlc.get("close")
        volume = int(ff.get("marketFF", {}).get("v", 0) or feed.get("v", 0) or 0)
        oi = int(ff.get("marketFF", {}).get("eoi", 0) or feed.get("oi", 0) or 0)
        ltt_raw = ltpc.get("ltt")

        return NormalizedTick(
            symbol=symbol,
            instrument_key=inst_key,
            exchange="NSE",
            timestamp=time.time(),
            received_at=time.time() * 1000.0,
            last_trade_time=float(ltt_raw) / 1000.0 if ltt_raw and float(ltt_raw) > 1e11 else (float(ltt_raw) if ltt_raw else time.time()),
            ltp=ltp,
            open=float(raw_open) if raw_open is not None else None,
            high=float(raw_high) if raw_high is not None else None,
            low=float(raw_low) if raw_low is not None else None,
            close=float(raw_close) if raw_close is not None else ltp,
            previous_close=prev_close,
            change=change,
            change_percent=change_pct,
            volume=volume,
            is_cumulative_volume=True,
            open_interest=oi if oi > 0 else None,
            provider="UPSTOX",
            is_live=True,
            market_status="LIVE"
        )
