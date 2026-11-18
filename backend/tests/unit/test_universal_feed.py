"""
Universal Feed Unit Test Suite
==============================
Co-located alias forwarding for Universal Market Data & Feed tests.
Ensures pytest invocations targeting `test_universal_feed.py` execute cleanly.
"""

import os
import sys

# Ensure repository root is in sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.tests.unit.test_universal_market_data import (  # noqa: F401
    sample_gold_contract,
    sample_crude_contract,
    sample_upstox_gold_quote_payload,
    TestUniversalQuoteModel,
    TestUniversalMarketDataFeed,
    TestCandleAggregatorDaily,
    TestIntradayResampling,
    TestUpstoxClientMCXHardening,
    TestMarketDataServiceZeroMockEnforcement,
)
