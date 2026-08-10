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
}

def get_instrument_key(symbol: str) -> str:
    """Resolve symbol string to Upstox instrument key."""
    clean_sym = symbol.strip().upper()
    if clean_sym in INSTRUMENT_MAP:
        return INSTRUMENT_MAP[clean_sym]["instrument_key"]
    # If instrument key format is already passed directly (e.g. NSE_EQ|...)
    if "|" in symbol:
        return symbol
    # Default fallback construct
    if clean_sym.endswith(".NS"):
        return f"NSE_EQ|{clean_sym.replace('.NS', '')}"
    return f"NSE_EQ|{clean_sym}"

def get_instrument_metadata(symbol: str) -> Dict[str, Any]:
    """Retrieve full instrument metadata dictionary."""
    clean_sym = symbol.strip().upper()
    if clean_sym in INSTRUMENT_MAP:
        return INSTRUMENT_MAP[clean_sym]
    key = get_instrument_key(symbol)
    return {
        "instrument_key": key,
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_type": "EQUITY",
        "display_name": symbol
    }

def get_symbol_from_key(instrument_key: str) -> str:
    """Reverse map instrument_key to primary UI symbol."""
    for sym, meta in INSTRUMENT_MAP.items():
        if meta["instrument_key"] == instrument_key:
            return sym
    return instrument_key
