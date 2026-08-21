from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class CorporateActionType(str, Enum):
    BONUS = "BONUS"
    SPLIT = "SPLIT"
    REVERSE_SPLIT = "REVERSE_SPLIT"
    RIGHTS = "RIGHTS"
    MERGER = "MERGER"
    DEMERGER = "DEMERGER"
    SYMBOL_CHANGE = "SYMBOL_CHANGE"

class PriceAdjustmentMode(str, Enum):
    RAW_EXCHANGE_PRICE = "RAW_EXCHANGE_PRICE"
    CORPORATE_ACTION_ADJUSTED_PRICE = "CORPORATE_ACTION_ADJUSTED_PRICE"

class AnomalyClassification(str, Enum):
    NORMAL_MARKET_MOVE = "NORMAL_MARKET_MOVE"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    SPLIT = "SPLIT"
    BONUS = "BONUS"
    DATA_ERROR = "DATA_ERROR"
    STALE_CACHE = "STALE_CACHE"
    WRONG_INSTRUMENT = "WRONG_INSTRUMENT"
    PRICE_INTEGRITY_ERROR = "PRICE_INTEGRITY_ERROR"
    UNKNOWN = "UNKNOWN"

class CorporateActionEvent(BaseModel):
    symbol: str
    exchange: str = "NSE"
    action_type: CorporateActionType
    announcement_date: Optional[str] = None
    ex_date: str # ISO Date YYYY-MM-DD
    record_date: Optional[str] = None
    ratio_before: float = Field(..., description="Ratio denominator (e.g. 1 for 1:1 bonus or 10 for 10:1 split)")
    ratio_after: float = Field(..., description="Ratio numerator (e.g. 1 for 1:1 bonus or 1 for 10:1 split)")
    adjustment_factor: float = Field(..., description="Price divisor for pre-ex historical prices")
    source: str = "NSE_OFFICIAL"
    source_timestamp: float = 0.0
    effective_timestamp: float = Field(..., description="Epoch seconds for ex-date midnight/session start")
    status: str = "COMPLETED"
