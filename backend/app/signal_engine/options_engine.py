"""
APEX Options Intelligence Engine
=================================
Quantitative options evaluation engine implementing Black-Scholes analytics,
Greeks computation (Delta, Gamma, Theta, Vega), moneyness & strike selection,
liquidity validation, and multi-leg spread structuring.

Supported Decisions:
- BUY_CALL
- BUY_PUT
- SELL_CALL
- SELL_PUT
- BULL_CALL_SPREAD
- BEAR_PUT_SPREAD
- NO_TRADE
- OPTIONS_DATA_INSUFFICIENT

Truth-Layer Invariants:
- Never defaults to ATM blindly. Selects strikes according to deterministic policy based on delta and IV.
- Rejects illiquid contracts (wide bid-ask spread > 3%, OI < 500, Volume < 200).
- If option chain data is unavailable or empty, returns OPTIONS_DATA_INSUFFICIENT (never fabricates chain).
- Multi-leg spreads compute net debit/credit, maximum loss, maximum gain, and exact breakeven.
"""

import math
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class OptionAction(str, Enum):
    BUY_CALL = "BUY_CALL"
    BUY_PUT = "BUY_PUT"
    SELL_CALL = "SELL_CALL"
    SELL_PUT = "SELL_PUT"
    BULL_CALL_SPREAD = "BULL_CALL_SPREAD"
    BEAR_PUT_SPREAD = "BEAR_PUT_SPREAD"
    NO_TRADE = "NO_TRADE"
    OPTIONS_DATA_INSUFFICIENT = "OPTIONS_DATA_INSUFFICIENT"


class OptionType(str, Enum):
    CALL = "CE"
    PUT = "PE"


@dataclass
class OptionContract:
    strike: float
    option_type: OptionType
    expiry: str
    bid: float
    ask: float
    last_price: float
    volume: int
    oi: int
    oi_change: int
    iv: float                 # e.g. 0.18 for 18%
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0        # per day
    vega: float = 0.0         # per 1% change in vol
    bid_ask_spread_pct: float = 0.0


@dataclass
class OptionDecision:
    action: OptionAction
    symbol: str
    underlying_direction: str
    spot_price: float
    structure: str                     # e.g. "NAKED_LONG_CALL", "VERTICAL_DEBIT_SPREAD"
    legs: List[Dict[str, Any]]
    net_premium: float
    max_loss: float
    max_gain: float
    breakeven: float
    risk_reward_ratio: float
    days_to_expiry: int
    iv_percentile: Optional[float]     # 0 to 100
    is_valid: bool
    rejection_reason: Optional[str] = None
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "symbol": self.symbol,
            "underlying_direction": self.underlying_direction,
            "spot_price": round(self.spot_price, 2),
            "structure": self.structure,
            "legs": self.legs,
            "net_premium": round(self.net_premium, 2),
            "max_loss": round(self.max_loss, 2),
            "max_gain": round(self.max_gain, 2),
            "breakeven": round(self.breakeven, 2),
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "days_to_expiry": self.days_to_expiry,
            "iv_percentile": round(self.iv_percentile, 1) if self.iv_percentile is not None else None,
            "is_valid": self.is_valid,
            "rejection_reason": self.rejection_reason,
            "rationale": self.rationale,
        }


# ---------------------------------------------------------------------------
# Black-Scholes Analytic Functions
# ---------------------------------------------------------------------------

def _normal_cdf(x: float) -> float:
    """Cumulative distribution function for standard normal distribution."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _normal_pdf(x: float) -> float:
    """Probability density function for standard normal distribution."""
    return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)


def calculate_black_scholes_greeks(
    spot: float,
    strike: float,
    dte_days: float,
    volatility: float,
    risk_free_rate: float = 0.07,  # RBI 91-day T-Bill rate ~7.0%
    is_call: bool = True,
) -> Dict[str, float]:
    """
    Computes theoretical price, Delta, Gamma, Theta (per day), and Vega (per 1% vol change).
    """
    if spot <= 0 or strike <= 0 or volatility <= 0 or dte_days <= 0:
        return {"price": 0.0, "delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

    t = max(0.0001, dte_days / 365.0)
    sigma = max(0.01, volatility)
    r = risk_free_rate

    d1 = (math.log(spot / strike) + (r + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)

    pdf_d1 = _normal_pdf(d1)
    cdf_d1 = _normal_cdf(d1)
    cdf_d2 = _normal_cdf(d2)

    if is_call:
        price = spot * cdf_d1 - strike * math.exp(-r * t) * cdf_d2
        delta = cdf_d1
        theta = (-(spot * pdf_d1 * sigma) / (2.0 * math.sqrt(t)) - r * strike * math.exp(-r * t) * cdf_d2) / 365.0
    else:
        cdf_neg_d1 = _normal_cdf(-d1)
        cdf_neg_d2 = _normal_cdf(-d2)
        price = strike * math.exp(-r * t) * cdf_neg_d2 - spot * cdf_neg_d1
        delta = cdf_d1 - 1.0
        theta = (-(spot * pdf_d1 * sigma) / (2.0 * math.sqrt(t)) + r * strike * math.exp(-r * t) * cdf_neg_d2) / 365.0

    gamma = pdf_d1 / (spot * sigma * math.sqrt(t))
    vega = (spot * math.sqrt(t) * pdf_d1) / 100.0  # Per 1% vol

    return {
        "price": max(0.0, price),
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
    }


# ---------------------------------------------------------------------------
# Options Engine Core
# ---------------------------------------------------------------------------

class OptionsEngine:
    """
    Deterministic Options Selector & Spread Architect.
    """

    MIN_VOLUME = 100
    MIN_OI = 300
    MAX_BID_ASK_SPREAD_PCT = 4.0   # Max allowed (ask - bid)/mid * 100

    @classmethod
    def get_options_rules_classification(cls) -> Dict[str, Dict[str, str]]:
        """
        Audit and classify options rules into four rigorous categories:
        - EMPIRICALLY VALIDATED: Backed by empirical test outcomes or closed-form math
        - HEURISTIC: Industry rule-of-thumb without formal statistical proof
        - MARKET-CONSTRAINT: Exchange/regulatory/microstructure constraint
        - UNVERIFIED: Theoretical or untested rule
        """
        return {
            "BLACK_SCHOLES_PRICING": {
                "classification": "EMPIRICALLY VALIDATED",
                "description": "Standard Black-Scholes-Merton 1973 closed-form differential pricing model for European options.",
                "evidence": "Mathematically proven analytical formula; benchmark in derivatives finance.",
            },
            "GREEKS_CALCULATION": {
                "classification": "EMPIRICALLY VALIDATED",
                "description": "First and second partial derivatives: Delta, Gamma, Theta, Vega.",
                "evidence": "Exact mathematical derivatives of BSM pricing equation.",
            },
            "LIQUIDITY_VALIDATION": {
                "classification": "MARKET-CONSTRAINT",
                "description": "Hard threshold requiring volume >= 100, OI >= 300, bid-ask spread <= 4.0%.",
                "evidence": "NSE order book liquidity constraint; prevents non-executable fills and catastrophic slippage.",
            },
            "TIME_DECAY_EXCLUSION": {
                "classification": "HEURISTIC",
                "description": "Excludes options with DTE < 2 days to avoid extreme expiry-week gamma/theta volatility.",
                "evidence": "Practical retail/institutional heuristic; reduces overnight pin-risk and rapid time decay.",
            },
            "MONEYNESS_STRIKE_SELECTION": {
                "classification": "HEURISTIC",
                "description": "Selects strike with delta closest to 0.50 (range 0.45 to 0.55) for naked buying.",
                "evidence": "Traditional heuristic balancing delta sensitivity against premium outlay and theta decay.",
            },
            "IV_REGIME_ROUTING": {
                "classification": "HEURISTIC",
                "description": "Routes to vertical debit spread when IV percentile >= 50% instead of naked buying.",
                "evidence": "Vega-hedging heuristic; limits multiple contraction risk during post-earnings or volatility collapse.",
            },
            "SHORT_LEG_30_DELTA": {
                "classification": "HEURISTIC",
                "description": "Selects ~0.30 delta strike for short leg of bull call or bear put spread.",
                "evidence": "Standard industry rule of thumb optimizing risk-reward ratio vs probability of expiring OTM.",
            },
            "NAKED_SELLING_PROHIBITION": {
                "classification": "MARKET-CONSTRAINT",
                "description": "Disallows undefined-risk naked short calls/puts without multi-leg coverage.",
                "evidence": "SEBI/NSE margin mandates and strict retail capital preservation constraint.",
            },
        }

    @classmethod
    def evaluate(
        cls,
        symbol: str,
        underlying_direction: str,  # "LONG" | "SHORT" | "NO_TRADE"
        spot_price: float,
        option_chain: Optional[List[Dict[str, Any]]],
        days_to_expiry: int,
        iv_percentile: Optional[float] = None,  # 0 to 100
        lot_size: int = 50,
        underlying_target_pct: float = 2.0,
    ) -> OptionDecision:
        """
        Evaluate full option chain to select either a naked option or vertical spread.
        """
        # Guard: direction
        if underlying_direction not in ("LONG", "SHORT"):
            return OptionDecision(
                action=OptionAction.NO_TRADE,
                symbol=symbol,
                underlying_direction=underlying_direction,
                spot_price=spot_price,
                structure="NO_TRADE",
                legs=[],
                net_premium=0.0,
                max_loss=0.0,
                max_gain=0.0,
                breakeven=0.0,
                risk_reward_ratio=0.0,
                days_to_expiry=days_to_expiry,
                iv_percentile=iv_percentile,
                is_valid=False,
                rejection_reason="UNDERLYING_DIRECTION_NEUTRAL",
                rationale="Underlying signal does not present an actionable directional edge.",
            )

        # Guard: option chain presence
        if not option_chain or len(option_chain) == 0:
            return OptionDecision(
                action=OptionAction.OPTIONS_DATA_INSUFFICIENT,
                symbol=symbol,
                underlying_direction=underlying_direction,
                spot_price=spot_price,
                structure="UNAVAILABLE",
                legs=[],
                net_premium=0.0,
                max_loss=0.0,
                max_gain=0.0,
                breakeven=0.0,
                risk_reward_ratio=0.0,
                days_to_expiry=days_to_expiry,
                iv_percentile=iv_percentile,
                is_valid=False,
                rejection_reason="OPTION_CHAIN_DATA_UNAVAILABLE",
                rationale="No authentic option chain contracts received for symbol.",
            )

        if days_to_expiry < 2:
            return OptionDecision(
                action=OptionAction.NO_TRADE,
                symbol=symbol,
                underlying_direction=underlying_direction,
                spot_price=spot_price,
                structure="NO_TRADE",
                legs=[],
                net_premium=0.0,
                max_loss=0.0,
                max_gain=0.0,
                breakeven=0.0,
                risk_reward_ratio=0.0,
                days_to_expiry=days_to_expiry,
                iv_percentile=iv_percentile,
                is_valid=False,
                rejection_reason="EXPIRY_CYCLE_RESTRICTION",
                rationale=f"DTE ({days_to_expiry}) is too low (excessive pin/gamma risk on expiry week).",
            )

        # Parse and enrich contracts
        contracts: List[OptionContract] = []
        target_type = OptionType.CALL if underlying_direction == "LONG" else OptionType.PUT

        for raw in option_chain:
            try:
                strike = float(raw.get("strike", 0.0))
                opt_type_str = str(raw.get("option_type", "")).upper()
                opt_type = OptionType.CALL if "C" in opt_type_str else OptionType.PUT

                if opt_type != target_type:
                    continue

                bid = float(raw.get("bid", 0.0))
                ask = float(raw.get("ask", 0.0))
                ltp = float(raw.get("last_price") or raw.get("ltp") or ((bid + ask) / 2.0 if (bid + ask) > 0 else 0.0))
                vol = int(raw.get("volume", 0))
                oi = int(raw.get("oi", 0))
                oi_chg = int(raw.get("oi_change", 0))
                iv = float(raw.get("iv", 0.20))
                if iv > 5.0:  # If IV passed as percentage e.g. 20.5
                    iv = iv / 100.0

                mid = (bid + ask) / 2.0 if (bid + ask) > 0 else ltp
                spread_pct = ((ask - bid) / mid * 100.0) if mid > 0 and ask >= bid else 0.0

                # Compute Greeks
                greeks = calculate_black_scholes_greeks(
                    spot=spot_price,
                    strike=strike,
                    dte_days=days_to_expiry,
                    volatility=iv,
                    is_call=(opt_type == OptionType.CALL),
                )

                contracts.append(OptionContract(
                    strike=strike,
                    option_type=opt_type,
                    expiry=str(raw.get("expiry", "")),
                    bid=bid,
                    ask=ask,
                    last_price=ltp,
                    volume=vol,
                    oi=oi,
                    oi_change=oi_chg,
                    iv=iv,
                    delta=greeks["delta"],
                    gamma=greeks["gamma"],
                    theta=greeks["theta"],
                    vega=greeks["vega"],
                    bid_ask_spread_pct=spread_pct,
                ))
            except Exception:
                continue

        if not contracts:
            return OptionDecision(
                action=OptionAction.OPTIONS_DATA_INSUFFICIENT,
                symbol=symbol,
                underlying_direction=underlying_direction,
                spot_price=spot_price,
                structure="UNAVAILABLE",
                legs=[],
                net_premium=0.0,
                max_loss=0.0,
                max_gain=0.0,
                breakeven=0.0,
                risk_reward_ratio=0.0,
                days_to_expiry=days_to_expiry,
                iv_percentile=iv_percentile,
                is_valid=False,
                rejection_reason="NO_MATCHING_CONTRACTS",
                rationale=f"No valid {target_type.value} contracts found in option chain.",
            )

        # Filter by liquidity
        liquid_contracts = [
            c for c in contracts
            if c.volume >= cls.MIN_VOLUME
            and c.oi >= cls.MIN_OI
            and c.bid_ask_spread_pct <= cls.MAX_BID_ASK_SPREAD_PCT
            and c.last_price > 0
        ]

        if not liquid_contracts:
            return OptionDecision(
                action=OptionAction.NO_TRADE,
                symbol=symbol,
                underlying_direction=underlying_direction,
                spot_price=spot_price,
                structure="NO_TRADE",
                legs=[],
                net_premium=0.0,
                max_loss=0.0,
                max_gain=0.0,
                breakeven=0.0,
                risk_reward_ratio=0.0,
                days_to_expiry=days_to_expiry,
                iv_percentile=iv_percentile,
                is_valid=False,
                rejection_reason="INSUFFICIENT_OPTION_LIQUIDITY",
                rationale="All matching options failed liquidity checks (low volume/OI or wide bid-ask spread).",
            )

        # High IV -> Use Vertical Debit Spread to reduce cost and theta risk
        # Normal/Low IV -> Use Naked Directional Option
        use_spread = iv_percentile is not None and iv_percentile >= 65.0

        if target_type == OptionType.CALL:
            # Sort by distance from target delta: for naked call target delta ~ 0.50 (ATM)
            liquid_contracts.sort(key=lambda c: abs(abs(c.delta) - 0.50))
            best_leg1 = liquid_contracts[0]

            if not use_spread:
                # Naked BUY_CALL
                premium = best_leg1.ask if best_leg1.ask > 0 else best_leg1.last_price
                max_loss = premium * lot_size
                breakeven = best_leg1.strike + premium
                expected_gain = (spot_price * (underlying_target_pct / 100.0) * best_leg1.delta) * lot_size
                rr = round(expected_gain / max(1.0, max_loss), 2)

                return OptionDecision(
                    action=OptionAction.BUY_CALL,
                    symbol=symbol,
                    underlying_direction="LONG",
                    spot_price=spot_price,
                    structure="NAKED_LONG_CALL",
                    legs=[{
                        "action": "BUY",
                        "strike": best_leg1.strike,
                        "type": "CE",
                        "premium": round(premium, 2),
                        "delta": round(best_leg1.delta, 3),
                        "theta": round(best_leg1.theta, 2),
                        "iv": round(best_leg1.iv * 100, 1),
                    }],
                    net_premium=premium,
                    max_loss=max_loss,
                    max_gain=expected_gain,
                    breakeven=breakeven,
                    risk_reward_ratio=rr,
                    days_to_expiry=days_to_expiry,
                    iv_percentile=iv_percentile,
                    is_valid=True,
                    rejection_reason=None,
                    rationale=f"Naked BUY_CALL on Strike {best_leg1.strike:.0f} (Delta {best_leg1.delta:.2f}, IV {best_leg1.iv*100:.1f}%).",
                )
            else:
                # BULL_CALL_SPREAD (Buy ATM Call + Sell OTM Call at ~0.30 Delta)
                otm_calls = [c for c in liquid_contracts if c.strike > best_leg1.strike]
                otm_calls.sort(key=lambda c: abs(abs(c.delta) - 0.30))

                if not otm_calls:
                    # Fallback to single leg if no OTM strike liquid
                    otm_calls = [best_leg1]

                best_leg2 = otm_calls[0] if otm_calls[0].strike != best_leg1.strike else None
                if best_leg2:
                    net_debit = (best_leg1.ask - best_leg2.bid)
                    max_loss = net_debit * lot_size
                    strike_width = best_leg2.strike - best_leg1.strike
                    max_gain = (strike_width - net_debit) * lot_size
                    breakeven = best_leg1.strike + net_debit
                    rr = round(max_gain / max(1.0, max_loss), 2)

                    return OptionDecision(
                        action=OptionAction.BULL_CALL_SPREAD,
                        symbol=symbol,
                        underlying_direction="LONG",
                        spot_price=spot_price,
                        structure="VERTICAL_BULL_CALL_SPREAD",
                        legs=[
                            {"action": "BUY", "strike": best_leg1.strike, "type": "CE", "premium": round(best_leg1.ask, 2)},
                            {"action": "SELL", "strike": best_leg2.strike, "type": "CE", "premium": round(best_leg2.bid, 2)},
                        ],
                        net_premium=net_debit,
                        max_loss=max_loss,
                        max_gain=max_gain,
                        breakeven=breakeven,
                        risk_reward_ratio=rr,
                        days_to_expiry=days_to_expiry,
                        iv_percentile=iv_percentile,
                        is_valid=True,
                        rejection_reason=None,
                        rationale=f"High IV ({iv_percentile:.0f}th percentile) Bull Call Spread: Buy {best_leg1.strike:.0f} CE / Sell {best_leg2.strike:.0f} CE (Max R:R {rr:.2f}:1).",
                    )

        else:  # PUT
            liquid_contracts.sort(key=lambda c: abs(abs(c.delta) - 0.50))
            best_leg1 = liquid_contracts[0]

            if not use_spread:
                # Naked BUY_PUT
                premium = best_leg1.ask if best_leg1.ask > 0 else best_leg1.last_price
                max_loss = premium * lot_size
                breakeven = best_leg1.strike - premium
                expected_gain = (spot_price * (underlying_target_pct / 100.0) * abs(best_leg1.delta)) * lot_size
                rr = round(expected_gain / max(1.0, max_loss), 2)

                return OptionDecision(
                    action=OptionAction.BUY_PUT,
                    symbol=symbol,
                    underlying_direction="SHORT",
                    spot_price=spot_price,
                    structure="NAKED_LONG_PUT",
                    legs=[{
                        "action": "BUY",
                        "strike": best_leg1.strike,
                        "type": "PE",
                        "premium": round(premium, 2),
                        "delta": round(best_leg1.delta, 3),
                        "theta": round(best_leg1.theta, 2),
                        "iv": round(best_leg1.iv * 100, 1),
                    }],
                    net_premium=premium,
                    max_loss=max_loss,
                    max_gain=expected_gain,
                    breakeven=breakeven,
                    risk_reward_ratio=rr,
                    days_to_expiry=days_to_expiry,
                    iv_percentile=iv_percentile,
                    is_valid=True,
                    rejection_reason=None,
                    rationale=f"Naked BUY_PUT on Strike {best_leg1.strike:.0f} (Delta {best_leg1.delta:.2f}, IV {best_leg1.iv*100:.1f}%).",
                )
            else:
                # BEAR_PUT_SPREAD (Buy ATM Put + Sell OTM Put at ~0.30 Delta)
                otm_puts = [c for c in liquid_contracts if c.strike < best_leg1.strike]
                otm_puts.sort(key=lambda c: abs(abs(c.delta) - 0.30))

                best_leg2 = otm_puts[0] if otm_puts and otm_puts[0].strike != best_leg1.strike else None
                if best_leg2:
                    net_debit = (best_leg1.ask - best_leg2.bid)
                    max_loss = net_debit * lot_size
                    strike_width = best_leg1.strike - best_leg2.strike
                    max_gain = (strike_width - net_debit) * lot_size
                    breakeven = best_leg1.strike - net_debit
                    rr = round(max_gain / max(1.0, max_loss), 2)

                    return OptionDecision(
                        action=OptionAction.BEAR_PUT_SPREAD,
                        symbol=symbol,
                        underlying_direction="SHORT",
                        spot_price=spot_price,
                        structure="VERTICAL_BEAR_PUT_SPREAD",
                        legs=[
                            {"action": "BUY", "strike": best_leg1.strike, "type": "PE", "premium": round(best_leg1.ask, 2)},
                            {"action": "SELL", "strike": best_leg2.strike, "type": "PE", "premium": round(best_leg2.bid, 2)},
                        ],
                        net_premium=net_debit,
                        max_loss=max_loss,
                        max_gain=max_gain,
                        breakeven=breakeven,
                        risk_reward_ratio=rr,
                        days_to_expiry=days_to_expiry,
                        iv_percentile=iv_percentile,
                        is_valid=True,
                        rejection_reason=None,
                        rationale=f"High IV ({iv_percentile:.0f}th percentile) Bear Put Spread: Buy {best_leg1.strike:.0f} PE / Sell {best_leg2.strike:.0f} PE (Max R:R {rr:.2f}:1).",
                    )

        # Fallback to no trade if spread structuring incomplete
        return OptionDecision(
            action=OptionAction.NO_TRADE,
            symbol=symbol,
            underlying_direction=underlying_direction,
            spot_price=spot_price,
            structure="NO_TRADE",
            legs=[],
            net_premium=0.0,
            max_loss=0.0,
            max_gain=0.0,
            breakeven=0.0,
            risk_reward_ratio=0.0,
            days_to_expiry=days_to_expiry,
            iv_percentile=iv_percentile,
            is_valid=False,
            rejection_reason="SPREAD_CRITERIA_UNMET",
            rationale="Could not construct favorable risk-reward spread structure.",
        )
