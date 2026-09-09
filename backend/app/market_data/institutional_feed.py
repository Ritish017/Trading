import time
import logging
import datetime
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

IST_TZ = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

# Cached flow data in memory with TTL
_CACHED_FLOW: Optional[Dict[str, Any]] = None
_CACHE_TIMESTAMP: float = 0
_CACHE_TTL_SECONDS: float = 300.0  # 5 minutes cache


async def get_fii_dii_flow() -> Dict[str, Any]:
    """
    Fetch authentic FII / DII cash & derivative settlement flows from NSE clearing.
    Follows authoritative engineering principle:
      - Authentic today's settlement: status = LIVE, is_live = True, is_today = True
      - Authentic previous session settlement: status = PREVIOUS_SESSION, is_live = False, is_today = False
      - Source unavailable: status = DATA_PENDING, is_live = False, data = null
    Never labels previous-day or static fallback data as today's live data.
    """
    global _CACHED_FLOW, _CACHE_TIMESTAMP

    now = time.time()
    today_ist = datetime.datetime.now(IST_TZ).strftime("%d-%b-%Y")

    # If recent live cache is still fresh, return cached copy with date status
    if _CACHED_FLOW and (now - _CACHE_TIMESTAMP) < _CACHE_TTL_SECONDS:
        fresh_copy = dict(_CACHED_FLOW)
        flow_date = str(fresh_copy.get("date") or "").strip()
        is_today = (flow_date.lower() == today_ist.lower())
        fresh_copy["is_today"] = is_today
        fresh_copy["status"] = "LIVE" if is_today else "PREVIOUS_SESSION"
        fresh_copy["is_live"] = is_today
        return fresh_copy

    try:
        # Attempt to query live NSE public settlement feed
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        async with httpx.AsyncClient(timeout=4.0, headers=headers, follow_redirects=True) as client:
            resp = await client.get("https://www.nseindia.com/api/fiidiiTradeReact")
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) >= 2:
                    fii_net = 0.0
                    dii_net = 0.0
                    date_val = None
                    for item in data:
                        cat = str(item.get("category", "")).upper()
                        net_val = float(str(item.get("netValue", "0")).replace(",", ""))
                        date_val = str(item.get("date", "")).strip()
                        if "FII" in cat or "FPI" in cat:
                            fii_net = net_val
                        elif "DII" in cat:
                            dii_net = net_val

                    is_today = bool(date_val and date_val.lower() == today_ist.lower())
                    status = "LIVE" if is_today else "PREVIOUS_SESSION"

                    live_flow = {
                        "date": date_val,
                        "trading_date": date_val,
                        "is_today": is_today,
                        "fiiCashNetCr": round(fii_net, 2),
                        "diiCashNetCr": round(dii_net, 2),
                        "fiiIndexFuturesCr": None,
                        "fiiIndexOptionsCr": None,
                        "fiiStockFuturesCr": None,
                        "status": status,
                        "provenance": f"AUTHENTIC_EXCHANGE_SETTLEMENT_{date_val}" if date_val else "AUTHENTIC_EXCHANGE_SETTLEMENT",
                        "source": "NSE/NSDL",
                        "is_live": is_today,
                        "timestamp": now,
                    }
                    _CACHED_FLOW = live_flow
                    _CACHE_TIMESTAMP = now
                    return live_flow
    except Exception as e:
        logger.debug(f"[INSTITUTIONAL FEED] Live NSE settlement fetch failed ({e}).")

    # If live fetch fails, check if we have an older cached value
    if _CACHED_FLOW:
        stale_copy = dict(_CACHED_FLOW)
        stale_copy["status"] = "STALE"
        stale_copy["is_live"] = False
        return stale_copy

    # Otherwise truthfully return DATA_PENDING with null data
    return {
        "date": None,
        "trading_date": None,
        "is_today": False,
        "fiiCashNetCr": None,
        "diiCashNetCr": None,
        "fiiIndexFuturesCr": None,
        "fiiIndexOptionsCr": None,
        "fiiStockFuturesCr": None,
        "status": "DATA_PENDING",
        "provenance": "PENDING_EXCHANGE_DISCLOSURE",
        "source": "NSE/NSDL",
        "is_live": False,
        "data": None,
        "timestamp": now,
        "error": "Verified institutional flow data pending exchange publication",
    }
