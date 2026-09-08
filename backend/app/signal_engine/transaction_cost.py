"""
APEX Centralized Transaction Cost Engine
=========================================
Authoritative, centralized statutory, exchange, brokerage, and slippage cost calculator
compliant with current Indian regulatory schedules (SEBI, NSE, BSE, CDSL, Stamp Act).

Asset Classes Covered:
- EQUITY_DELIVERY
- EQUITY_INTRADAY
- FUTURES
- OPTIONS

Statutory & Exchange Schedule:
- Brokerage: ₹20 flat or 0.05% max per executed order (whichever is lower, or flat ₹20 for F&O)
- STT (Securities Transaction Tax):
    * Equity Delivery: 0.1% on buy and 0.1% on sell
    * Equity Intraday: 0.025% on sell only
    * Futures: 0.02% on sell turnover
    * Options: 0.1% on sell premium (exercised: 0.125% on intrinsic)
- Exchange Turnover Fee (NSE):
    * Cash Equity: 0.00345% (0.0000345)
    * Futures: 0.002% (0.00002)
    * Options: 0.053% of premium turnover (0.00053)
- GST: 18% on (Brokerage + Exchange Turnover Fee + SEBI Charges)
- SEBI Turnover Charges: ₹10 per crore (0.0001% / 0.000001)
- Stamp Duty:
    * Equity Delivery Buy: 0.015%
    * Equity Intraday Buy: 0.003%
    * Futures Buy: 0.002%
    * Options Buy: 0.003% of premium
- Slippage: Modeled dynamically based on asset tier and spread.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


COST_MODEL_VERSION = "NSE-STATUTORY-2026-V1"

COST_MODEL_METADATA: Dict[str, Any] = {
    "version": COST_MODEL_VERSION,
    "jurisdiction": "INDIA_SEBI_NSE",
    "effective_date": "2024-10-01",
    "updated_for_fy26": True,
    "statutory_rates": {
        "stt": {
            "equity_delivery": 0.001,
            "equity_intraday_sell": 0.00025,
            "futures_sell": 0.0002,
            "options_sell_premium": 0.001,
        },
        "exchange_turnover": {
            "equity": 0.0000345,
            "futures": 0.00002,
            "options_premium": 0.00053,
        },
        "gst_rate": 0.18,
        "sebi_turnover_rate": 0.000001,
        "stamp_duty": {
            "equity_delivery_buy": 0.00015,
            "equity_intraday_buy": 0.00003,
            "futures_buy": 0.00002,
            "options_buy_premium": 0.00003,
        },
    },
    "default_slippage_bps": {
        "large_cap": 2.0,
        "mid_cap": 5.0,
        "index_futures": 1.0,
        "index_options": 10.0,
    },
}


class AssetClass(str, Enum):
    EQUITY_DELIVERY = "EQUITY_DELIVERY"
    EQUITY_INTRADAY = "EQUITY_INTRADAY"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"

# Alias for compatibility across engines
AssetType = AssetClass


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class CostBreakdown:
    turnover: float
    brokerage: float
    stt: float
    exchange_charges: float
    sebi_charges: float
    stamp_duty: float
    gst: float
    slippage: float
    total_statutory_and_exchange: float
    total_cost: float
    net_effective_pct: float

    @property
    def total_costs(self) -> float:
        return self.total_cost

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turnover": round(self.turnover, 2),
            "brokerage": round(self.brokerage, 2),
            "stt": round(self.stt, 2),
            "exchange_charges": round(self.exchange_charges, 2),
            "sebi_charges": round(self.sebi_charges, 4),
            "stamp_duty": round(self.stamp_duty, 2),
            "gst": round(self.gst, 2),
            "slippage": round(self.slippage, 2),
            "total_statutory_and_exchange": round(self.total_statutory_and_exchange, 2),
            "total_cost": round(self.total_cost, 2),
            "total_costs": round(self.total_cost, 2),
            "net_effective_pct": round(self.net_effective_pct, 4),
        }


class TransactionCostCalculator:
    """
    Centralized statutory and commercial transaction cost calculator.
    """

    GST_RATE = 0.18
    SEBI_RATE = 10.0 / 10000000.0  # ₹10 per crore = 0.000001

    @classmethod
    def calculate(
        cls,
        asset_type: AssetClass,
        buy_price: float,
        sell_price: float,
        quantity: int,
        slippage_pct: float = 0.0005,
    ) -> CostBreakdown:
        """Convenience method for roundtrip calculation."""
        slippage_bps = slippage_pct * 10000.0
        return cls.calculate_roundtrip(
            asset_class=asset_type,
            entry_price=buy_price,
            exit_price=sell_price,
            quantity=quantity,
            is_long=True,
            slippage_bps=slippage_bps,
        )

    @classmethod
    def calculate_single_leg(
        cls,
        asset_class: AssetClass,
        side: OrderSide,
        price: float,
        quantity: int,
        slippage_bps: float = 2.0,
    ) -> CostBreakdown:
        """
        Calculate precise friction on a single order leg.
        slippage_bps: basis points (1 bp = 0.01% = 0.0001)
        """
        if price <= 0 or quantity <= 0:
            return CostBreakdown(
                turnover=0.0,
                brokerage=0.0,
                stt=0.0,
                exchange_charges=0.0,
                sebi_charges=0.0,
                stamp_duty=0.0,
                gst=0.0,
                slippage=0.0,
                total_statutory_and_exchange=0.0,
                total_cost=0.0,
                net_effective_pct=0.0,
            )

        turnover = price * quantity
        slippage = turnover * (slippage_bps / 10000.0)

        # 1. Brokerage
        if asset_class in (AssetClass.FUTURES, AssetClass.OPTIONS):
            brokerage = 20.0
        elif asset_class == AssetClass.EQUITY_INTRADAY:
            brokerage = min(20.0, turnover * 0.0005)
        else:  # Delivery
            brokerage = min(20.0, turnover * 0.001)

        # 2. STT
        if asset_class == AssetClass.EQUITY_DELIVERY:
            stt = turnover * 0.001  # 0.1% buy & sell
        elif asset_class == AssetClass.EQUITY_INTRADAY:
            stt = turnover * 0.00025 if side == OrderSide.SELL else 0.0
        elif asset_class == AssetClass.FUTURES:
            stt = turnover * 0.0002 if side == OrderSide.SELL else 0.0
        elif asset_class == AssetClass.OPTIONS:
            stt = turnover * 0.001 if side == OrderSide.SELL else 0.0
        else:
            stt = 0.0

        # 3. Exchange turnover charges
        if asset_class in (AssetClass.EQUITY_DELIVERY, AssetClass.EQUITY_INTRADAY):
            exch_rate = 0.0000345
        elif asset_class == AssetClass.FUTURES:
            exch_rate = 0.0000200
        else:  # Options premium
            exch_rate = 0.0005300
        exchange_charges = turnover * exch_rate

        # 4. SEBI turnover charges
        sebi_charges = turnover * cls.SEBI_RATE

        # 5. Stamp duty (applicable strictly on BUY leg)
        if side == OrderSide.BUY:
            if asset_class == AssetClass.EQUITY_DELIVERY:
                stamp_duty = turnover * 0.00015
            elif asset_class == AssetClass.EQUITY_INTRADAY:
                stamp_duty = turnover * 0.00003
            elif asset_class == AssetClass.FUTURES:
                stamp_duty = turnover * 0.00002
            else:  # Options
                stamp_duty = turnover * 0.00003
        else:
            stamp_duty = 0.0

        # 6. GST
        gst = (brokerage + exchange_charges + sebi_charges) * cls.GST_RATE

        total_statutory = stt + exchange_charges + sebi_charges + stamp_duty + gst
        total_cost = brokerage + total_statutory + slippage
        net_pct = (total_cost / turnover) * 100.0 if turnover > 0 else 0.0

        return CostBreakdown(
            turnover=turnover,
            brokerage=brokerage,
            stt=stt,
            exchange_charges=exchange_charges,
            sebi_charges=sebi_charges,
            stamp_duty=stamp_duty,
            gst=gst,
            slippage=slippage,
            total_statutory_and_exchange=total_statutory,
            total_cost=total_cost,
            net_effective_pct=net_pct,
        )

    @classmethod
    def calculate_roundtrip(
        cls,
        asset_class: AssetClass,
        entry_price: float,
        exit_price: float,
        quantity: int,
        is_long: bool = True,
        slippage_bps: float = 2.0,
    ) -> CostBreakdown:
        """
        Calculate total roundtrip transaction costs (Entry leg + Exit leg).
        """
        entry_side = OrderSide.BUY if is_long else OrderSide.SELL
        exit_side = OrderSide.SELL if is_long else OrderSide.BUY

        leg1 = cls.calculate_single_leg(asset_class, entry_side, entry_price, quantity, slippage_bps)
        leg2 = cls.calculate_single_leg(asset_class, exit_side, exit_price, quantity, slippage_bps)

        total_turnover = leg1.turnover + leg2.turnover
        total_brokerage = leg1.brokerage + leg2.brokerage
        total_stt = leg1.stt + leg2.stt
        total_exchange = leg1.exchange_charges + leg2.exchange_charges
        total_sebi = leg1.sebi_charges + leg2.sebi_charges
        total_stamp = leg1.stamp_duty + leg2.stamp_duty
        total_gst = leg1.gst + leg2.gst
        total_slippage = leg1.slippage + leg2.slippage

        total_stat = total_stt + total_exchange + total_sebi + total_stamp + total_gst
        total_cost = total_brokerage + total_stat + total_slippage
        net_pct = (total_cost / total_turnover) * 100.0 if total_turnover > 0 else 0.0

        return CostBreakdown(
            turnover=total_turnover,
            brokerage=total_brokerage,
            stt=total_stt,
            exchange_charges=total_exchange,
            sebi_charges=total_sebi,
            stamp_duty=total_stamp,
            gst=total_gst,
            slippage=total_slippage,
            total_statutory_and_exchange=total_stat,
            total_cost=total_cost,
            net_effective_pct=net_pct,
        )


# Alias for compatibility across live paper and signal engines
TransactionCostEngine = TransactionCostCalculator
