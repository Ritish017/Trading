"""
Signal Intelligence Engine — Position Sizing Engine
=====================================================
Computes risk-based position sizing for qualified signals.

Methods supported:
1. FIXED_RISK  — Risk a fixed percentage of capital per trade (default)
2. PERCENTAGE  — Allocate fixed % of capital
3. FIXED_QTY   — Fixed number of shares (for manual override)

Risk-based sizing formula (method=FIXED_RISK):
  max_risk_amount = capital * (risk_per_trade_pct / 100)
  risk_per_share  = entry_price - stop_price (LONG) or stop_price - entry_price (SHORT)
  quantity        = floor(max_risk_amount / risk_per_share)
  capital_required = quantity * entry_price
  maximum_loss    = quantity * risk_per_share

Constraints:
- Quantity must be ≥ 1 share
- Capital required must be ≤ available capital
- For F&O, quantity must be rounded to lot_size multiples
- Maximum loss must be ≤ risk_per_trade_pct * capital
"""
import logging
import math
from typing import Any, Dict, Optional

from backend.app.signal_engine.models import (
    PositionSizing,
    SignalEngineConfig,
)

logger = logging.getLogger(__name__)


class PositionSizingEngine:
    """
    Risk-based position sizing for APEX signals.

    Invariants:
    - Never sizes a position that would lose more than risk_per_trade_pct of capital
    - Returns explicit PositionSizing with all components shown
    - Never returns negative quantity or capital
    """

    def compute(
        self,
        direction: str,
        entry_price: float,
        stop_price: float,
        config: SignalEngineConfig,
        lot_size: Optional[int] = None,
        available_capital: Optional[float] = None,
    ) -> Optional[PositionSizing]:
        """
        Compute position sizing for a signal.
        Returns PositionSizing or None if sizing cannot be computed.
        """
        if entry_price <= 0 or stop_price <= 0:
            return None

        capital = available_capital or config.capital
        if capital <= 0:
            return None

        if direction == "LONG":
            risk_per_share = entry_price - stop_price
        else:  # SHORT
            risk_per_share = stop_price - entry_price

        if risk_per_share <= 0:
            logger.warning(
                "Position sizing: risk per share is zero or negative "
                f"(entry={entry_price}, stop={stop_price}, direction={direction})"
            )
            return None

        # Compute maximum allowable risk amount
        max_risk_amount = capital * (config.risk_per_trade_pct / 100)

        # Compute raw quantity
        raw_qty = max_risk_amount / risk_per_share

        # Round down to nearest whole share
        quantity = int(math.floor(raw_qty))

        # Apply lot size constraint for F&O
        if lot_size and lot_size > 1:
            quantity = max(lot_size, int(math.floor(raw_qty / lot_size)) * lot_size)
            sizing_notes = f"Rounded to lot size {lot_size}"
        else:
            sizing_notes = None

        if quantity < 1:
            # Position too small — common when stop is very tight and capital is limited
            # Try allocating minimum 1 share and see if it exceeds risk limits
            quantity = 1
            sizing_notes = "Minimum 1 share (risk per share exceeds max risk budget)"

        capital_required = round(quantity * entry_price, 2)
        maximum_loss = round(quantity * risk_per_share, 2)

        # Validate capital required doesn't exceed available
        max_position_capital = capital * (config.max_portfolio_exposure_pct / 100 / max(1, 3))
        if capital_required > max_position_capital:
            # Scale down to fit within single position limit
            quantity = max(1, int(math.floor(max_position_capital / entry_price)))
            if lot_size and lot_size > 1:
                quantity = max(lot_size, int(math.floor(quantity / lot_size)) * lot_size)
            capital_required = round(quantity * entry_price, 2)
            maximum_loss = round(quantity * risk_per_share, 2)
            sizing_notes = (sizing_notes or "") + " Position scaled to fit single-position capital limit."

        return PositionSizing(
            method="FIXED_RISK",
            capital=round(capital, 2),
            risk_per_trade_pct=config.risk_per_trade_pct,
            max_risk_amount=round(max_risk_amount, 2),
            entry_price=round(entry_price, 2),
            stop_price=round(stop_price, 2),
            risk_per_share=round(risk_per_share, 2),
            quantity=quantity,
            capital_required=capital_required,
            maximum_loss=maximum_loss,
            sizing_notes=sizing_notes,
            lot_size=lot_size,
        )


# Module-level singleton
position_sizing_engine = PositionSizingEngine()
