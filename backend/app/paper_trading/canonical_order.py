"""
Canonical Paper Order & Execution Model
=========================================
Implements the canonical order state machine, statutory friction model,
and verified lifecycle transitions required for production paper trading.
"""

from enum import Enum
import time
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class OrderState(str, Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


VALID_ORDER_TRANSITIONS: Dict[OrderState, set[OrderState]] = {
    OrderState.CREATED: {OrderState.VALIDATED, OrderState.REJECTED},
    OrderState.VALIDATED: {OrderState.ACCEPTED, OrderState.REJECTED},
    OrderState.ACCEPTED: {OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED},
    OrderState.PARTIALLY_FILLED: {OrderState.FILLED, OrderState.CANCELLED},
    OrderState.FILLED: set(),
    OrderState.CANCELLED: set(),
    OrderState.REJECTED: set(),
}


def validate_order_transition(current_state: OrderState, new_state: OrderState) -> None:
    """
    Validates state machine transitions for canonical orders.
    Raises ValueError on illegal transitions.
    """
    if current_state == new_state:
        return
    allowed = VALID_ORDER_TRANSITIONS.get(current_state, set())
    if new_state not in allowed:
        raise ValueError(
            f"Illegal order state transition: cannot transition from {current_state.value} to {new_state.value}."
        )


class CanonicalOrder(BaseModel):
    order_id: str
    account_id: str = "primary_personal_account"
    symbol: str
    exchange: str = "NSE"
    side: str  # BUY or SELL
    quantity: int
    order_type: str = "MARKET"  # MARKET, LIMIT, SL
    requested_price: float
    status: OrderState = OrderState.CREATED
    created_at: float = Field(default_factory=time.time)
    filled_at: Optional[float] = None
    rejection_reason: Optional[str] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    product_type: str = "CNC"  # CNC or MIS
    source: str = "MANUAL"

    def transition_to(self, new_state: OrderState, reason: Optional[str] = None) -> None:
        validate_order_transition(self.status, new_state)
        self.status = new_state
        if reason:
            self.rejection_reason = reason
        if new_state == OrderState.FILLED:
            self.filled_at = time.time()


class CanonicalFill(BaseModel):
    fill_id: str
    order_id: str
    account_id: str = "primary_personal_account"
    symbol: str
    side: str
    quantity: int
    price: float
    timestamp: float = Field(default_factory=time.time)
    brokerage: float = 20.0
    stt: float = 0.0
    exchange_charges: float = 0.0
    sebi_charges: float = 0.0
    gst: float = 0.0
    stamp_duty: float = 0.0
    slippage: float = 0.0
    fees: float = 0.0  # total non-slippage fees

    @property
    def total_friction(self) -> float:
        return self.fees + self.slippage
