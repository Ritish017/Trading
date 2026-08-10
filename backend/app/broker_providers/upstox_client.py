import logging
import asyncio
from typing import Dict, Any, List, Optional
import httpx
from backend.app.market.instruments import get_instrument_key, get_instrument_metadata

logger = logging.getLogger(__name__)

class UpstoxRESTClient:
    """
    Production-grade Async REST Client for Upstox V2/V3 API.
    Handles read-only Analytics Token authentication, connection pooling, retries, and header redaction.
    """

    def __init__(self, token: str, base_url: str = "https://api.upstox.com"):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.client: Optional[httpx.AsyncClient] = None

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }

    async def _init_client(self):
        if self.client is None or self.client.is_closed:
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._get_headers(),
                timeout=httpx.Timeout(10.0, connect=5.0),
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50)
            )

    async def close(self):
        if self.client and not self.client.is_closed:
            await self.client.aclose()
            self.client = None

    async def _request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, retries: int = 2) -> Dict[str, Any]:
        await self._init_client()
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        
        last_error = None
        for attempt in range(retries + 1):
            try:
                # Log endpoint without logging sensitive headers
                logger.debug(f"[UPSTOX REST] {method} {endpoint} (Attempt {attempt + 1})")
                resp = await self.client.request(method, url, params=params)
                
                if resp.status_code == 429: # Rate limit
                    logger.warning("[UPSTOX REST] Rate limit hit (429). Retrying after backoff...")
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                
                resp.raise_for_status()
                data = resp.json()
                return data
            except httpx.HTTPStatusError as e:
                last_error = e
                logger.error(f"[UPSTOX REST] HTTP Error {e.response.status_code} for {endpoint}: {e.response.text}")
                if e.response.status_code in (401, 403):
                    # Authentication failure - do not retry
                    break
                await asyncio.sleep(1.0 * (attempt + 1))
            except Exception as e:
                last_error = e
                logger.error(f"[UPSTOX REST] Request failed for {endpoint}: {str(e)}")
                await asyncio.sleep(1.0 * (attempt + 1))

        if last_error:
            raise last_error
        raise RuntimeError(f"Request failed for {endpoint}")

    async def get_ws_authorize_url(self) -> str:
        """Fetch authorized WebSocket redirect URL from Upstox Feed Authorization API."""
        endpoint = "/v2/feed/market-data-feed/authorize"
        res = await self._request("GET", endpoint)
        data = res.get("data", {})
        ws_url = data.get("authorizedRedirectUri") or data.get("wsUrl") or data.get("authorized_redirect_uri")
        if not ws_url:
            raise ValueError("Upstox WS authorization did not return a valid redirect URI.")
        return ws_url

    async def get_full_quote(self, symbol: str) -> Dict[str, Any]:
        """Fetch full market quote snapshot for an instrument."""
        inst_key = get_instrument_key(symbol)
        endpoint = f"/v2/market-quote/quotes?instrument_key={inst_key}"
        res = await self._request("GET", endpoint)
        raw_data = res.get("data", {})
        
        # Upstox returns keys formatted as "NSE_EQ:INE002A01018" or "NSE_INDEX:Nifty 50"
        quote_body = None
        for k, v in raw_data.items():
            quote_body = v
            break
            
        if not quote_body:
            # Try ohlc endpoint fallback if quotes is empty
            ohlc_res = await self._request("GET", f"/v2/market-quote/ohlc?instrument_key={inst_key}&interval=1d")
            quote_body = ohlc_res.get("data", {}).get(inst_key.replace("|", ":"), {})

        ohlc = quote_body.get("ohlc", {})
        depth = quote_body.get("depth", {})
        bids = depth.get("buy", [])
        asks = depth.get("sell", [])

        ltp = float(quote_body.get("last_price", 0.0) or quote_body.get("close", 0.0))
        prev_close = float(ohlc.get("close", ltp) or ltp)
        change = round(ltp - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0

        meta = get_instrument_metadata(symbol)

        return {
            "symbol": symbol,
            "instrument_key": inst_key,
            "exchange": meta.get("exchange", "NSE"),
            "instrument_type": meta.get("instrument_type", "EQUITY"),
            "ltp": ltp,
            "open": float(ohlc.get("open", ltp)),
            "high": float(ohlc.get("high", ltp)),
            "low": float(ohlc.get("low", ltp)),
            "close": ltp,
            "previous_close": prev_close,
            "change": change,
            "change_percent": change_pct,
            "volume": int(quote_body.get("volume", 0)),
            "open_interest": int(quote_body.get("oi", 0)),
            "bid": float(bids[0].get("price", 0.0)) if bids else None,
            "ask": float(asks[0].get("price", 0.0)) if asks else None,
            "timestamp": float(quote_body.get("timestamp", 0) or 0.0) / 1000.0,
            "source": "UPSTOX",
            "is_live": True
        }

    async def get_historical_candles(self, symbol: str, interval: str = "5m", to_date: Optional[str] = None, from_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch historical candle series from Upstox API."""
        inst_key = get_instrument_key(symbol)
        
        # Upstox interval mapping: 1m -> 1minute, 5m -> 5minute, 15m -> 15minute, 30m -> 30minute, 1h -> 60minute, 1D -> day
        upstox_interval_map = {
            "1m": "1minute",
            "3m": "3minute",
            "5m": "5minute",
            "15m": "15minute",
            "30m": "30minute",
            "1h": "60minute",
            "1D": "day"
        }
        mapped_interval = upstox_interval_map.get(interval, "5minute")

        if to_date and from_date:
            endpoint = f"/v2/historical-candle/{inst_key}/{mapped_interval}/{to_date}/{from_date}"
        else:
            endpoint = f"/v2/historical-candle/intraday/{inst_key}/{mapped_interval}"

        res = await self._request("GET", endpoint)
        raw_candles = res.get("data", {}).get("candles", [])

        normalized = []
        for c in raw_candles:
            # Upstox candle format: [timestamp_iso, open, high, low, close, volume, open_interest]
            ts_str = c[0]
            # Convert ISO string to timestamp if needed
            try:
                import datetime
                dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                ts = int(dt.timestamp())
            except Exception:
                ts = int(c[0]) if isinstance(c[0], (int, float)) else 0

            normalized.append({
                "timestamp": ts,
                "time": ts,
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": int(c[5]),
                "source": "UPSTOX"
            })
        
        # Upstox returns newest first; reverse for chronological order
        normalized.reverse()
        return normalized

    async def get_option_chain(self, symbol: str, expiry_date: Optional[str] = None) -> Dict[str, Any]:
        """Fetch Option Chain snapshot for an underlying symbol."""
        inst_key = get_instrument_key(symbol)
        endpoint = f"/v2/option/chain?instrument_key={inst_key}"
        if expiry_date:
            endpoint += f"&expiry_date={expiry_date}"

        res = await self._request("GET", endpoint)
        chain_data = res.get("data", [])

        total_call_oi = 0
        total_put_oi = 0

        strikes_payload = []
        for item in chain_data:
            strike_price = float(item.get("strike_price", 0.0))
            call_data = item.get("call_options", {}).get("market_data", {})
            put_data = item.get("put_options", {}).get("market_data", {})

            c_oi = int(call_data.get("oi", 0) or 0)
            p_oi = int(put_data.get("oi", 0) or 0)
            total_call_oi += c_oi
            total_put_oi += p_oi

            strikes_payload.append({
                "strike": strike_price,
                "call": {
                    "ltp": float(call_data.get("ltp", 0.0) or 0.0),
                    "oi": c_oi,
                    "volume": int(call_data.get("volume", 0) or 0),
                    "iv": float(call_data.get("iv", 0.0) or 0.0) if call_data.get("iv") is not None else None,
                    "delta": None,
                    "gamma": None,
                    "theta": None,
                    "vega": None
                },
                "put": {
                    "ltp": float(put_data.get("ltp", 0.0) or 0.0),
                    "oi": p_oi,
                    "volume": int(put_data.get("volume", 0) or 0),
                    "iv": float(put_data.get("iv", 0.0) or 0.0) if put_data.get("iv") is not None else None,
                    "delta": None,
                    "gamma": None,
                    "theta": None,
                    "vega": None
                }
            })

        pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else 1.0

        return {
            "underlying": symbol,
            "expiry": expiry_date or "NEAR",
            "pcr": pcr,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "strikes": strikes_payload,
            "source": "UPSTOX"
        }
