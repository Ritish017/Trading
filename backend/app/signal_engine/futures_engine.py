"""
APEX Futures Decision Engine
=============================
Evaluates equity underlying signals against real futures market structure
(basis, open interest dynamics, rollover cycle, liquidity, margin requirement)
to produce evidence-backed futures decisions: BUY FUTURE, SELL FUTURE, or NO TRADE.

Truth-Layer Invariants:
- Never converts an equity signal blindly into a futures trade.
- If futures volume or OI is insufficient, fails closed to NO_TRADE.
- Explicitly models basis risk, expiry risk, and rollover penalty.
- Sizing strictly adheres to lot size and available margin capital.
"""

import math
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from backend.app.signal_engine.transaction_cost import (
    TransactionCostCalculator, AssetClass, OrderSide
)


class FuturesAction(str, Enum):
    BUY_FUTURE = "BUY_FUTURE"
    SELL_FUTURE = "SELL_FUTURE"
    NO_TRADE = "NO_TRADE"


class OpenInterestPattern(str, Enum):
    LONG_BUILDUP = "LONG_BUILDUP"         # Price Up, OI Up (Bullish)
    SHORT_BUILDUP = "SHORT_BUILDUP"       # Price Down, OI Up (Bearish)
    SHORT_COVERING = "SHORT_COVERING"     # Price Up, OI Down (Weak Bullish)
    LONG_UNWINDING = "LONG_UNWINDING"     # Price Down, OI Down (Weak Bearish)
    NEUTRAL = "NEUTRAL"


@dataclass
class FuturesDecision:
    action: FuturesAction
    symbol: str
    underlying_direction: str
    spot_price: float
    futures_price: float
    basis: float
    basis_pct: float
    days_to_expiry: int
    oi: int
    oi_change_pct: float
    oi_pattern: OpenInterestPattern
    volume: int
    lot_size: int
    recommended_lots: int
    total_quantity: int
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    risk_reward_ratio: float
    margin_required: float
    estimated_costs: float
    is_valid: bool
    rejection_reason: Optional[str] = None
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "symbol": self.symbol,
            "underlying_direction": self.underlying_direction,
            "spot_price": round(self.spot_price, 2),
            "futures_price": round(self.futures_price, 2),
            "basis": round(self.basis, 2),
            "basis_pct": round(self.basis_pct, 4),
            "days_to_expiry": self.days_to_expiry,
            "oi": self.oi,
            "oi_change_pct": round(self.oi_change_pct, 2),
            "oi_pattern": self.oi_pattern.value,
            "volume": self.volume,
            "lot_size": self.lot_size,
            "recommended_lots": self.recommended_lots,
            "total_quantity": self.total_quantity,
            "entry_price": round(self.entry_price, 2),
            "stop_loss": round(self.stop_loss, 2),
            "target_1": round(self.target_1, 2),
            "target_2": round(self.target_2, 2),
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "margin_required": round(self.margin_required, 2),
            "estimated_costs": round(self.estimated_costs, 2),
            "is_valid": self.is_valid,
            "rejection_reason": self.rejection_reason,
            "rationale": self.rationale,
        }


class FuturesEngine:
    """
    Evaluates underlying opportunity for futures trade suitability.
    """

    MIN_VOLUME_LOTS = 50
    MIN_OI_LOTS = 200
    MAX_BASIS_DEVIATION_PCT = 3.0  # Excessive basis disconnect
    MIN_DAYS_TO_EXPIRY = 2         # Avoid trading on expiry day or DTE < 2 to prevent physical delivery / pin risk

    @classmethod
    def analyze(
        cls,
        symbol: str,
        underlying_direction: str,  # "LONG" | "SHORT" | "NO_TRADE"
        spot_price: float,
        futures_price: float,
        days_to_expiry: int,
        oi: int,
        volume: int,
        lot_size: int,
        underlying_stop: float,
        underlying_target_1: float,
        underlying_target_2: float,
        oi_change_pct: float = 0.0,
        available_capital: float = 1000000.0,
        margin_per_lot: Optional[float] = None,
        max_capital_allocation_pct: float = 25.0,
    ) -> FuturesDecision:
        """
        Synthesize underlying opportunity and futures microstructure into a FuturesDecision.
        """
        if underlying_direction not in ("LONG", "SHORT"):
            return FuturesDecision(
                action=FuturesAction.NO_TRADE,
                symbol=symbol,
                underlying_direction=underlying_direction,
                spot_price=spot_price,
                futures_price=futures_price,
                basis=0.0,
                basis_pct=0.0,
                days_to_expiry=days_to_expiry,
                oi=oi,
                oi_change_pct=oi_change_pct,
                oi_pattern=OpenInterestPattern.NEUTRAL,
                volume=volume,
                lot_size=lot_size,
                recommended_lots=0,
                total_quantity=0,
                entry_price=futures_price,
                stop_loss=0.0,
                target_1=0.0,
                target_2=0.0,
                risk_reward_ratio=0.0,
                margin_required=0.0,
                estimated_costs=0.0,
                is_valid=False,
                rejection_reason="UNDERLYING_DIRECTION_NOT_TRADEABLE",
                rationale="Underlying signal does not indicate a directional long or short.",
            )

        if spot_price <= 0 or futures_price <= 0:
            return FuturesDecision(
                action=FuturesAction.NO_TRADE,
                symbol=symbol,
                underlying_direction=underlying_direction,
                spot_price=spot_price,
                futures_price=futures_price,
                basis=0.0,
                basis_pct=0.0,
                days_to_expiry=days_to_expiry,
                oi=oi,
                oi_change_pct=oi_change_pct,
                oi_pattern=OpenInterestPattern.NEUTRAL,
                volume=volume,
                lot_size=lot_size,
                recommended_lots=0,
                total_quantity=0,
                entry_price=futures_price,
                stop_loss=0.0,
                target_1=0.0,
                target_2=0.0,
                risk_reward_ratio=0.0,
                margin_required=0.0,
                estimated_costs=0.0,
                is_valid=False,
                rejection_reason="INVALID_PRICE_DATA",
                rationale="Spot or futures price must be strictly positive.",
            )

        # 1. Basis Analysis
        basis = futures_price - spot_price
        basis_pct = (basis / spot_price) * 100.0

        if abs(basis_pct) > cls.MAX_BASIS_DEVIATION_PCT:
            return FuturesDecision(
                action=FuturesAction.NO_TRADE,
                symbol=symbol,
                underlying_direction=underlying_direction,
                spot_price=spot_price,
                futures_price=futures_price,
                basis=basis,
                basis_pct=basis_pct,
                days_to_expiry=days_to_expiry,
                oi=oi,
                oi_change_pct=oi_change_pct,
                oi_pattern=OpenInterestPattern.NEUTRAL,
                volume=volume,
                lot_size=lot_size,
                recommended_lots=0,
                total_quantity=0,
                entry_price=futures_price,
                stop_loss=0.0,
                target_1=0.0,
                target_2=0.0,
                risk_reward_ratio=0.0,
                margin_required=0.0,
                estimated_costs=0.0,
                is_valid=False,
                rejection_reason="EXCESSIVE_BASIS_DISCONNECT",
                rationale=f"Basis deviation ({basis_pct:.2f}%) exceeds safety threshold of ±{cls.MAX_BASIS_DEVIATION_PCT}%.",
            )

        # 2. Expiry / Rollover Gate
        if days_to_expiry < cls.MIN_DAYS_TO_EXPIRY:
            return FuturesDecision(
                action=FuturesAction.NO_TRADE,
                symbol=symbol,
                underlying_direction=underlying_direction,
                spot_price=spot_price,
                futures_price=futures_price,
                basis=basis,
                basis_pct=basis_pct,
                days_to_expiry=days_to_expiry,
                oi=oi,
                oi_change_pct=oi_change_pct,
                oi_pattern=OpenInterestPattern.NEUTRAL,
                volume=volume,
                lot_size=lot_size,
                recommended_lots=0,
                total_quantity=0,
                entry_price=futures_price,
                stop_loss=0.0,
                target_1=0.0,
                target_2=0.0,
                risk_reward_ratio=0.0,
                margin_required=0.0,
                estimated_costs=0.0,
                is_valid=False,
                rejection_reason="EXPIRY_CYCLE_RESTRICTION",
                rationale=f"Days to expiry ({days_to_expiry}) is below minimum {cls.MIN_DAYS_TO_EXPIRY} days (rollover/physical delivery risk).",
            )

        # 3. Liquidity Gate
        volume_lots = volume // max(1, lot_size)
        oi_lots = oi // max(1, lot_size)
        if volume_lots < cls.MIN_VOLUME_LOTS or oi_lots < cls.MIN_OI_LOTS:
            return FuturesDecision(
                action=FuturesAction.NO_TRADE,
                symbol=symbol,
                underlying_direction=underlying_direction,
                spot_price=spot_price,
                futures_price=futures_price,
                basis=basis,
                basis_pct=basis_pct,
                days_to_expiry=days_to_expiry,
                oi=oi,
                oi_change_pct=oi_change_pct,
                oi_pattern=OpenInterestPattern.NEUTRAL,
                volume=volume,
                lot_size=lot_size,
                recommended_lots=0,
                total_quantity=0,
                entry_price=futures_price,
                stop_loss=0.0,
                target_1=0.0,
                target_2=0.0,
                risk_reward_ratio=0.0,
                margin_required=0.0,
                estimated_costs=0.0,
                is_valid=False,
                rejection_reason="LOW_FUTURES_LIQUIDITY",
                rationale=f"Futures liquidity insufficient: Volume={volume_lots} lots (min {cls.MIN_VOLUME_LOTS}), OI={oi_lots} lots (min {cls.MIN_OI_LOTS}).",
            )

        # 4. Open Interest Pattern Classification
        is_price_up = basis > 0 or futures_price >= spot_price
        if is_price_up and oi_change_pct > 2.0:
            oi_pattern = OpenInterestPattern.LONG_BUILDUP
        elif not is_price_up and oi_change_pct > 2.0:
            oi_pattern = OpenInterestPattern.SHORT_BUILDUP
        elif is_price_up and oi_change_pct < -2.0:
            oi_pattern = OpenInterestPattern.SHORT_COVERING
        elif not is_price_up and oi_change_pct < -2.0:
            oi_pattern = OpenInterestPattern.LONG_UNWINDING
        else:
            oi_pattern = OpenInterestPattern.NEUTRAL

        # Check for sharp OI divergence
        if underlying_direction == "LONG" and oi_pattern == OpenInterestPattern.SHORT_BUILDUP:
            return FuturesDecision(
                action=FuturesAction.NO_TRADE,
                symbol=symbol,
                underlying_direction=underlying_direction,
                spot_price=spot_price,
                futures_price=futures_price,
                basis=basis,
                basis_pct=basis_pct,
                days_to_expiry=days_to_expiry,
                oi=oi,
                oi_change_pct=oi_change_pct,
                oi_pattern=oi_pattern,
                volume=volume,
                lot_size=lot_size,
                recommended_lots=0,
                total_quantity=0,
                entry_price=futures_price,
                stop_loss=0.0,
                target_1=0.0,
                target_2=0.0,
                risk_reward_ratio=0.0,
                margin_required=0.0,
                estimated_costs=0.0,
                is_valid=False,
                rejection_reason="FUTURES_OI_DIVERGENCE",
                rationale="Underlying indicates LONG but futures shows aggressive SHORT_BUILDUP.",
            )
        elif underlying_direction == "SHORT" and oi_pattern == OpenInterestPattern.LONG_BUILDUP:
            return FuturesDecision(
                action=FuturesAction.NO_TRADE,
                symbol=symbol,
                underlying_direction=underlying_direction,
                spot_price=spot_price,
                futures_price=futures_price,
                basis=basis,
                basis_pct=basis_pct,
                days_to_expiry=days_to_expiry,
                oi=oi,
                oi_change_pct=oi_change_pct,
                oi_pattern=oi_pattern,
                volume=volume,
                lot_size=lot_size,
                recommended_lots=0,
                total_quantity=0,
                entry_price=futures_price,
                stop_loss=0.0,
                target_1=0.0,
                target_2=0.0,
                risk_reward_ratio=0.0,
                margin_required=0.0,
                estimated_costs=0.0,
                is_valid=False,
                rejection_reason="FUTURES_OI_DIVERGENCE",
                rationale="Underlying indicates SHORT but futures shows aggressive LONG_BUILDUP.",
            )

        # 5. Stop Loss & Target Projection on Futures
        price_diff = futures_price - spot_price
        f_stop = round(underlying_stop + price_diff, 2)
        f_t1 = round(underlying_target_1 + price_diff, 2)
        f_t2 = round(underlying_target_2 + price_diff, 2)

        # Invariant checks
        if underlying_direction == "LONG":
            if f_stop >= futures_price or f_t1 <= futures_price:
                return FuturesDecision(
                    action=FuturesAction.NO_TRADE,
                    symbol=symbol,
                    underlying_direction=underlying_direction,
                    spot_price=spot_price,
                    futures_price=futures_price,
                    basis=basis,
                    basis_pct=basis_pct,
                    days_to_expiry=days_to_expiry,
                    oi=oi,
                    oi_change_pct=oi_change_pct,
                    oi_pattern=oi_pattern,
                    volume=volume,
                    lot_size=lot_size,
                    recommended_lots=0,
                    total_quantity=0,
                    entry_price=futures_price,
                    stop_loss=f_stop,
                    target_1=f_t1,
                    target_2=f_t2,
                    risk_reward_ratio=0.0,
                    margin_required=0.0,
                    estimated_costs=0.0,
                    is_valid=False,
                    rejection_reason="INVALID_FUTURES_GEOMETRY",
                    rationale=f"Long futures stop {f_stop} >= entry {futures_price} or target {f_t1} <= entry.",
                )
            risk_dist = futures_price - f_stop
            reward_dist = f_t1 - futures_price
        else:  # SHORT
            if f_stop <= futures_price or f_t1 >= futures_price:
                return FuturesDecision(
                    action=FuturesAction.NO_TRADE,
                    symbol=symbol,
                    underlying_direction=underlying_direction,
                    spot_price=spot_price,
                    futures_price=futures_price,
                    basis=basis,
                    basis_pct=basis_pct,
                    days_to_expiry=days_to_expiry,
                    oi=oi,
                    oi_change_pct=oi_change_pct,
                    oi_pattern=oi_pattern,
                    volume=volume,
                    lot_size=lot_size,
                    recommended_lots=0,
                    total_quantity=0,
                    entry_price=futures_price,
                    stop_loss=f_stop,
                    target_1=f_t1,
                    target_2=f_t2,
                    risk_reward_ratio=0.0,
                    margin_required=0.0,
                    estimated_costs=0.0,
                    is_valid=False,
                    rejection_reason="INVALID_FUTURES_GEOMETRY",
                    rationale=f"Short futures stop {f_stop} <= entry {futures_price} or target {f_t1} >= entry.",
                )
            risk_dist = f_stop - futures_price
            reward_dist = futures_price - f_t1

        rr = round(reward_dist / max(0.01, risk_dist), 2)
        if rr < 1.5:
            return FuturesDecision(
                action=FuturesAction.NO_TRADE,
                symbol=symbol,
                underlying_direction=underlying_direction,
                spot_price=spot_price,
                futures_price=futures_price,
                basis=basis,
                basis_pct=basis_pct,
                days_to_expiry=days_to_expiry,
                oi=oi,
                oi_change_pct=oi_change_pct,
                oi_pattern=oi_pattern,
                volume=volume,
                lot_size=lot_size,
                recommended_lots=0,
                total_quantity=0,
                entry_price=futures_price,
                stop_loss=f_stop,
                target_1=f_t1,
                target_2=f_t2,
                risk_reward_ratio=rr,
                margin_required=0.0,
                estimated_costs=0.0,
                is_valid=False,
                rejection_reason="POOR_RISK_REWARD",
                rationale=f"Futures R:R ({rr:.2f}) below minimum 1.5 threshold.",
            )

        # 6. Sizing & Margin Validation
        contract_value_per_lot = futures_price * lot_size
        estimated_margin_per_lot = margin_per_lot if margin_per_lot else contract_value_per_lot * 0.20  # ~20% SPAN+Exposure
        max_allowed_capital = available_capital * (max_capital_allocation_pct / 100.0)

        lots = int(max_allowed_capital // estimated_margin_per_lot)
        if lots < 1:
            return FuturesDecision(
                action=FuturesAction.NO_TRADE,
                symbol=symbol,
                underlying_direction=underlying_direction,
                spot_price=spot_price,
                futures_price=futures_price,
                basis=basis,
                basis_pct=basis_pct,
                days_to_expiry=days_to_expiry,
                oi=oi,
                oi_change_pct=oi_change_pct,
                oi_pattern=oi_pattern,
                volume=volume,
                lot_size=lot_size,
                recommended_lots=0,
                total_quantity=0,
                entry_price=futures_price,
                stop_loss=f_stop,
                target_1=f_t1,
                target_2=f_t2,
                risk_reward_ratio=rr,
                margin_required=estimated_margin_per_lot,
                estimated_costs=0.0,
                is_valid=False,
                rejection_reason="INSUFFICIENT_MARGIN_CAPITAL",
                rationale=f"Required margin per lot (₹{estimated_margin_per_lot:,.0f}) exceeds allocated capital (₹{max_allowed_capital:,.0f}).",
            )

        total_qty = lots * lot_size
        total_margin = lots * estimated_margin_per_lot

        # 7. Transaction Cost Estimation
        costs = TransactionCostCalculator.calculate_roundtrip(
            asset_class=AssetClass.FUTURES,
            entry_price=futures_price,
            exit_price=f_t1,
            quantity=total_qty,
            is_long=(underlying_direction == "LONG"),
        )

        action = FuturesAction.BUY_FUTURE if underlying_direction == "LONG" else FuturesAction.SELL_FUTURE
        rationale = (
            f"Qualified {action.value}: Basis {basis:+.2f} ({basis_pct:+.2f}%), "
            f"OI Pattern {oi_pattern.value}, DTE {days_to_expiry}d, "
            f"R:R {rr:.2f}:1 across {lots} lot(s)."
        )

        return FuturesDecision(
            action=action,
            symbol=symbol,
            underlying_direction=underlying_direction,
            spot_price=spot_price,
            futures_price=futures_price,
            basis=basis,
            basis_pct=basis_pct,
            days_to_expiry=days_to_expiry,
            oi=oi,
            oi_change_pct=oi_change_pct,
            oi_pattern=oi_pattern,
            volume=volume,
            lot_size=lot_size,
            recommended_lots=lots,
            total_quantity=total_qty,
            entry_price=futures_price,
            stop_loss=f_stop,
            target_1=f_t1,
            target_2=f_t2,
            risk_reward_ratio=rr,
            margin_required=total_margin,
            estimated_costs=costs.total_cost,
            is_valid=True,
            rejection_reason=None,
            rationale=rationale,
        )
