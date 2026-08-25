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
    """Production-grade async REST client for Upstox with strict instrument identity."""

    def __init__(self, token: str, base_url: str = "https://api.upstox.com"):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.client: Optional[httpx.AsyncClient] = None

    def _get_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}

    async def _init_client(self):
        if self.client is None or self.client.is_closed:
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._get_headers(),
                timeout=httpx.Timeout(10.0, connect=5.0),
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
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
                logger.debug("[UPSTOX REST] %s %s (Attempt %s)", method, endpoint, attempt + 1)
                resp = await self.client.request(method, url, params=params)
                if resp.status_code == 429:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                last_error = e
                logger.error("[UPSTOX REST] HTTP Error %s for %s", e.response.status_code, endpoint)
                if e.response.status_code in (400, 401, 403, 404):
                    break
                await asyncio.sleep(0.5 * (attempt + 1))
            except Exception as e:
                last_error = e
                logger.error("[UPSTOX REST] Request failed for %s: %s", endpoint, e)
                await asyncio.sleep(0.5 * (attempt + 1))
        if last_error:
            raise last_error
        raise RuntimeError(f"Request failed for {endpoint}")

    @staticmethod
    def _quote_body_for_instrument(raw_data: Any, inst_key: str) -> Optional[Dict[str, Any]]:
        """Resolve exactly the requested Upstox instrument; never take an arbitrary first value."""
        if not isinstance(raw_data, dict):
            return None
        candidates = (inst_key, inst_key.replace("|", ":"))
        for key in candidates:
            value = raw_data.get(key)
            if isinstance(value, dict):
                return value
        # Reject ambiguous/mismatched responses rather than guessing.
        if len(raw_data) == 1:
            only_key, only_value = next(iter(raw_data.items()))
            if str(only_key) in candidates and isinstance(only_value, dict):
                return only_value
        return None

    @staticmethod
    def _validate_quote_identity(quote_body: Dict[str, Any], symbol: str, inst_key: str) -> None:
        """Require provider identity to agree with the requested canonical instrument when supplied."""
        provider_key = quote_body.get("instrument_key") or quote_body.get("instrument_token") or quote_body.get("instrumentKey")
        provider_symbol = quote_body.get("symbol") or quote_body.get("trading_symbol") or quote_body.get("tradingSymbol")
        if provider_key is not None and str(provider_key).replace(":", "|") != inst_key:
            raise ValueError(f"Upstox instrument identity mismatch for {symbol}: expected {inst_key}, got {provider_key}")
        if provider_symbol is not None:
            meta = get_instrument_metadata(symbol) or {}
            expected_symbol = str(meta.get("trading_symbol") or symbol).upper()
            actual_symbol = str(provider_symbol).upper()
            if actual_symbol not in {expected_symbol, symbol.upper(), symbol.upper().replace(".NS", "") }:
                raise ValueError(f"Upstox symbol identity mismatch for {symbol}: got {provider_symbol}")

    @staticmethod
    def _normalize_quote(quote_body: Dict[str, Any], symbol: str, inst_key: str) -> Dict[str, Any]:
        ohlc = quote_body.get("ohlc", {}) or {}
        depth = quote_body.get("depth", {}) or {}
        bids = depth.get("buy", []) or []
        asks = depth.get("sell", []) or []
        ltp_raw = quote_body.get("last_price")
        if ltp_raw is None:
            ltp_raw = quote_body.get("close")
        if ltp_raw is None:
            raise ValueError(f"Upstox returned no price for {symbol}")
        ltp = float(ltp_raw)
        if ltp <= 0:
            raise ValueError(f"Upstox returned invalid price for {symbol}: {ltp}")
        cp_raw = ohlc.get("close")
        prev_close = float(cp_raw) if cp_raw is not None and float(cp_raw) > 0 else None
        change = round(ltp - prev_close, 2) if prev_close is not None else None
        change_pct = round((change / prev_close) * 100, 2) if prev_close and change is not None else None
        meta = get_instrument_metadata(symbol) or {}
        raw_open, raw_high, raw_low = ohlc.get("open"), ohlc.get("high"), ohlc.get("low")
        return {
            "symbol": symbol,
            "instrument_key": inst_key,
            "provider_instrument_key": inst_key,
            "provider_symbol": quote_body.get("symbol") or quote_body.get("trading_symbol") or symbol,
            "exchange": meta.get("exchange", "NSE"),
            "instrument_type": meta.get("instrument_type", "EQUITY"),
            "ltp": ltp,
            "open": float(raw_open) if raw_open is not None else None,
            "high": float(raw_high) if raw_high is not None else None,
            "low": float(raw_low) if raw_low is not None else None,
            "close": float(cp_raw) if cp_raw is not None else None,
            "previous_close": prev_close,
            "change": change,
            "change_percent": change_pct,
            "volume": int(quote_body.get("volume", 0) or 0),
            "open_interest": int(quote_body.get("oi", 0) or 0),
            "bid": float(bids[0].get("price")) if bids and bids[0].get("price") is not None else None,
            "ask": float(asks[0].get("price")) if asks and asks[0].get("price") is not None else None,
            "timestamp": parse_upstox_timestamp(quote_body.get("timestamp")),
            "source": "UPSTOX",
            "provider": "UPSTOX",
            "provider_mode": "AUTHENTIC_LIVE",
            "data_status": "LIVE",
            "market_status": "LIVE",
            "freshness": "LIVE",
            "is_live": True,
            "price_domain": "RAW_EXCHANGE_PRICE",
            "adjustment_status": "RAW_EXCHANGE_PRICE",
        }

    async def get_ws_authorize_url(self) -> str:
        res = await self._request("GET", "/v3/feed/market-data-feed/authorize")
        data = res.get("data", {})
        ws_url = data.get("authorizedRedirectUri") or data.get("wsUrl") or data.get("authorized_redirect_uri")
        if not ws_url:
            raise ValueError("Upstox WS authorization did not return a valid redirect URI.")
        return ws_url

    async def get_full_quote(self, symbol: str) -> Dict[str, Any]:
        inst_key = get_instrument_key(symbol)
        if not inst_key:
            raise ValueError(f"Unknown or unresolved instrument symbol: {symbol}")
        endpoint = f"/v2/market-quote/quotes?instrument_key={inst_key}"
        res = await self._request("GET", endpoint)
        raw_data = res.get("data", {})
        quote_body = self._quote_body_for_instrument(raw_data, inst_key)
        if quote_body is None:
            ohlc_res = await self._request("GET", f"/v2/market-quote/ohlc?instrument_key={inst_key}&interval=1d")
            quote_body = self._quote_body_for_instrument(ohlc_res.get("data", {}), inst_key)
        if quote_body is None:
            raise ValueError(f"No identity-matched market quote returned from Upstox for {symbol} ({inst_key})")
        self._validate_quote_identity(quote_body, symbol, inst_key)
        return self._normalize_quote(quote_body, symbol, inst_key)

    async def get_multi_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        if not symbols:
            return []
        keys = [get_instrument_key(s) for s in symbols if get_instrument_key(s)]
        if not keys:
            return []
        res = await self._request("GET", f"/v2/market-quote/quotes?instrument_key={','.join(keys)}")
        raw_data = res.get("data", {})
        results = []
        for symbol in symbols:
            inst_key = get_instrument_key(symbol)
            if not inst_key:
                continue
            quote_body = self._quote_body_for_instrument(raw_data, inst_key)
            if quote_body is None:
                continue
            try:
                self._validate_quote_identity(quote_body, symbol, inst_key)
                results.append(self._normalize_quote(quote_body, symbol, inst_key))
            except ValueError as exc:
                logger.error("[UPSTOX REST] Rejecting mismatched quote for %s: %s", symbol, exc)
        return results

    async def get_historical_candles(self, symbol: str, interval: str = "5m", to_date: Optional[str] = None, from_date: Optional[str] = None) -> List[Dict[str, Any]]:
        import urllib.parse
        import datetime
        inst_key = get_instrument_key(symbol)
        upstox_supported_map = {"1m": "1minute", "30m": "30minute", "1D": "day"}
        mapped_interval = upstox_supported_map.get(interval)
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
                        normalized.append({"timestamp": ts, "time": ts, "open": float(c[1]), "high": float(c[2]), "low": float(c[3]), "close": float(c[4]), "volume": int(c[5]) if len(c) > 5 else 0, "source": "UPSTOX", "is_live": False, "provider": "UPSTOX", "symbol": symbol, "instrument_key": inst_key, "price_domain": "RAW_EXCHANGE_PRICE", "adjustment_status": "RAW_EXCHANGE_PRICE"})
                    normalized.reverse()
                    if normalized:
                        return normalized
            except Exception as e:
                logger.info("[UPSTOX REST] Native candle query for %s failed/skipped: %s", symbol, e)
        try:
            ticker_map = {"NIFTY 50": "^NSEI", "NIFTY50": "^NSEI", "NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "BANK NIFTY": "^NSEBANK", "FINNIFTY": "NIFTY_FIN_SERVICE.NS", "SENSEX": "^BSESN", "INDIA VIX": "^INDIAVIX"}
            clean_sym = symbol.strip()
            yf_ticker = ticker_map.get(clean_sym, clean_sym if clean_sym.endswith(".NS") or clean_sym.endswith(".BO") else f"{clean_sym}.NS")
            yf_interval = "1m" if interval == "1m" else ("5m" if interval == "5m" else ("15m" if interval == "15m" else ("60m" if interval == "1h" else "1d")))
            yf_range = "5d" if interval in ("1m", "5m") else ("1mo" if interval in ("15m", "1h") else "1y")
            yf_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(yf_ticker)}?interval={yf_interval}&range={yf_range}"
            async with httpx.AsyncClient(timeout=4.0) as client:
                r = await client.get(yf_url, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    body = r.json().get("chart", {}).get("result", [{}])[0]
                    timestamps = body.get("timestamp", [])
                    q = body.get("indicators", {}).get("quote", [{}])[0]
                    yf_candles = []
                    for i, t in enumerate(timestamps):
                        if i < len(q.get("open", [])) and q.get("open", [])[i] is not None and q.get("close", [])[i] is not None:
                            o, c = float(q["open"][i]), float(q["close"][i])
                            h = float(q.get("high", [None] * len(timestamps))[i]) if q.get("high", [None] * len(timestamps))[i] is not None else max(o, c)
                            l = float(q.get("low", [None] * len(timestamps))[i]) if q.get("low", [None] * len(timestamps))[i] is not None else min(o, c)
                            v = int(q.get("volume", [0] * len(timestamps))[i] or 0)
                            yf_candles.append({"timestamp": int(t), "time": int(t), "open": round(o, 2), "high": round(h, 2), "low": round(l, 2), "close": round(c, 2), "volume": v, "source": "YAHOO_FINANCE", "provider": "YAHOO_FINANCE", "is_live": False, "symbol": symbol, "instrument_key": inst_key, "price_domain": "RAW_EXCHANGE_PRICE", "adjustment_status": "RAW_EXCHANGE_PRICE"})
                    if yf_candles:
                        return yf_candles
        except Exception as e:
            logger.error("[YAHOO_FINANCE FEED] Historical candle fetch failed for %s: %s", symbol, e)
        return []

    async def get_option_chain(self, symbol: str, expiry_date: Optional[str] = None) -> Dict[str, Any]:
        inst_key = get_instrument_key(symbol)
        if not inst_key:
            return {"status": "UNAVAILABLE", "source": "UPSTOX", "reason": "UNKNOWN_INSTRUMENT_KEY", "symbol": symbol, "strikes": []}
        endpoint = f"/v2/option/chain?instrument_key={inst_key}"
        if expiry_date:
            endpoint += f"&expiry_date={expiry_date}"
        try:
            chain_data = (await self._request("GET", endpoint)).get("data", [])
        except Exception as e:
            logger.warning("[UPSTOX REST] Option chain unavailable for %s: %s", symbol, e)
            chain_data = []
        if not chain_data:
            return {"status": "UNAVAILABLE", "source": "UPSTOX", "reason": "OPTION_CHAIN_DATA_UNAVAILABLE", "symbol": symbol, "spotPrice": None, "atmStrike": None, "pcr": None, "maxPainStrike": None, "totalCallOI": None, "totalPutOI": None, "impliedVolatility": None, "expiryDate": expiry_date or "UNAVAILABLE", "strikes": []}
        total_call_oi = total_put_oi = 0
        strikes_payload, iv_list = [], []
        for item in chain_data:
            strike_price = float(item.get("strike_price", 0.0))
            call_data = item.get("call_options", {}).get("market_data", {})
            put_data = item.get("put_options", {}).get("market_data", {})
            c_oi, p_oi = int(call_data.get("oi", 0) or 0), int(put_data.get("oi", 0) or 0)
            total_call_oi += c_oi; total_put_oi += p_oi
            c_iv = float(call_data.get("iv")) if call_data.get("iv") is not None else None
            p_iv = float(put_data.get("iv")) if put_data.get("iv") is not None else None
            if c_iv and c_iv > 0: iv_list.append(c_iv)
            if p_iv and p_iv > 0: iv_list.append(p_iv)
            strikes_payload.append({"strike": strike_price, "call": {"ltp": float(call_data.get("ltp", 0.0) or 0.0), "oi": c_oi, "volume": int(call_data.get("volume", 0) or 0), "iv": c_iv}, "put": {"ltp": float(put_data.get("ltp", 0.0) or 0.0), "oi": p_oi, "volume": int(put_data.get("volume", 0) or 0), "iv": p_iv}})
        spot_price = None
        try: spot_price = (await self.get_full_quote(symbol)).get("ltp")
        except Exception: pass
        atm = round(spot_price / 50.0) * 50 if spot_price else (strikes_payload[len(strikes_payload)//2]["strike"] if strikes_payload else None)
        pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else None
        max_pain = None
        if strikes_payload:
            min_loss = float("inf")
            for target in strikes_payload:
                loss = 0.0; t_strike = target["strike"]
                for item in strikes_payload:
                    s = item["strike"]
                    loss += max(0.0, t_strike - s) * item["call"]["oi"]
                    loss += max(0.0, s - t_strike) * item["put"]["oi"]
                if loss < min_loss: min_loss, max_pain = loss, t_strike
        return {"status": "AVAILABLE", "symbol": symbol, "spotPrice": spot_price, "atmStrike": atm, "pcr": pcr, "maxPainStrike": max_pain, "totalCallOI": total_call_oi, "totalPutOI": total_put_oi, "impliedVolatility": round(sum(iv_list)/len(iv_list), 2) if iv_list else None, "expiryDate": expiry_date or "NEAR", "strikes": strikes_payload, "source": "UPSTOX", "is_live": True}
