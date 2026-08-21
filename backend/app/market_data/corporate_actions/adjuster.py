import copy
from typing import Dict, Any, List, Optional
from backend.app.market_data.corporate_actions.models import (
    PriceAdjustmentMode,
)
from backend.app.market_data.corporate_actions.registry import (
    CorporateActionRegistry,
    corporate_action_registry,
)

class CorporateActionAdjuster:
    """
    Generic Corporate Action Normalization and Price Adjustment Service.
    Enforces strict mathematical separation between RAW_EXCHANGE_PRICE and CORPORATE_ACTION_ADJUSTED_PRICE.
    """

    def __init__(self, registry: Optional[CorporateActionRegistry] = None):
        self.registry = registry or corporate_action_registry

    def adjust_candle(
        self,
        candle: Dict[str, Any],
        symbol: str,
        mode: PriceAdjustmentMode = PriceAdjustmentMode.CORPORATE_ACTION_ADJUSTED_PRICE,
        target_timestamp: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Adjusts a single OHLCV candle for corporate action effects.
        
        Rules:
        - RAW_EXCHANGE_PRICE: Preserves raw historical traded exchange prices.
        - CORPORATE_ACTION_ADJUSTED_PRICE: If candle timestamp is before an ex-date, divides OHLC & VWAP by factor,
          and multiplies volume by factor.
        - Post-action candles (timestamp >= ex_date) are NEVER adjusted.
        """
        adj = copy.deepcopy(candle)
        raw_ts = float(adj.get("timestamp") or adj.get("time") or 0.0)

        if mode == PriceAdjustmentMode.RAW_EXCHANGE_PRICE:
            adj["price_adjustment_mode"] = "RAW"
            adj["adjustment_factor_applied"] = 1.0
            return adj

        factor = self.registry.get_cumulative_factor(symbol, raw_ts, target_timestamp)
        adj["price_adjustment_mode"] = "ADJUSTED"
        adj["adjustment_factor_applied"] = factor

        if factor != 1.0 and factor > 0:
            for field in ["open", "high", "low", "close"]:
                if field in adj and adj[field] is not None:
                    adj[field] = round(float(adj[field]) / factor, 4)

            # Volume adjustment: Historical share quantity is multiplied by factor (for bonus/split)
            if "volume" in adj and adj["volume"] is not None:
                adj["volume"] = int(round(float(adj["volume"]) * factor))

            if "volumeLakhs" in adj and adj["volumeLakhs"] is not None:
                adj["volumeLakhs"] = round(float(adj["volumeLakhs"]) * factor, 4)

            if "vwap" in adj and adj["vwap"] is not None:
                adj["vwap"] = round(float(adj["vwap"]) / factor, 4)

        return adj

    def adjust_candle_series(
        self,
        candles: List[Dict[str, Any]],
        symbol: str,
        mode: PriceAdjustmentMode = PriceAdjustmentMode.CORPORATE_ACTION_ADJUSTED_PRICE,
        target_timestamp: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Adjust an entire historical series of candles to a single canonical price domain."""
        return [self.adjust_candle(c, symbol, mode, target_timestamp) for c in candles]

    def validate_live_quote(self, quote: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        """
        CRITICAL LIVE PRICE RULE:
        Current live market price from the exchange/provider is the current post-corporate-action market price.
        It MUST NEVER be divided or multiplied by historical corporate-action factors.
        """
        validated = copy.deepcopy(quote)
        validated["price_domain"] = "CURRENT_EXCHANGE_PRICE"
        validated["adjustment"] = "N/A — live quote"
        validated["price_adjustment_mode"] = "RAW_EXCHANGE_PRICE"
        return validated

# Global instance
corporate_action_adjuster = CorporateActionAdjuster()
