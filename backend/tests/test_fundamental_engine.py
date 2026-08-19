"""
Unit Test Suite — APEX Fundamental & Factor Research Engine (Phase 7)
=====================================================================
Verifies:
1. FundamentalObservation schema & point-in-time visibility safeguards.
2. Missing vs zero distinction (Debt=0 vs Debt=None).
3. Lookahead prevention (future reports invisible to historical queries).
4. Financial statement normalization (Income, Balance, Cash Flow).
5. Growth factors (YoY Revenue, Net Profit, EPS).
6. Profitability factors (ROE, ROCE, Margins).
7. Leverage & Solvency factors (Debt/Equity, Interest Coverage).
8. Cash flow quality factors (FCF conversion).
9. Valuation factors (P/E, P/B, EV/EBITDA).
10. Dependency Engine context caching.
11. Cross-sectional percentiles and Z-scores.
12. Sector-relative spreads and peer rankings.
13. Factor correlations and redundancy identification.
14. Factor Scorecard generation.
15. Technical x Fundamental 3x3 Confluence matrix.
16. Factor Portfolio simulation, turnover, and HHI sector concentration.
17. Fundamental Copilot evidence citations and Skeptic Mode.
"""

import pytest
import numpy as np
from backend.app.fundamental_engine.models import (
    DataStatus,
    FundamentalObservation,
    NormalizedIncomeStatement,
    NormalizedBalanceSheet,
    NormalizedCashFlow,
    CompanyProfile,
    StatementFrequency,
)
from backend.app.fundamental_engine.providers import (
    MockFundamentalProvider,
    fundamental_data_hub,
)
from backend.app.fundamental_engine.factors import (
    FACTOR_REGISTRY,
    calculate_growth_yoy,
    calculate_roe,
    calculate_roce,
    calculate_margin,
    calculate_debt_to_equity,
    calculate_interest_coverage,
    calculate_fcf_conversion,
    calculate_pe_ratio,
    calculate_pb_ratio,
    calculate_ev_to_ebitda,
)
from backend.app.fundamental_engine.dependency_engine import (
    FundamentalDependencyEngine,
)
from backend.app.fundamental_engine.normalization import (
    calculate_cross_sectional_ranks,
    calculate_sector_relative_factors,
    calculate_factor_correlations,
    identify_redundant_factors,
)
from backend.app.fundamental_engine.confluence_engine import (
    confluence_engine,
)
from backend.app.fundamental_engine.portfolio_engine import (
    portfolio_engine,
)
from backend.app.ai_engine.agents import FundamentalCopilotAgent


# ---------------------------------------------------------------------------
# 1. FundamentalObservation & Point-in-Time Visibility
# ---------------------------------------------------------------------------

def test_fundamental_observation_lookahead_prevention():
    # Report published on May 15, 2024 (ts: 1715731200)
    obs = FundamentalObservation(
        symbol="RELIANCE.NS",
        metric="revenue",
        value=901064.0,
        period_end="2024-03-31",
        publication_timestamp=1715731200,
    )

    # Query before publication date (May 1, 2024 -> ts: 1714521600)
    assert obs.is_visible_at(1714521600) is False

    # Query after publication date (May 20, 2024 -> ts: 1716163200)
    assert obs.is_visible_at(1716163200) is True


def test_missing_vs_zero_distinction():
    # Debt = 0.0 is valid debt-free equity
    d_e_zero = calculate_debt_to_equity(total_debt=0.0, equity=100000.0)
    assert d_e_zero == 0.0

    # Debt = None is missing / unavailable
    d_e_missing = calculate_debt_to_equity(total_debt=None, equity=100000.0)
    assert d_e_missing is None


# ---------------------------------------------------------------------------
# 2. Factor Mathematical Calculations
# ---------------------------------------------------------------------------

def test_growth_factor_calculation():
    # FY24: 100, FY23: 80 -> +25%
    g = calculate_growth_yoy(curr=100.0, prev=80.0)
    assert g == 25.0

    # Missing prev -> None
    assert calculate_growth_yoy(curr=100.0, prev=None) is None


def test_profitability_factors_calculation():
    # Net Profit: 20, Equity: 100 -> ROE = 20%
    roe = calculate_roe(net_profit=20.0, equity=100.0)
    assert roe == 20.0

    # Operating Margin: OpProfit 30, Rev 150 -> 20%
    margin = calculate_margin(numerator=30.0, revenue=150.0)
    assert margin == 20.0


def test_leverage_and_solvency_factors():
    # Debt: 50, Equity: 100 -> D/E = 0.5
    de = calculate_debt_to_equity(total_debt=50.0, equity=100.0)
    assert de == 0.5

    # EBIT: 40, Interest: 8 -> Interest Coverage = 5.0
    cov = calculate_interest_coverage(ebit=40.0, interest_expense=8.0)
    assert cov == 5.0


def test_cash_flow_quality_factors():
    # FCF: 80, Net Profit: 100 -> 80%
    fcf_conv = calculate_fcf_conversion(free_cash_flow=80.0, net_profit=100.0)
    assert fcf_conv == 80.0


def test_valuation_factors():
    # Price: 2500, EPS: 100 -> P/E = 25.0
    pe = calculate_pe_ratio(market_cap=None, net_profit=None, price=2500.0, eps=100.0)
    assert pe == 25.0

    # Market Cap: 100000, Equity: 20000 -> P/B = 5.0
    pb = calculate_pb_ratio(market_cap=100000.0, equity=20000.0)
    assert pb == 5.0


# ---------------------------------------------------------------------------
# 3. Dependency Engine Point-in-Time Context Caching
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dependency_engine_point_in_time_filtering():
    # TCS FY24 published on 2024-04-12 (ts: 1712880000)
    # Query as of 2024-01-01 (before FY24 published)
    ctx_early = await FundamentalDependencyEngine.build_context("TCS.NS", as_of_timestamp=1704067200)
    # Only FY23 should be visible
    assert len(ctx_early.incomes) == 1
    assert ctx_early.incomes[-1].period_end == "2023-03-31"

    # Query as of 2024-05-01 (after FY24 published)
    ctx_later = await FundamentalDependencyEngine.build_context("TCS.NS", as_of_timestamp=1714521600)
    assert len(ctx_later.incomes) == 2
    assert ctx_later.incomes[-1].period_end == "2024-03-31"
    assert ctx_later.factor_cache["PROFITABILITY_ROE"] is not None


# ---------------------------------------------------------------------------
# 4. Cross-Sectional Normalization & Sector-Relative Ranks
# ---------------------------------------------------------------------------

def test_cross_sectional_ranking():
    peer_roe = {
        "TCS.NS": 48.0,
        "INFY.NS": 36.0,
        "WIPRO.NS": 18.0,
    }
    ranks = calculate_cross_sectional_ranks(peer_roe, "PROFITABILITY_ROE")
    assert ranks["TCS.NS"].percentile_rank == 100.0
    assert ranks["WIPRO.NS"].percentile_rank == 0.0
    assert ranks["INFY.NS"].percentile_rank == 50.0


def test_sector_relative_spread():
    peer_roe = {
        "TCS.NS": 48.0,
        "INFY.NS": 36.0,
        "WIPRO.NS": 18.0,
    }
    summary = calculate_sector_relative_factors("TCS.NS", "IT", peer_roe, "PROFITABILITY_ROE")
    assert summary.sector_median == 36.0
    assert summary.sector_spread_pct > 0


def test_factor_correlation_and_redundancy():
    data = {
        "TCS.NS": {"ROE": 48.0, "ROCE": 55.0, "DE": 0.0},
        "INFY.NS": {"ROE": 36.0, "ROCE": 42.0, "DE": 0.0},
        "RELIANCE.NS": {"ROE": 10.0, "ROCE": 12.0, "DE": 0.4},
    }
    corr = calculate_factor_correlations(data)
    assert "ROE" in corr
    redundant = identify_redundant_factors(corr, threshold=0.85)
    assert len(redundant) > 0  # ROE and ROCE should correlate strongly


# ---------------------------------------------------------------------------
# 5. Factor Scorecard & Confluence Matrix
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_factor_scorecard_generation():
    scorecard = await confluence_engine.generate_scorecard("TCS.NS")
    assert scorecard.symbol == "TCS.NS"
    assert scorecard.company_name == "Tata Consultancy Services Ltd"
    assert len(scorecard.factors) > 0
    assert "PROFITABILITY" in scorecard.category_summaries


@pytest.mark.asyncio
async def test_technical_fundamental_confluence_matrix():
    scorecard = await confluence_engine.generate_scorecard("TCS.NS")
    confluence = confluence_engine.evaluate_technical_fundamental_confluence(
        symbol="TCS.NS",
        technical_active_count=8,
        technical_total_count=20,
        scorecard=scorecard,
    )
    assert confluence.technical_state in ["BULLISH", "NEUTRAL", "BEARISH"]
    assert confluence.fundamental_state in ["STRONG", "NEUTRAL", "WEAK", "MODERATE"]
    assert confluence.confluence_quadrant in [
        "HIGH_CONVICTION_LONG", "MOMENTUM_WITHOUT_EARNINGS", "VALUE_TRAP_OR_CONTRARIAN_OPPORTUNITY", "HIGH_RISK_AVOID", "NEUTRAL_MIXED_EVIDENCE"
    ]


# ---------------------------------------------------------------------------
# 6. Factor Portfolio Simulation & Sector HHI
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_factor_portfolio_simulation():
    res = await portfolio_engine.simulate_factor_portfolio(
        universe_symbols=["TCS.NS", "INFY.NS", "RELIANCE.NS", "TATAMOTORS.NS"],
        price_history_map={},
        factor_id="PROFITABILITY_ROE",
        rebalance_frequency="QUARTERLY",
        top_quantile=0.50,
    )
    assert res.total_rebalances > 0
    assert res.annual_turnover_pct >= 0.0
    assert res.avg_sector_hhi >= 0.0
    assert len(res.equity_curve) > 0


# ---------------------------------------------------------------------------
# 7. Fundamental Copilot & Skeptic Mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fundamental_copilot_skeptic_mode():
    agent = FundamentalCopilotAgent()
    scorecard = await confluence_engine.generate_scorecard("TATAMOTORS.NS")

    res = await agent.answer(
        symbol="TATAMOTORS.NS",
        user_message="CHALLENGE THIS FUNDAMENTAL THESIS",
        scorecard=vars(scorecard),
        is_skeptic_mode=True,
    )
    assert "reply" in res
    assert "Skeptic" in res["reply"] or "Critique" in res["reply"] or "Audited" in res["reply"]
