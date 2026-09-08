"""
Signal Intelligence Engine — Historical Signal Outcome Engine
==============================================================
Post-trade forward market evaluation tracking actual execution, excursion,
costs, slippage, and realized R for generated signals.

Evaluates signals against subsequent authentic market data with strict
financial invariants:
- MAE (Maximum Adverse Excursion) in INR points, %, and R
- MFE (Maximum Favorable Excursion) in INR points, %, and R
- Target 1, 2, 3 hit sequence tracking
- Stop loss hit tracking (with intraday high/low excursion checks)
- Transaction cost deduction (Brokerage, STT, Exchange, SEBI, GST, Stamp Duty, Slippage)
- Gross PnL vs Net PnL reconciliation
- Holding time in candles and seconds
- Directional support: LONG, SHORT
- Asset class support: EQUITY, FUTURES, OPTIONS
"""
import logging
import time
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field

from backend.app.signal_engine.transaction_cost import (
    TransactionCostCalculator,
    AssetType,
    CostBreakdown,
)

logger = logging.getLogger(__name__)


class SignalOutcome(BaseModel):
    """Authoritative outcome record for an evaluated signal."""
    signal_id: str
    symbol: str
    asset_class: str = "EQUITY"
    direction: str = "LONG"
    status: str = "EXPIRED"  # TARGET_1, TARGET_2, TARGET_3, STOPPED, EXPIRED, UNFILLED
    is_win: bool = False
    entry_price: float
    exit_price: float
    stop_loss_price: float
    target_1_price: float
    target_2_price: Optional[float] = None
    target_3_price: Optional[float] = None

    # Excursion metrics
    mae: float = 0.0          # INR points
    mfe: float = 0.0          # INR points
    mae_pct: float = 0.0      # % of entry
    mfe_pct: float = 0.0      # % of entry
    mae_r: float = 0.0        # Multiples of R
    mfe_r: float = 0.0        # Multiples of R
    realized_r: float = 0.0   # Realized R
    theoretical_r: float = 0.0

    # Financial breakdown
    quantity: int = 1
    gross_pnl: float = 0.0
    brokerage: float = 0.0
    stt: float = 0.0
    exchange_charges: float = 0.0
    sebi_charges: float = 0.0
    gst: float = 0.0
    stamp_duty: float = 0.0
    slippage: float = 0.0
    total_costs: float = 0.0
    net_pnl: float = 0.0

    # Execution stats
    holding_candles: int = 0
    holding_time_seconds: float = 0.0
    entry_timestamp: float = 0.0
    exit_timestamp: float = 0.0
    exit_reason: str = ""

    model_config = ConfigDict(use_enum_values=True)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class OutcomeEngine:
    """
    Evaluates forward candles against a signal's entry, stop, and targets.
    """

    @staticmethod
    def evaluate(
        signal: Any,
        forward_candles: List[Dict[str, Any]],
        slippage_pct: float = 0.0005,  # 5 bps slippage by default
        max_entry_wait_candles: int = 5,
        session: Optional[Any] = None,
    ) -> SignalOutcome:
        """
        Evaluate a signal against subsequent forward candles.

        Args:
            signal: SignalDecision or dict containing signal parameters
            forward_candles: Chronological list of candles occurring AFTER signal generation
            slippage_pct: Slippage assumption as fraction of price
            max_entry_wait_candles: Max candles to wait for entry fill before expiring
            session: Optional AsyncSession for database persistence

        Returns:
            SignalOutcome record
        """
        # Unpack signal attributes safely
        sig_id = getattr(signal, "signal_id", None) or (signal.get("signal_id") if isinstance(signal, dict) else "unknown")
        symbol = getattr(signal, "symbol", None) or (signal.get("symbol") if isinstance(signal, dict) else "UNKNOWN")

        direction_raw = getattr(signal, "direction", "LONG")
        direction = direction_raw.value if hasattr(direction_raw, "value") else str(direction_raw).upper()

        asset_class_raw = getattr(signal, "asset_class", "EQUITY")
        asset_class = asset_class_raw.value if hasattr(asset_class_raw, "value") else str(asset_class_raw).upper()

        entry = getattr(signal, "entry", None) or (signal.get("entry") if isinstance(signal, dict) else None)
        if entry is None or entry <= 0:
            entry = float(forward_candles[0].get("close", 100.0)) if forward_candles else 100.0

        # Stop loss
        stop_loss_price = 0.0
        stop_loss_obj = getattr(signal, "stop_loss", None) or (signal.get("stop_loss") if isinstance(signal, dict) else None)
        if hasattr(stop_loss_obj, "price"):
            stop_loss_price = float(stop_loss_obj.price)
        elif isinstance(stop_loss_obj, dict):
            stop_loss_price = float(stop_loss_obj.get("price", 0.0))
        elif isinstance(stop_loss_obj, (int, float)):
            stop_loss_price = float(stop_loss_obj)

        if stop_loss_price <= 0:
            stop_loss_price = entry * (0.98 if direction == "LONG" else 1.02)

        # Targets
        targets_obj = getattr(signal, "targets", None) or (signal.get("targets") if isinstance(signal, dict) else [])
        t1, t2, t3 = 0.0, 0.0, 0.0
        if targets_obj and len(targets_obj) > 0:
            first = targets_obj[0]
            t1 = float(getattr(first, "price", 0.0) if hasattr(first, "price") else (first.get("price", 0.0) if isinstance(first, dict) else first))
            if len(targets_obj) > 1:
                sec = targets_obj[1]
                t2 = float(getattr(sec, "price", 0.0) if hasattr(sec, "price") else (sec.get("price", 0.0) if isinstance(sec, dict) else sec))
            if len(targets_obj) > 2:
                third = targets_obj[2]
                t3 = float(getattr(third, "price", 0.0) if hasattr(third, "price") else (third.get("price", 0.0) if isinstance(third, dict) else third))

        if t1 <= 0:
            t1 = entry * (1.03 if direction == "LONG" else 0.97)

        # Quantity
        quantity = 100
        pos_size = getattr(signal, "position_size", None) or (signal.get("position_size") if isinstance(signal, dict) else None)
        if hasattr(pos_size, "quantity"):
            quantity = int(pos_size.quantity)
        elif isinstance(pos_size, dict):
            quantity = int(pos_size.get("quantity", 100))

        if quantity <= 0:
            quantity = 1

        # Initial risk R distance
        r_distance = abs(entry - stop_loss_price)
        if r_distance <= 0:
            r_distance = entry * 0.01

        theoretical_r = abs(t1 - entry) / r_distance

        # Handle empty forward candles
        if not forward_candles:
            return SignalOutcome(
                signal_id=sig_id,
                symbol=symbol,
                asset_class=asset_class,
                direction=direction,
                status="EXPIRED",
                is_win=False,
                entry_price=entry,
                exit_price=entry,
                stop_loss_price=stop_loss_price,
                target_1_price=t1,
                target_2_price=t2 if t2 > 0 else None,
                target_3_price=t3 if t3 > 0 else None,
                theoretical_r=theoretical_r,
                quantity=quantity,
                exit_reason="No forward market data available",
            )

        # Step 1: Wait for entry fill
        filled_index = -1
        fill_price = entry

        for idx, candle in enumerate(forward_candles[:max_entry_wait_candles]):
            c_high = float(candle.get("high", candle.get("close", entry)))
            c_low = float(candle.get("low", candle.get("close", entry)))

            # Check if price overlaps entry
            if c_low <= entry <= c_high:
                filled_index = idx
                fill_price = entry
                break

        if filled_index == -1:
            # Unfilled
            return SignalOutcome(
                signal_id=sig_id,
                symbol=symbol,
                asset_class=asset_class,
                direction=direction,
                status="UNFILLED",
                is_win=False,
                entry_price=entry,
                exit_price=entry,
                stop_loss_price=stop_loss_price,
                target_1_price=t1,
                target_2_price=t2 if t2 > 0 else None,
                target_3_price=t3 if t3 > 0 else None,
                theoretical_r=theoretical_r,
                quantity=quantity,
                exit_reason=f"Price did not trade through {entry:.2f} within {max_entry_wait_candles} candles",
            )

        # Step 2: Track forward excursion from fill candle onward
        entry_candle = forward_candles[filled_index]
        entry_ts = float(entry_candle.get("timestamp", time.time()))

        mae_pts = 0.0
        mfe_pts = 0.0
        terminal_status = "EXPIRED"
        exit_price = float(forward_candles[-1].get("close", fill_price))
        exit_ts = float(forward_candles[-1].get("timestamp", entry_ts + 3600))
        exit_reason = "Forward observation window completed"
        holding_candles = len(forward_candles) - filled_index

        for idx in range(filled_index, len(forward_candles)):
            c = forward_candles[idx]
            c_high = float(c.get("high", c.get("close", fill_price)))
            c_low = float(c.get("low", c.get("close", fill_price)))
            c_ts = float(c.get("timestamp", entry_ts + (idx - filled_index) * 900))

            if direction == "LONG":
                # Excursions
                current_mfe = max(0.0, c_high - fill_price)
                current_mae = max(0.0, fill_price - c_low)
                mfe_pts = max(mfe_pts, current_mfe)
                mae_pts = max(mae_pts, current_mae)

                # Check Stop Loss First (Conservative)
                if c_low <= stop_loss_price:
                    terminal_status = "STOPPED"
                    exit_price = stop_loss_price * (1.0 - slippage_pct)
                    exit_ts = c_ts
                    exit_reason = f"Stop Loss breached at {stop_loss_price:.2f}"
                    holding_candles = idx - filled_index + 1
                    break

                # Check Targets
                if t3 > 0 and c_high >= t3:
                    terminal_status = "TARGET_3"
                    exit_price = t3 * (1.0 - slippage_pct)
                    exit_ts = c_ts
                    exit_reason = f"Target 3 reached at {t3:.2f}"
                    holding_candles = idx - filled_index + 1
                    break
                elif t2 > 0 and c_high >= t2:
                    terminal_status = "TARGET_2"
                    exit_price = t2 * (1.0 - slippage_pct)
                    exit_ts = c_ts
                    exit_reason = f"Target 2 reached at {t2:.2f}"
                    holding_candles = idx - filled_index + 1
                    break
                elif t1 > 0 and c_high >= t1:
                    terminal_status = "TARGET_1"
                    exit_price = t1 * (1.0 - slippage_pct)
                    exit_ts = c_ts
                    exit_reason = f"Target 1 reached at {t1:.2f}"
                    holding_candles = idx - filled_index + 1
                    # Can continue to target 2/3 if not breaking, but if evaluating single-target:
                    break

            else:  # SHORT
                # Excursions
                current_mfe = max(0.0, fill_price - c_low)
                current_mae = max(0.0, c_high - fill_price)
                mfe_pts = max(mfe_pts, current_mfe)
                mae_pts = max(mae_pts, current_mae)

                # Check Stop Loss First
                if c_high >= stop_loss_price:
                    terminal_status = "STOPPED"
                    exit_price = stop_loss_price * (1.0 + slippage_pct)
                    exit_ts = c_ts
                    exit_reason = f"Stop Loss breached at {stop_loss_price:.2f}"
                    holding_candles = idx - filled_index + 1
                    break

                # Check Targets
                if t3 > 0 and c_low <= t3:
                    terminal_status = "TARGET_3"
                    exit_price = t3 * (1.0 + slippage_pct)
                    exit_ts = c_ts
                    exit_reason = f"Target 3 reached at {t3:.2f}"
                    holding_candles = idx - filled_index + 1
                    break
                elif t2 > 0 and c_low <= t2:
                    terminal_status = "TARGET_2"
                    exit_price = t2 * (1.0 + slippage_pct)
                    exit_ts = c_ts
                    exit_reason = f"Target 2 reached at {t2:.2f}"
                    holding_candles = idx - filled_index + 1
                    break
                elif t1 > 0 and c_low <= t1:
                    terminal_status = "TARGET_1"
                    exit_price = t1 * (1.0 + slippage_pct)
                    exit_ts = c_ts
                    exit_reason = f"Target 1 reached at {t1:.2f}"
                    holding_candles = idx - filled_index + 1
                    break

        # Step 3: Compute PnL and R metrics
        mae_pct = (mae_pts / fill_price) * 100.0 if fill_price > 0 else 0.0
        mfe_pct = (mfe_pts / fill_price) * 100.0 if fill_price > 0 else 0.0
        mae_r = mae_pts / r_distance if r_distance > 0 else 0.0
        mfe_r = mfe_pts / r_distance if r_distance > 0 else 0.0

        if direction == "LONG":
            gross_pnl = (exit_price - fill_price) * quantity
            realized_r = (exit_price - fill_price) / r_distance
        else:
            gross_pnl = (fill_price - exit_price) * quantity
            realized_r = (fill_price - exit_price) / r_distance

        is_win = realized_r > 0.0 and terminal_status in ("TARGET_1", "TARGET_2", "TARGET_3")

        # Step 4: Calculate transaction costs
        asset_enum = AssetType.EQUITY_INTRADAY
        if asset_class == "FUTURES":
            asset_enum = AssetType.FUTURES
        elif asset_class == "OPTIONS":
            asset_enum = AssetType.OPTIONS

        cost_breakdown = TransactionCostCalculator.calculate(
            asset_type=asset_enum,
            buy_price=fill_price if direction == "LONG" else exit_price,
            sell_price=exit_price if direction == "LONG" else fill_price,
            quantity=quantity,
            slippage_pct=slippage_pct,
        )

        net_pnl = gross_pnl - cost_breakdown.total_costs
        holding_time_seconds = max(0.0, exit_ts - entry_ts)

        outcome = SignalOutcome(
            signal_id=sig_id,
            symbol=symbol,
            asset_class=asset_class,
            direction=direction,
            status=terminal_status,
            is_win=is_win,
            entry_price=round(fill_price, 2),
            exit_price=round(exit_price, 2),
            stop_loss_price=round(stop_loss_price, 2),
            target_1_price=round(t1, 2),
            target_2_price=round(t2, 2) if t2 > 0 else None,
            target_3_price=round(t3, 2) if t3 > 0 else None,
            mae=round(mae_pts, 2),
            mfe=round(mfe_pts, 2),
            mae_pct=round(mae_pct, 2),
            mfe_pct=round(mfe_pct, 2),
            mae_r=round(mae_r, 2),
            mfe_r=round(mfe_r, 2),
            realized_r=round(realized_r, 2),
            theoretical_r=round(theoretical_r, 2),
            quantity=quantity,
            gross_pnl=round(gross_pnl, 2),
            brokerage=round(cost_breakdown.brokerage, 2),
            stt=round(cost_breakdown.stt, 2),
            exchange_charges=round(cost_breakdown.exchange_charges, 2),
            sebi_charges=round(cost_breakdown.sebi_charges, 2),
            gst=round(cost_breakdown.gst, 2),
            stamp_duty=round(cost_breakdown.stamp_duty, 2),
            slippage=round(cost_breakdown.slippage, 2),
            total_costs=round(cost_breakdown.total_costs, 2),
            net_pnl=round(net_pnl, 2),
            holding_candles=holding_candles,
            holding_time_seconds=holding_time_seconds,
            entry_timestamp=entry_ts,
            exit_timestamp=exit_ts,
            exit_reason=exit_reason,
        )

        return outcome


outcome_engine = OutcomeEngine()
