import logging
import asyncio
import time
from typing import Dict, Any, List, Optional
import httpx
from backend.app.market.instruments import get_instrument_key, get_instrument_metadata

logger = logging.getLogger(__name__)

def parse_upstox_timestamp(ts_val: Any) -> float:
    if not ts_val:
        return time.time()
    if isinstance(ts_val, (int, float)):
        return float(ts_val) / 1000.0 if ts_val > 1e11 else float(ts_val)
    if isinstance(ts_val, str):
        try:
            val = float(ts_val)
            return val / 1000.0 if val > 1e11 else val
        except ValueError:
            pass
        try:
            import datetime
            dt = datetime.datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            pass
    return time.time()

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
                if e.response.status_code in (400, 401, 403, 404):
                    # Bad Request, Auth failure, or Not Found - do not retry
                    break
                await asyncio.sleep(0.5 * (attempt + 1))
            except Exception as e:
                last_error = e
                logger.error(f"[UPSTOX REST] Request failed for {endpoint}: {str(e)}")
                await asyncio.sleep(0.5 * (attempt + 1))


        if last_error:
            raise last_error
        raise RuntimeError(f"Request failed for {endpoint}")

    async def get_ws_authorize_url(self) -> str:
        """Fetch authorized WebSocket redirect URL from Upstox Feed Authorization API."""
        endpoint = "/v3/feed/market-data-feed/authorize"
        res = await self._request("GET", endpoint)
        data = res.get("data", {})
        ws_url = data.get("authorizedRedirectUri") or data.get("wsUrl") or data.get("authorized_redirect_uri")
        if not ws_url:
            raise ValueError("Upstox WS authorization did not return a valid redirect URI.")
        return ws_url

    async def get_full_quote(self, symbol: str) -> Dict[str, Any]:
        """Fetch full market quote snapshot for an instrument."""
        inst_key = get_instrument_key(symbol)
        if not inst_key:
            raise ValueError(f"Unknown or unresolved instrument symbol: {symbol}")

        endpoint = f"/v2/market-quote/quotes?instrument_key={inst_key}"
        res = await self._request("GET", endpoint)
        raw_data = res.get("data", {})
        
        quote_body = None
        for k, v in raw_data.items():
            quote_body = v
            break
            
        if not quote_body:
            # Try ohlc endpoint fallback if quotes is empty
            ohlc_res = await self._request("GET", f"/v2/market-quote/ohlc?instrument_key={inst_key}&interval=1d")
            quote_body = ohlc_res.get("data", {}).get(inst_key.replace("|", ":"), {})

        if not quote_body:
            raise ValueError(f"No market quote data returned from Upstox for {symbol}")

        ohlc = quote_body.get("ohlc", {})
        depth = quote_body.get("depth", {})
        bids = depth.get("buy", [])
        asks = depth.get("sell", [])

        ltp = float(quote_body.get("last_price", 0.0) or quote_body.get("close", 0.0))
        cp_raw = ohlc.get("close")
        prev_close = float(cp_raw) if cp_raw is not None and float(cp_raw) > 0 else (ltp if ltp > 0 else None)
        
        if prev_close is not None and prev_close > 0:
            change = round(ltp - prev_close, 2)
            change_pct = round((change / prev_close) * 100, 2)
        else:
            change = 0.0
            change_pct = 0.0

        meta = get_instrument_metadata(symbol) or {}

        raw_open = ohlc.get("open")
        raw_high = ohlc.get("high")
        raw_low = ohlc.get("low")

        return {
            "symbol": symbol,
            "instrument_key": inst_key,
            "exchange": meta.get("exchange", "NSE"),
            "instrument_type": meta.get("instrument_type", "EQUITY"),
            "ltp": ltp,
            "open": float(raw_open) if raw_open is not None else ltp,
            "high": float(raw_high) if raw_high is not None else ltp,
            "low": float(raw_low) if raw_low is not None else ltp,
            "close": ltp,
            "previous_close": prev_close,
            "change": change,
            "change_percent": change_pct,
            "volume": int(quote_body.get("volume", 0) or 0),
            "open_interest": int(quote_body.get("oi", 0) or 0),
            "bid": float(bids[0].get("price", 0.0)) if bids and bids[0].get("price") is not None else None,
            "ask": float(asks[0].get("price", 0.0)) if asks and asks[0].get("price") is not None else None,
            "timestamp": parse_upstox_timestamp(quote_body.get("timestamp")),
            "source": "UPSTOX",
            "is_live": True
        }

    async def get_multi_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Fetch market quotes for multiple symbols in a single Upstox API request."""
        if not symbols:
            return []
        keys = [get_instrument_key(s) for s in symbols if get_instrument_key(s)]
        if not keys:
            return []
        comma_keys = ",".join(keys)
        endpoint = f"/v2/market-quote/quotes?instrument_key={comma_keys}"
        try:
            res = await self._request("GET", endpoint)
            raw_data = res.get("data", {})
        except Exception as e:
            logger.error(f"[UPSTOX REST] Multi-quote request failed: {str(e)}")
            raw_data = {}

        results = []
        for symbol in symbols:
            inst_key = get_instrument_key(symbol)
            if not inst_key:
                continue
            inst_colon = inst_key.replace("|", ":")
            quote_body = raw_data.get(inst_key) or raw_data.get(inst_colon) or {}
            
            if quote_body:
                ohlc = quote_body.get("ohlc", {})
                depth = quote_body.get("depth", {})
                bids = depth.get("buy", [])
                asks = depth.get("sell", [])
                ltp = float(quote_body.get("last_price", 0.0) or quote_body.get("close", 0.0))
                cp_raw = ohlc.get("close")
                prev_close = float(cp_raw) if cp_raw is not None and float(cp_raw) > 0 else (ltp if ltp > 0 else None)
                
                if prev_close is not None and prev_close > 0:
                    change = round(ltp - prev_close, 2)
                    change_pct = round((change / prev_close) * 100, 2)
                else:
                    change = 0.0
                    change_pct = 0.0

                meta = get_instrument_metadata(symbol) or {}
                raw_open = ohlc.get("open")
                raw_high = ohlc.get("high")
                raw_low = ohlc.get("low")

                results.append({
                    "symbol": symbol,
                    "instrument_key": inst_key,
                    "exchange": meta.get("exchange", "NSE"),
                    "instrument_type": meta.get("instrument_type", "EQUITY"),
                    "ltp": ltp,
                    "open": float(raw_open) if raw_open is not None else ltp,
                    "high": float(raw_high) if raw_high is not None else ltp,
                    "low": float(raw_low) if raw_low is not None else ltp,
                    "close": ltp,
                    "previous_close": prev_close,
                    "change": change,
                    "change_percent": change_pct,
                    "volume": int(quote_body.get("volume", 0) or 0),
                    "open_interest": int(quote_body.get("oi", 0) or 0),
                    "bid": float(bids[0].get("price", 0.0)) if bids and bids[0].get("price") is not None else None,
                    "ask": float(asks[0].get("price", 0.0)) if asks and asks[0].get("price") is not None else None,
                    "timestamp": parse_upstox_timestamp(quote_body.get("timestamp")),
                    "source": "UPSTOX",
                    "is_live": True
                })
            else:
                try:
                    single = await self.get_full_quote(symbol)
                    results.append(single)
                except Exception:
                    pass

        return results

    async def get_historical_candles(
        self, symbol: str, interval: str = "5m", to_date: Optional[str] = None, from_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch historical candle series with provenance tracking (UPSTOX or YAHOO_FINANCE fallback)."""
        import urllib.parse
        import datetime

        inst_key = get_instrument_key(symbol)
        
        # Upstox only natively supports: 1minute, 30minute, day, week, month
        upstox_supported_map = {
            "1m": "1minute",
            "30m": "30minute",
            "1D": "day"
        }
        mapped_interval = upstox_supported_map.get(interval)

        # 1. If Upstox natively supports the interval and inst_key is known, try Upstox API first
        if mapped_interval and inst_key:
            try:
                encoded_key = urllib.parse.quote(inst_key, safe="")
                endpoint = f"/v2/historical-candle/{encoded_key}/{mapped_interval}/{to_date}/{from_date}"
                res = await self._request("GET", endpoint)
                raw_candles = res.get("data", {}).get("candles", [])
                if raw_candles:
                    normalized = []
                    for c in raw_candles:
                        ts_str = c[0]
                        try:
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
                            "volume": int(c[5]) if len(c) > 5 else 0,
                            "source": "UPSTOX",
                            "is_live": True
                        })
                    normalized.reverse()
                    if normalized:
                        return normalized
            except Exception as e:
                logger.info(f"[UPSTOX REST] Native candle query for {symbol} ({interval}) failed/skipped: {str(e)}")

        # 2. Authentic Market Feed Fallback (Yahoo Finance Chart Engine)
        try:
            ticker_map = {
                "NIFTY 50": "^NSEI",
                "NIFTY50": "^NSEI",
                "NIFTY": "^NSEI",
                "BANKNIFTY": "^NSEBANK",
                "BANK NIFTY": "^NSEBANK",
                "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
                "SENSEX": "^BSESN",
                "INDIA VIX": "^INDIAVIX"
            }
            clean_sym = symbol.strip()
            yf_ticker = ticker_map.get(clean_sym, clean_sym if clean_sym.endswith(".NS") or clean_sym.endswith(".BO") else f"{clean_sym}.NS")
            
            yf_interval = "1m" if interval == "1m" else ("5m" if interval == "5m" else ("15m" if interval == "15m" else ("60m" if interval == "1h" else "1d")))
            yf_range = "5d" if interval in ("1m", "5m") else ("1mo" if interval in ("15m", "1h") else "1y")

            yf_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(yf_ticker)}?interval={yf_interval}&range={yf_range}"
            async with httpx.AsyncClient(timeout=4.0) as client:
                r = await client.get(yf_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                if r.status_code == 200:
                    data = r.json()
                    res_body = data.get("chart", {}).get("result", [{}])[0]
                    timestamps = res_body.get("timestamp", [])
                    quote_data = res_body.get("indicators", {}).get("quote", [{}])[0]
                    opens = quote_data.get("open", [])
                    highs = quote_data.get("high", [])
                    lows = quote_data.get("low", [])
                    closes = quote_data.get("close", [])
                    volumes = quote_data.get("volume", [])

                    yf_candles = []
                    for i, t in enumerate(timestamps):
                        if i < len(opens) and opens[i] is not None and closes[i] is not None:
                            o = float(opens[i])
                            c = float(closes[i])
                            h = float(highs[i]) if highs[i] is not None else max(o, c)
                            l = float(lows[i]) if lows[i] is not None else min(o, c)
                            v = int(volumes[i]) if i < len(volumes) and volumes[i] is not None else 0
                            yf_candles.append({
                                "timestamp": int(t),
                                "time": int(t),
                                "open": round(o, 2),
                                "high": round(h, 2),
                                "low": round(l, 2),
                                "close": round(c, 2),
                                "volume": v,
                                "source": "YAHOO_FINANCE",
                                "is_live": False
                            })
                    if yf_candles:
                        return yf_candles
        except Exception as e:
            logger.error(f"[YAHOO_FINANCE FEED] Historical candle fetch failed for {symbol}: {str(e)}")

        return []

    async def get_option_chain(self, symbol: str, expiry_date: Optional[str] = None) -> Dict[str, Any]:
        """Fetch Option Chain snapshot for an underlying symbol without synthetic fallbacks."""
        inst_key = get_instrument_key(symbol)
        if not inst_key:
            return {
                "status": "UNAVAILABLE",
                "source": "UPSTOX",
                "reason": "UNKNOWN_INSTRUMENT_KEY",
                "symbol": symbol,
                "strikes": []
            }

        endpoint = f"/v2/option/chain?instrument_key={inst_key}"
        if expiry_date:
            endpoint += f"&expiry_date={expiry_date}"

        try:
            res = await self._request("GET", endpoint)
            chain_data = res.get("data", [])
        except Exception as e:
            logger.warning(f"[UPSTOX REST] Option chain fetch unavailable for {symbol}: {str(e)}")
            chain_data = []

        if not chain_data:
            return {
                "status": "UNAVAILABLE",
                "source": "UPSTOX",
                "reason": "OPTION_CHAIN_DATA_UNAVAILABLE",
                "symbol": symbol,
                "spotPrice": None,
                "atmStrike": None,
                "pcr": None,
                "maxPainStrike": None,
                "totalCallOI": None,
                "totalPutOI": None,
                "impliedVolatility": None,
                "expiryDate": expiry_date or "UNAVAILABLE",
                "strikes": []
            }

        total_call_oi = 0
        total_put_oi = 0
        strikes_payload = []
        iv_list = []

        for item in chain_data:
            strike_price = float(item.get("strike_price", 0.0))
            call_data = item.get("call_options", {}).get("market_data", {})
            put_data = item.get("put_options", {}).get("market_data", {})

            c_oi = int(call_data.get("oi", 0) or 0)
            p_oi = int(put_data.get("oi", 0) or 0)
            total_call_oi += c_oi
            total_put_oi += p_oi

            c_iv = float(call_data.get("iv")) if call_data.get("iv") is not None else None
            p_iv = float(put_data.get("iv")) if put_data.get("iv") is not None else None
            if c_iv and c_iv > 0:
                iv_list.append(c_iv)
            if p_iv and p_iv > 0:
                iv_list.append(p_iv)

            strikes_payload.append({
                "strike": strike_price,
                "call": {
                    "ltp": float(call_data.get("ltp", 0.0) or 0.0),
                    "oi": c_oi,
                    "volume": int(call_data.get("volume", 0) or 0),
                    "iv": c_iv,
                },
                "put": {
                    "ltp": float(put_data.get("ltp", 0.0) or 0.0),
                    "oi": p_oi,
                    "volume": int(put_data.get("volume", 0) or 0),
                    "iv": p_iv,
                }
            })

        spot_price = None
        try:
            q = await self.get_full_quote(symbol)
            spot_price = q.get("ltp")
        except Exception:
            pass

        atm = round(spot_price / 50.0) * 50 if spot_price else (strikes_payload[len(strikes_payload) // 2]["strike"] if strikes_payload else None)
        pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else None
        
        # Real Max Pain calculation from strikes
        max_pain = None
        if strikes_payload:
            min_loss = float("inf")
            for target in strikes_payload:
                t_strike = target["strike"]
                loss = 0.0
                for s_item in strikes_payload:
                    s_price = s_item["strike"]
                    loss += max(0.0, t_strike - s_price) * s_item["call"]["oi"]
                    loss += max(0.0, s_price - t_strike) * s_item["put"]["oi"]
                if loss < min_loss:
                    min_loss = loss
                    max_pain = t_strike

        avg_iv = round(sum(iv_list) / len(iv_list), 2) if iv_list else None

        return {
            "status": "AVAILABLE",
            "symbol": symbol,
            "spotPrice": spot_price,
            "atmStrike": atm,
            "pcr": pcr,
            "maxPainStrike": max_pain,
            "totalCallOI": total_call_oi,
            "totalPutOI": total_put_oi,
            "impliedVolatility": avg_iv,
            "expiryDate": expiry_date or "NEAR",
            "strikes": strikes_payload,
            "source": "UPSTOX",
            "is_live": True
        }
