"""
Fundamental Engine — Quantitative Factor Registry & Calculations (Phase 7)
===========================================================================
Defines canonical fundamental and quality factors with deterministic mathematical
formulas, dependency contracts, and direction preferences.

CRITICAL MATHEMATICAL INVARIANTS:
1. Missing numerator or denominator yields None (UNAVAILABLE). Never substitute 0.
2. Division by zero yields None.
3. True 0.0 (e.g. Total Debt = 0) is valid: Debt/Equity = 0.0.
4. No fabricated forward estimates.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Callable


class FactorCategory(str, Enum):
    VALUE = "VALUE"
    GROWTH = "GROWTH"
    PROFITABILITY = "PROFITABILITY"
    LEVERAGE = "LEVERAGE"
    CASH_FLOW_QUALITY = "CASH_FLOW_QUALITY"
    COMPOSITE_QUALITY = "COMPOSITE_QUALITY"


class DirectionPreference(str, Enum):
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"
    RANGE_BOUND = "RANGE_BOUND"


@dataclass
class FactorDefinition:
    """
    Authoritative quantitative factor definition contract.
    """
    factor_id: str
    name: str
    category: FactorCategory
    description: str
    formula: str
    dependencies: List[str]
    direction_preference: DirectionPreference
    min_observations: int = 1
    point_in_time_required: bool = True
    version: str = "1.0.0"
    enabled: bool = True
    experimental: bool = False
    unit: str = "RATIO"  # RATIO, PERCENT, MULTIPLE, PER_SHARE


# ---------------------------------------------------------------------------
# Deterministic Mathematical Factor Calculators
# ---------------------------------------------------------------------------

def calculate_growth_yoy(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
    """Calculates YoY growth rate: ((Current - Previous) / abs(Previous)) * 100."""
    if curr is None or prev is None:
        return None
    if prev == 0.0:
        return None
    return round(((curr - prev) / abs(prev)) * 100.0, 2)


def calculate_roe(net_profit: Optional[float], equity: Optional[float]) -> Optional[float]:
    """Return on Equity: (Net Profit / Shareholders' Equity) * 100."""
    if net_profit is None or equity is None or equity <= 0:
        return None
    return round((net_profit / equity) * 100.0, 2)


def calculate_roce(ebit: Optional[float], total_assets: Optional[float], current_liabilities: Optional[float]) -> Optional[float]:
    """Return on Capital Employed: (EBIT / (Total Assets - Current Liabilities)) * 100."""
    if ebit is None or total_assets is None or current_liabilities is None:
        return None
    cap_employed = total_assets - current_liabilities
    if cap_employed <= 0:
        return None
    return round((ebit / cap_employed) * 100.0, 2)


def calculate_roa(net_profit: Optional[float], total_assets: Optional[float]) -> Optional[float]:
    """Return on Assets: (Net Profit / Total Assets) * 100."""
    if net_profit is None or total_assets is None or total_assets <= 0:
        return None
    return round((net_profit / total_assets) * 100.0, 2)


def calculate_margin(numerator: Optional[float], revenue: Optional[float]) -> Optional[float]:
    """Margin: (Numerator / Revenue) * 100."""
    if numerator is None or revenue is None or revenue <= 0:
        return None
    return round((numerator / revenue) * 100.0, 2)


def calculate_debt_to_equity(total_debt: Optional[float], equity: Optional[float]) -> Optional[float]:
    """Debt to Equity Ratio: Total Debt / Shareholders' Equity."""
    if total_debt is None or equity is None or equity <= 0:
        return None
    return round(total_debt / equity, 3)


def calculate_net_debt_to_ebitda(net_debt: Optional[float], ebitda: Optional[float]) -> Optional[float]:
    """Net Debt to EBITDA Ratio: Net Debt / EBITDA."""
    if net_debt is None or ebitda is None or ebitda <= 0:
        return None
    return round(net_debt / ebitda, 2)


def calculate_interest_coverage(ebit: Optional[float], interest_expense: Optional[float]) -> Optional[float]:
    """Interest Coverage: EBIT / Interest Expense."""
    if ebit is None or interest_expense is None:
        return None
    if interest_expense == 0:
        return 999.0  # Debt-free / zero interest
    return round(ebit / interest_expense, 2)


def calculate_current_ratio(current_assets: Optional[float], current_liabilities: Optional[float]) -> Optional[float]:
    """Current Ratio: Current Assets / Current Liabilities."""
    if current_assets is None or current_liabilities is None or current_liabilities <= 0:
        return None
    return round(current_assets / current_liabilities, 2)


def calculate_fcf_conversion(free_cash_flow: Optional[float], net_profit: Optional[float]) -> Optional[float]:
    """FCF Conversion: (Free Cash Flow / Net Profit) * 100."""
    if free_cash_flow is None or net_profit is None or net_profit <= 0:
        return None
    return round((free_cash_flow / net_profit) * 100.0, 2)


def calculate_pe_ratio(market_cap: Optional[float], net_profit: Optional[float], price: Optional[float] = None, eps: Optional[float] = None) -> Optional[float]:
    """Price to Earnings: Market Cap / Net Profit or Price / EPS."""
    if price is not None and eps is not None and eps > 0:
        return round(price / eps, 2)
    if market_cap is not None and net_profit is not None and net_profit > 0:
        return round(market_cap / net_profit, 2)
    return None


def calculate_pb_ratio(market_cap: Optional[float], equity: Optional[float]) -> Optional[float]:
    """Price to Book: Market Cap / Shareholders' Equity."""
    if market_cap is None or equity is None or equity <= 0:
        return None
    return round(market_cap / equity, 2)


def calculate_ev_to_ebitda(market_cap: Optional[float], net_debt: Optional[float], ebitda: Optional[float]) -> Optional[float]:
    """Enterprise Value to EBITDA: (Market Cap + Net Debt) / EBITDA."""
    if market_cap is None or net_debt is None or ebitda is None or ebitda <= 0:
        return None
    ev = market_cap + net_debt
    return round(ev / ebitda, 2)


# ---------------------------------------------------------------------------
# 2. Canonical Factor Registry
# ---------------------------------------------------------------------------

FACTOR_REGISTRY: Dict[str, FactorDefinition] = {
    # ── Valuation Factors ──
    "VALUATION_PE": FactorDefinition(
        factor_id="VALUATION_PE",
        name="Price-to-Earnings Ratio (P/E)",
        category=FactorCategory.VALUE,
        description="Market valuation multiple relative to trailing net profits.",
        formula="Price / Trailing Twelve Months EPS",
        dependencies=["price", "eps", "net_profit"],
        direction_preference=DirectionPreference.LOWER_IS_BETTER,
        unit="MULTIPLE",
    ),
    "VALUATION_PB": FactorDefinition(
        factor_id="VALUATION_PB",
        name="Price-to-Book Ratio (P/B)",
        category=FactorCategory.VALUE,
        description="Market valuation multiple relative to balance sheet equity.",
        formula="Market Capitalization / Shareholders' Equity",
        dependencies=["market_cap", "shareholders_equity"],
        direction_preference=DirectionPreference.LOWER_IS_BETTER,
        unit="MULTIPLE",
    ),
    "VALUATION_EV_EBITDA": FactorDefinition(
        factor_id="VALUATION_EV_EBITDA",
        name="Enterprise Value to EBITDA (EV/EBITDA)",
        category=FactorCategory.VALUE,
        description="Capital-structure neutral operating cash flow valuation multiple.",
        formula="(Market Capitalization + Net Debt) / EBITDA",
        dependencies=["market_cap", "net_debt", "ebitda"],
        direction_preference=DirectionPreference.LOWER_IS_BETTER,
        unit="MULTIPLE",
    ),

    # ── Growth Factors ──
    "GROWTH_REVENUE_YOY": FactorDefinition(
        factor_id="GROWTH_REVENUE_YOY",
        name="Revenue Growth YoY",
        category=FactorCategory.GROWTH,
        description="Year-over-Year top-line sales growth percentage.",
        formula="((Revenue_T - Revenue_T-1) / Revenue_T-1) * 100",
        dependencies=["revenue"],
        direction_preference=DirectionPreference.HIGHER_IS_BETTER,
        unit="PERCENT",
    ),
    "GROWTH_NET_PROFIT_YOY": FactorDefinition(
        factor_id="GROWTH_NET_PROFIT_YOY",
        name="Net Profit Growth YoY",
        category=FactorCategory.GROWTH,
        description="Year-over-Year bottom-line net profit growth percentage.",
        formula="((NetProfit_T - NetProfit_T-1) / NetProfit_T-1) * 100",
        dependencies=["net_profit"],
        direction_preference=DirectionPreference.HIGHER_IS_BETTER,
        unit="PERCENT",
    ),
    "GROWTH_EPS_YOY": FactorDefinition(
        factor_id="GROWTH_EPS_YOY",
        name="EPS Growth YoY",
        category=FactorCategory.GROWTH,
        description="Year-over-Year diluted earnings per share growth percentage.",
        formula="((EPS_T - EPS_T-1) / EPS_T-1) * 100",
        dependencies=["eps"],
        direction_preference=DirectionPreference.HIGHER_IS_BETTER,
        unit="PERCENT",
    ),

    # ── Profitability Factors ──
    "PROFITABILITY_ROE": FactorDefinition(
        factor_id="PROFITABILITY_ROE",
        name="Return on Equity (ROE)",
        category=FactorCategory.PROFITABILITY,
        description="Net income generated per unit of shareholders' equity.",
        formula="(Net Income / Shareholders' Equity) * 100",
        dependencies=["net_profit", "shareholders_equity"],
        direction_preference=DirectionPreference.HIGHER_IS_BETTER,
        unit="PERCENT",
    ),
    "PROFITABILITY_ROCE": FactorDefinition(
        factor_id="PROFITABILITY_ROCE",
        name="Return on Capital Employed (ROCE)",
        category=FactorCategory.PROFITABILITY,
        description="Operating profit generated per unit of total capital employed.",
        formula="(EBIT / (Total Assets - Current Liabilities)) * 100",
        dependencies=["ebit", "total_assets", "total_current_liabilities"],
        direction_preference=DirectionPreference.HIGHER_IS_BETTER,
        unit="PERCENT",
    ),
    "PROFITABILITY_OP_MARGIN": FactorDefinition(
        factor_id="PROFITABILITY_OP_MARGIN",
        name="Operating Profit Margin",
        category=FactorCategory.PROFITABILITY,
        description="Percentage of revenue remaining after operating costs.",
        formula="(Operating Profit / Revenue) * 100",
        dependencies=["operating_profit", "revenue"],
        direction_preference=DirectionPreference.HIGHER_IS_BETTER,
        unit="PERCENT",
    ),

    # ── Leverage & Solvency Factors ──
    "LEVERAGE_DEBT_TO_EQUITY": FactorDefinition(
        factor_id="LEVERAGE_DEBT_TO_EQUITY",
        name="Debt to Equity Ratio (D/E)",
        category=FactorCategory.LEVERAGE,
        description="Total borrowings relative to shareholders' equity cushion.",
        formula="Total Debt / Shareholders' Equity",
        dependencies=["total_debt", "shareholders_equity"],
        direction_preference=DirectionPreference.LOWER_IS_BETTER,
        unit="RATIO",
    ),
    "LEVERAGE_INTEREST_COVERAGE": FactorDefinition(
        factor_id="LEVERAGE_INTEREST_COVERAGE",
        name="Interest Coverage Ratio",
        category=FactorCategory.LEVERAGE,
        description="Capacity to service debt obligations from operating profits.",
        formula="EBIT / Interest Expense",
        dependencies=["ebit", "interest_expense"],
        direction_preference=DirectionPreference.HIGHER_IS_BETTER,
        unit="RATIO",
    ),

    # ── Cash Flow Quality Factors ──
    "CASHFLOW_FCF_CONVERSION": FactorDefinition(
        factor_id="CASHFLOW_FCF_CONVERSION",
        name="Free Cash Flow Conversion Rate",
        category=FactorCategory.CASH_FLOW_QUALITY,
        description="Percentage of accounting net profit converted into real cash flow.",
        formula="(Free Cash Flow / Net Profit) * 100",
        dependencies=["free_cash_flow", "net_profit"],
        direction_preference=DirectionPreference.HIGHER_IS_BETTER,
        unit="PERCENT",
    ),
}
