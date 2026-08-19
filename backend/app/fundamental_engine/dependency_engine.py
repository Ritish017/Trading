"""
Fundamental Engine — Dependency & Calculation Context (Phase 7)
===============================================================
Manages point-in-time calculation contexts, normalized statement lookups,
and dependency aggregation without redundant financial statement parsing.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple

from backend.app.fundamental_engine.models import (
    DataStatus,
    StatementFrequency,
    NormalizedIncomeStatement,
    NormalizedBalanceSheet,
    NormalizedCashFlow,
    CompanyProfile,
    FundamentalObservation,
)
from backend.app.fundamental_engine.providers import fundamental_data_hub
from backend.app.fundamental_engine.factors import (
    FACTOR_REGISTRY,
    FactorDefinition,
    calculate_growth_yoy,
    calculate_roe,
    calculate_roce,
    calculate_roa,
    calculate_margin,
    calculate_debt_to_equity,
    calculate_net_debt_to_ebitda,
    calculate_interest_coverage,
    calculate_current_ratio,
    calculate_fcf_conversion,
    calculate_pe_ratio,
    calculate_pb_ratio,
    calculate_ev_to_ebitda,
)

logger = logging.getLogger(__name__)


@dataclass
class FundamentalDependencyContext:
    """
    Point-in-time fundamental evaluation context for a specific symbol as of a specific date.
    Strictly encapsulates only financial information published on or before as_of_timestamp.
    """
    symbol: str
    as_of_timestamp: int
    profile: Optional[CompanyProfile] = None
    incomes: List[NormalizedIncomeStatement] = field(default_factory=list)
    balances: List[NormalizedBalanceSheet] = field(default_factory=list)
    cashflows: List[NormalizedCashFlow] = field(default_factory=list)
    observations: List[FundamentalObservation] = field(default_factory=list)
    factor_cache: Dict[str, Optional[float]] = field(default_factory=dict)
    current_price: Optional[float] = None


class FundamentalDependencyEngine:
    """
    Point-in-time factor dependency calculation engine.
    Ensures zero lookahead by strictly filtering out reports published after as_of_timestamp.
    """

    @classmethod
    async def build_context(
        cls,
        symbol: str,
        as_of_timestamp: Optional[int] = None,
        current_price: Optional[float] = None,
    ) -> FundamentalDependencyContext:
        limit_ts = as_of_timestamp or int(time.time())
        clean_sym = symbol.upper().strip()

        profile = await fundamental_data_hub.get_company_profile(clean_sym)
        all_incomes = await fundamental_data_hub.active_provider.get_income_statements(clean_sym)
        all_balances = await fundamental_data_hub.active_provider.get_balance_sheets(clean_sym)
        all_cashflows = await fundamental_data_hub.active_provider.get_cash_flows(clean_sym)

        # Point-in-Time Lookahead Filtering
        visible_incomes = [inc for inc in all_incomes if inc.publication_timestamp <= limit_ts]
        visible_balances = [bal for bal in all_balances if bal.publication_timestamp <= limit_ts]
        visible_cashflows = [cf for cf in all_cashflows if cf.publication_timestamp <= limit_ts]

        obs = await fundamental_data_hub.get_point_in_time_observations(
            clean_sym,
            metrics=["revenue", "ebitda", "ebit", "net_profit", "eps", "shareholders_equity", "total_debt", "net_debt", "total_assets", "operating_cash_flow", "free_cash_flow"],
            as_of_timestamp=limit_ts,
        )

        ctx = FundamentalDependencyContext(
            symbol=clean_sym,
            as_of_timestamp=limit_ts,
            profile=profile,
            incomes=visible_incomes,
            balances=visible_balances,
            cashflows=visible_cashflows,
            observations=obs,
            current_price=current_price,
        )

        cls._precalculate_factors(ctx)
        return ctx

    @classmethod
    def _precalculate_factors(cls, ctx: FundamentalDependencyContext):
        """Pre-calculates all canonical registered factors for the context."""
        latest_inc = ctx.incomes[-1] if ctx.incomes else None
        prev_inc = ctx.incomes[-2] if len(ctx.incomes) >= 2 else None

        latest_bal = ctx.balances[-1] if ctx.balances else None
        prev_bal = ctx.balances[-2] if len(ctx.balances) >= 2 else None

        latest_cf = ctx.cashflows[-1] if ctx.cashflows else None
        prev_cf = ctx.cashflows[-2] if len(ctx.cashflows) >= 2 else None

        # ── Growth ──
        if latest_inc and prev_inc:
            ctx.factor_cache["GROWTH_REVENUE_YOY"] = calculate_growth_yoy(latest_inc.revenue, prev_inc.revenue)
            ctx.factor_cache["GROWTH_NET_PROFIT_YOY"] = calculate_growth_yoy(latest_inc.net_profit, prev_inc.net_profit)
            ctx.factor_cache["GROWTH_EPS_YOY"] = calculate_growth_yoy(latest_inc.eps, prev_inc.eps)
        else:
            ctx.factor_cache["GROWTH_REVENUE_YOY"] = None
            ctx.factor_cache["GROWTH_NET_PROFIT_YOY"] = None
            ctx.factor_cache["GROWTH_EPS_YOY"] = None

        # ── Profitability ──
        if latest_inc and latest_bal:
            ctx.factor_cache["PROFITABILITY_ROE"] = calculate_roe(latest_inc.net_profit, latest_bal.shareholders_equity)
            ctx.factor_cache["PROFITABILITY_ROCE"] = calculate_roce(latest_inc.ebit, latest_bal.total_assets, latest_bal.total_current_liabilities)
            ctx.factor_cache["PROFITABILITY_OP_MARGIN"] = calculate_margin(latest_inc.operating_profit, latest_inc.revenue)
        else:
            ctx.factor_cache["PROFITABILITY_ROE"] = None
            ctx.factor_cache["PROFITABILITY_ROCE"] = None
            ctx.factor_cache["PROFITABILITY_OP_MARGIN"] = None

        # ── Leverage ──
        if latest_bal:
            ctx.factor_cache["LEVERAGE_DEBT_TO_EQUITY"] = calculate_debt_to_equity(latest_bal.total_debt, latest_bal.shareholders_equity)
        else:
            ctx.factor_cache["LEVERAGE_DEBT_TO_EQUITY"] = None

        if latest_inc:
            ctx.factor_cache["LEVERAGE_INTEREST_COVERAGE"] = calculate_interest_coverage(latest_inc.ebit, latest_inc.interest_expense)
        else:
            ctx.factor_cache["LEVERAGE_INTEREST_COVERAGE"] = None

        # ── Cash Flow Quality ──
        if latest_cf and latest_inc:
            ctx.factor_cache["CASHFLOW_FCF_CONVERSION"] = calculate_fcf_conversion(latest_cf.free_cash_flow, latest_inc.net_profit)
        else:
            ctx.factor_cache["CASHFLOW_FCF_CONVERSION"] = None

        # ── Valuation ──
        mcap = ctx.profile.market_cap_crores if ctx.profile else None
        if latest_inc:
            ctx.factor_cache["VALUATION_PE"] = calculate_pe_ratio(mcap, latest_inc.net_profit, price=ctx.current_price, eps=latest_inc.eps)
        else:
            ctx.factor_cache["VALUATION_PE"] = None

        if latest_bal:
            ctx.factor_cache["VALUATION_PB"] = calculate_pb_ratio(mcap, latest_bal.shareholders_equity)
        else:
            ctx.factor_cache["VALUATION_PB"] = None

        if latest_inc and latest_bal:
            ctx.factor_cache["VALUATION_EV_EBITDA"] = calculate_ev_to_ebitda(mcap, latest_bal.net_debt, latest_inc.ebitda)
        else:
            ctx.factor_cache["VALUATION_EV_EBITDA"] = None

    @classmethod
    def get_factor_value(cls, ctx: FundamentalDependencyContext, factor_id: str) -> Optional[float]:
        """Returns the computed factor value from the point-in-time context."""
        return ctx.factor_cache.get(factor_id)
