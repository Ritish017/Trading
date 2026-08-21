from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Master dictionary mapping symbol aliases to official Upstox Instrument Keys & metadata
INSTRUMENT_MAP: Dict[str, Dict[str, Any]] = {
    # Benchmark Indices
    "NIFTY 50": {
        "instrument_key": "NSE_INDEX|Nifty 50",
        "exchange": "NSE",
        "segment": "NSE_INDEX",
        "instrument_type": "INDEX",
        "display_name": "NIFTY 50 Benchmark"
    },
    "NIFTY50": {
        "instrument_key": "NSE_INDEX|Nifty 50",
        "exchange": "NSE",
        "segment": "NSE_INDEX",
        "instrument_type": "INDEX",
        "display_name": "NIFTY 50 Benchmark"
    },
    "BANKNIFTY": {
        "instrument_key": "NSE_INDEX|Nifty Bank",
        "exchange": "NSE",
        "segment": "NSE_INDEX",
        "instrument_type": "INDEX",
        "display_name": "NIFTY Bank Index"
    },
    "BANK NIFTY": {
        "instrument_key": "NSE_INDEX|Nifty Bank",
        "exchange": "NSE",
        "segment": "NSE_INDEX",
        "instrument_type": "INDEX",
        "display_name": "NIFTY Bank Index"
    },
    "FINNIFTY": {
        "instrument_key": "NSE_INDEX|Nifty Fin Service",
        "exchange": "NSE",
        "segment": "NSE_INDEX",
        "instrument_type": "INDEX",
        "display_name": "NIFTY Financial Services"
    },
    "INDIA VIX": {
        "instrument_key": "NSE_INDEX|India VIX",
        "exchange": "NSE",
        "segment": "NSE_INDEX",
        "instrument_type": "INDEX",
        "display_name": "India Volatility Index"
    },
    "SENSEX": {
        "instrument_key": "BSE_INDEX|SENSEX",
        "exchange": "BSE",
        "segment": "BSE_INDEX",
        "instrument_type": "INDEX",
        "display_name": "BSE SENSEX 30"
    },

    # Major NSE Equities
    "RELIANCE.NS": {
        "instrument_key": "NSE_EQ|INE002A01018",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Reliance Industries Ltd"
    },
    "RELIANCE": {
        "instrument_key": "NSE_EQ|INE002A01018",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Reliance Industries Ltd"
    },
    "TCS.NS": {
        "instrument_key": "NSE_EQ|INE467B01029",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Tata Consultancy Services"
    },
    "TCS": {
        "instrument_key": "NSE_EQ|INE467B01029",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Tata Consultancy Services"
    },
    "HDFCBANK.NS": {
        "instrument_key": "NSE_EQ|INE040A01034",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "HDFC Bank Ltd"
    },
    "HDFCBANK": {
        "instrument_key": "NSE_EQ|INE040A01034",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "HDFC Bank Ltd"
    },
    "ICICIBANK.NS": {
        "instrument_key": "NSE_EQ|INE090A01021",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "ICICI Bank Ltd"
    },
    "ICICIBANK": {
        "instrument_key": "NSE_EQ|INE090A01021",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "ICICI Bank Ltd"
    },
    "INFY.NS": {
        "instrument_key": "NSE_EQ|INE009A01021",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Infosys Ltd"
    },
    "INFY": {
        "instrument_key": "NSE_EQ|INE009A01021",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Infosys Ltd"
    },
    "SBIN.NS": {
        "instrument_key": "NSE_EQ|INE062A01020",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "State Bank of India"
    },
    "SBIN": {
        "instrument_key": "NSE_EQ|INE062A01020",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "State Bank of India"
    },
    "TATAMOTORS.NS": {
        "instrument_key": "NSE_EQ|INE155A01022",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Tata Motors Ltd"
    },
    "TATAMOTORS": {
        "instrument_key": "NSE_EQ|INE155A01022",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Tata Motors Ltd"
    },
    "MRF.NS": {
        "instrument_key": "NSE_EQ|INE883A01011",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "MRF Limited"
    },
    "MRF": {
        "instrument_key": "NSE_EQ|INE883A01011",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "MRF Limited"
    },
    "MARUTI.NS": {
        "instrument_key": "NSE_EQ|INE585B01010",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Maruti Suzuki India Ltd"
    },
    "MARUTI": {
        "instrument_key": "NSE_EQ|INE585B01010",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Maruti Suzuki India Ltd"
    },
    "M&M.NS": {
        "instrument_key": "NSE_EQ|INE101A01026",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Mahindra & Mahindra Ltd"
    },
    "M&M": {
        "instrument_key": "NSE_EQ|INE101A01026",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Mahindra & Mahindra Ltd"
    },
    "WIPRO.NS": {
        "instrument_key": "NSE_EQ|INE075A01022",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Wipro Limited"
    },
    "WIPRO": {
        "instrument_key": "NSE_EQ|INE075A01022",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Wipro Limited"
    },
    "TITAN.NS": {
        "instrument_key": "NSE_EQ|INE280A01028",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Titan Company Ltd"
    },
    "TITAN": {
        "instrument_key": "NSE_EQ|INE280A01028",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Titan Company Ltd"
    },
    "TATASTEEL.NS": {
        "instrument_key": "NSE_EQ|INE081A01020",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Tata Steel Ltd"
    },
    "TATASTEEL": {
        "instrument_key": "NSE_EQ|INE081A01020",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Tata Steel Ltd"
    },
    "ZOMATO.NS": {
        "instrument_key": "NSE_EQ|INE758T01015",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Zomato Limited"
    },
    "ZOMATO": {
        "instrument_key": "NSE_EQ|INE758T01015",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Zomato Limited"
    },
    "COALINDIA.NS": {
        "instrument_key": "NSE_EQ|INE522F01014",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Coal India Ltd"
    },
    "COALINDIA": {
        "instrument_key": "NSE_EQ|INE522F01014",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Coal India Ltd"
    },
    "ADANIENT.NS": {
        "instrument_key": "NSE_EQ|INE423A01024",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Adani Enterprises Ltd"
    },
    "ADANIENT": {
        "instrument_key": "NSE_EQ|INE423A01024",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Adani Enterprises Ltd"
    },
    "TATAMOTORS.NS": {
        "instrument_key": "NSE_EQ|INE155A01022",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Tata Motors Ltd"
    },
    "TATAMOTORS": {
        "instrument_key": "NSE_EQ|INE155A01022",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Tata Motors Ltd"
    },
    "NIFTY IT": {
        "instrument_key": "NSE_INDEX|Nifty IT",
        "exchange": "NSE",
        "segment": "NSE_INDEX",
        "instrument_type": "INDEX",
        "display_name": "NIFTY IT Index"
    },
    "NIFTYIT": {
        "instrument_key": "NSE_INDEX|Nifty IT",
        "exchange": "NSE",
        "segment": "NSE_INDEX",
        "instrument_type": "INDEX",
        "display_name": "NIFTY IT Index"
    },
    "ASIANPAINT.NS": {
        "instrument_key": "NSE_EQ|INE021A01026",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Asian Paints Ltd"
    },
    "ASIANPAINT": {
        "instrument_key": "NSE_EQ|INE021A01026",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": "Asian Paints Ltd"
    }
}

def normalize_symbol_alias(symbol: str) -> str:
    """Normalize symbol to standard uppercase canonical alias format."""
    clean = symbol.strip().upper()
    if clean.endswith(".NS"):
        clean_base = clean[:-3]
        return f"{clean_base}.NS"
    return clean

def get_instrument_key(symbol: str) -> Optional[str]:
    """
    Resolve symbol string to official Upstox instrument key.
    Returns None if instrument is unknown rather than inventing a fake key.
    """
    if not symbol:
        return None
    clean_sym = symbol.strip().upper()
    if clean_sym in INSTRUMENT_MAP:
        return INSTRUMENT_MAP[clean_sym]["instrument_key"]
    # If standard .NS alias is passed or omitted, check normalized alias
    if not clean_sym.endswith(".NS"):
        ns_sym = f"{clean_sym}.NS"
        if ns_sym in INSTRUMENT_MAP:
            return INSTRUMENT_MAP[ns_sym]["instrument_key"]
    else:
        base_sym = clean_sym.replace(".NS", "")
        if base_sym in INSTRUMENT_MAP:
            return INSTRUMENT_MAP[base_sym]["instrument_key"]

    # If raw instrument key format is already passed directly (e.g. NSE_EQ|INE...)
    if "|" in symbol and (symbol.startswith("NSE_") or symbol.startswith("BSE_")):
        return symbol

    # Unknown instrument
    return None

def get_instrument_metadata(symbol: str) -> Optional[Dict[str, Any]]:
    """Retrieve full instrument metadata dictionary if known."""
    clean_sym = symbol.strip().upper()
    if clean_sym in INSTRUMENT_MAP:
        return INSTRUMENT_MAP[clean_sym]
    if not clean_sym.endswith(".NS") and f"{clean_sym}.NS" in INSTRUMENT_MAP:
        return INSTRUMENT_MAP[f"{clean_sym}.NS"]
    if clean_sym.endswith(".NS") and clean_sym[:-3] in INSTRUMENT_MAP:
        return INSTRUMENT_MAP[clean_sym[:-3]]
    return None

def get_symbol_from_key(instrument_key: str) -> str:
    """
    Deterministically reverse map instrument_key to canonical primary UI symbol (.NS preferred for equities).
    """
    if not instrument_key:
        return ""
    # Look for .NS primary alias first
    for sym, meta in INSTRUMENT_MAP.items():
        if meta["instrument_key"] == instrument_key and sym.endswith(".NS"):
            return sym
    # Look for any matching alias
    for sym, meta in INSTRUMENT_MAP.items():
        if meta["instrument_key"] == instrument_key:
            return sym
    return instrument_key
