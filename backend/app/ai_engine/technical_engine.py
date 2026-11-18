"""
APEX Commodity Historical & Technical Engine (Re-export Alias)
============================================================
Provides backward-compatible re-exports from backend.app.market_data.technical_engine.
"""

from backend.app.market_data.technical_engine import (
    RealizedPriceRange,
    CommodityTechnicals,
    TechnicalEngine,
    technical_engine,
    compute_realized_range,
    compute_technical_indicators,
)

__all__ = [
    "RealizedPriceRange",
    "CommodityTechnicals",
    "TechnicalEngine",
    "technical_engine",
    "compute_realized_range",
    "compute_technical_indicators",
]
