"""
APEX MCX Contract & Resolution Models
====================================
Defines authoritative data models for MCX Commodity Futures contracts,
contract terms (Near-Month, Next-Month, Far-Month), rollover mechanics,
and dynamic commodity resolution structures.
"""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ContractTerm(str, Enum):
    """MCX Futures Contract Expiry Term Classification."""
    NEAR_MONTH = "NEAR_MONTH"
    NEXT_MONTH = "NEXT_MONTH"
    FAR_MONTH = "FAR_MONTH"


class MCXContract(BaseModel):
    """
    Standardized representation of an active MCX commodity futures contract.
    Preserves exact exchange specifications, multipliers, units, and rollover status.
    """
    instrument_key: str = Field(..., description="Upstox unique key, e.g. 'MCX_FO|495213'")
    exchange_token: str = Field(..., description="Exchange numeric token, e.g. '495213'")
    trading_symbol: str = Field(..., description="Official trading symbol, e.g. 'GOLD FUT 04 DEC 26'")
    commodity_symbol: str = Field(..., description="Base commodity symbol, e.g. 'GOLD'")
    term: ContractTerm = Field(..., description="Contract term: NEAR_MONTH, NEXT_MONTH, or FAR_MONTH")
    expiry_timestamp: int = Field(..., description="Unix epoch timestamp in milliseconds")
    expiry_date: str = Field(..., description="Formatted expiry date 'YYYY-MM-DD'")
    last_trading_date: str = Field(..., description="Last trading date string 'YYYY-MM-DD HH:MM:SS'")
    days_to_expiry: int = Field(..., description="Calendar days remaining until contract expiry")
    is_in_rollover_window: bool = Field(..., description="True if days_to_expiry <= 5 (tender/rollover period)")
    lot_size: int = Field(..., description="Minimum tradable lot size")
    qty_multiplier: float = Field(..., description="Physical quantity multiplier per contract")
    price_quote_unit: str = Field(..., description="Quotation unit, e.g. 'GRMS', 'KGS', 'BBL', 'mmBtu'")
    tick_size: float = Field(..., description="Tick size in paise (e.g. 100.0 paise = ₹1.00)")
    tick_size_rupees: float = Field(..., description="Tick size in rupees (tick_size / 100.0)")

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary with enum strings."""
        return self.model_dump()


class CommodityResolution(BaseModel):
    """
    Dynamic resolution result for a commodity, linking to its active
    Near-Month, Next-Month, and Far-Month contracts.
    """
    commodity_code: str = Field(..., description="Canonical commodity code, e.g. 'GOLD', 'CRUDEOIL'")
    display_name: str = Field(..., description="Human-readable commodity display name")
    unit: str = Field(..., description="Quotation price unit, e.g. '₹/10g', '₹/kg', '₹/bbl', '₹/mmBtu'")
    near_contract: MCXContract = Field(..., description="Active Near-Month (front) contract")
    next_contract: Optional[MCXContract] = Field(None, description="Active Next-Month contract if available")
    far_contract: Optional[MCXContract] = Field(None, description="Active Far-Month contract if available")
    available_contracts_count: int = Field(..., description="Total unexpired futures contracts discovered")
    resolved_at: float = Field(..., description="Unix timestamp (seconds) when resolution was executed")

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return self.model_dump()
