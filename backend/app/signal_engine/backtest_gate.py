"""
Quantitative Backtest Quality & Robustness Gate
===============================================
Ported directly from `tradermonty/claude-trading-skills`: `backtest-expert`.

Implements 5-dimension scoring framework with exact Decimal arithmetic
(eliminating floating-point cancellation error and noise):
  1. Sample Size   (0-20 pts) — Minimum 30 trades required for statistical validity.
  2. Expectancy    (0-20 pts) — Exact Decimal E = win_rate*avg_win - loss_rate*avg_loss.
  3. Risk Mgmt     (0-20 pts) — Max Drawdown (<20% is ideal; >=50% is catastrophic failure) and Profit Factor.
  4. Robustness    (0-20 pts) — Parameter count (penalty for >=7 parameters) and historical years tested.
  5. Exec Realism  (0-20 pts) — Conservative slippage and brokerage friction modeled.

Total: 0-100 pts.
Thresholds:
  >= 70 -> Deploy (Permitted to execute in paper/forward engine)
  40-69 -> Refine (Requires parameter tightening)
  < 40  -> Abandon (Overfitted, negative expectancy, or high risk)
"""

import math
from decimal import Decimal, localcontext
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel


def _exact(value: float) -> Decimal:
    return Decimal(repr(float(value)))


def _exact_components(
    win_rate: float, avg_win_pct: float, avg_loss_pct: float
) -> Tuple[Decimal, Decimal]:
    """Exact (win_rate * avg_win, (100 - win_rate) * avg_loss), both scaled by 100."""
    wr = _exact(win_rate)
    with localcontext() as ctx:
        ctx.prec = 100
        return wr * _exact(avg_win_pct), (Decimal(100) - wr) * _exact(avg_loss_pct)


def score_sample_size(total_trades: int) -> int:
    """Score based on number of trades. <30 -> 0; 30 -> 8; 100 -> 15; 200+ -> 20."""
    if total_trades < 30:
        return 0
    if total_trades < 100:
        return 8 + int((total_trades - 30) / 70 * 7)
    if total_trades < 200:
        return 15 + int((total_trades - 100) / 100 * 5)
    return 20


def calc_expectancy(win_rate: float, avg_win_pct: float, avg_loss_pct: float) -> float:
    """Exact decimal expectancy per trade in percent."""
    profit, loss = _exact_components(win_rate, avg_win_pct, avg_loss_pct)
    with localcontext() as ctx:
        ctx.prec = 100
        return float((profit - loss) / 100)


def score_expectancy(win_rate: float, avg_win_pct: float, avg_loss_pct: float) -> int:
    """Score based on expectancy value. <=0 -> 0; 0..0.5 -> 5..10; 0.5..1.5 -> 10..18; >=1.5 -> 20."""
    exp = calc_expectancy(win_rate, avg_win_pct, avg_loss_pct)
    if exp <= 0:
        return 0
    if exp < 0.5:
        return 5 + int(exp / 0.5 * 5)
    if exp < 1.5:
        return 10 + int((exp - 0.5) / 1.0 * 8)
    return 20


def calc_profit_factor(win_rate: float, avg_win_pct: float, avg_loss_pct: float) -> float:
    """Calculate exact profit factor: (win_rate * avg_win) / (loss_rate * avg_loss)."""
    profit, loss = _exact_components(win_rate, avg_win_pct, avg_loss_pct)
    if loss == 0:
        return float("inf") if profit > 0 else 0.0
    with localcontext() as ctx:
        ctx.prec = 100
        return float(profit / loss)


def score_risk_management(
    max_drawdown_pct: float,
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
) -> int:
    """
    Score based on max drawdown (0-12) and profit factor (0-8).
    Hard ceiling: >= 50% drawdown returns 0 immediately.
    """
    if max_drawdown_pct >= 50:
        return 0
    if max_drawdown_pct < 20:
        dd_score = 12
    else:
        dd_score = int(12 * (50 - max_drawdown_pct) / 30)

    pf = calc_profit_factor(win_rate, avg_win_pct, avg_loss_pct)
    exp = calc_expectancy(win_rate, avg_win_pct, avg_loss_pct)
    if exp <= 0:
        pf_score = 0
    elif pf >= 3.0:
        pf_score = 8
    elif pf <= 1.0:
        pf_score = 0
    else:
        pf_score = int(8 * (pf - 1.0) / 2.0)

    return dd_score + pf_score


def score_robustness(years_tested: int, num_parameters: int) -> int:
    """
    Years component (0-12): <1 -> 0, 1..4 -> linear 2..10, >=5 -> 12.
    Parameters component (0-8): 1-3 -> 8, 4 -> 6, 5-6 -> 3, >=7 -> 0.
    """
    if years_tested < 1:
        years_score = 0
    elif years_tested < 5:
        years_score = 2 + int((years_tested - 1) / 4 * 8)
    else:
        years_score = 12

    if num_parameters <= 3:
        param_score = 8
    elif num_parameters == 4:
        param_score = 6
    elif num_parameters <= 6:
        param_score = 3
    else:
        param_score = 0

    return years_score + param_score


def score_execution_realism(slippage_tested: bool) -> int:
    return 20 if slippage_tested else 0


class BacktestEvaluationResult(BaseModel):
    total_score: int
    verdict: str  # "Deploy", "Refine", "Abandon"
    sample_size_score: int
    expectancy_score: int
    risk_mgmt_score: int
    robustness_score: int
    execution_realism_score: int
    expectancy_value: float
    profit_factor: float
    red_flags: List[str]


def evaluate_backtest_robustness(
    total_trades: int,
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
    max_drawdown_pct: float,
    years_tested: int = 5,
    num_parameters: int = 3,
    slippage_tested: bool = True,
) -> BacktestEvaluationResult:
    """
    Evaluates quantitative strategy backtest quality.
    """
    s_sample = score_sample_size(total_trades)
    s_exp = score_expectancy(win_rate, avg_win_pct, avg_loss_pct)
    s_risk = score_risk_management(max_drawdown_pct, win_rate, avg_win_pct, avg_loss_pct)
    s_rob = score_robustness(years_tested, num_parameters)
    s_exec = score_execution_realism(slippage_tested)

    total_score = s_sample + s_exp + s_risk + s_rob + s_exec

    if total_score >= 70:
        verdict = "Deploy"
    elif total_score >= 40:
        verdict = "Refine"
    else:
        verdict = "Abandon"

    # Red flags
    red_flags = []
    if total_trades < 30:
        red_flags.append(f"Insufficient sample size: {total_trades} trades (< 30 minimum).")
    if not slippage_tested:
        red_flags.append("Execution friction/slippage omitted.")
    if max_drawdown_pct >= 50:
        red_flags.append(f"Catastrophic drawdown risk: {max_drawdown_pct}%.")
    if num_parameters >= 7:
        red_flags.append(f"High overfitting risk: {num_parameters} tunable parameters.")
    if calc_expectancy(win_rate, avg_win_pct, avg_loss_pct) <= 0:
        red_flags.append("Non-positive mathematical expectancy.")

    return BacktestEvaluationResult(
        total_score=total_score,
        verdict=verdict,
        sample_size_score=s_sample,
        expectancy_score=s_exp,
        risk_mgmt_score=s_risk,
        robustness_score=s_rob,
        execution_realism_score=s_exec,
        expectancy_value=round(calc_expectancy(win_rate, avg_win_pct, avg_loss_pct), 4),
        profit_factor=round(calc_profit_factor(win_rate, avg_win_pct, avg_loss_pct), 2),
        red_flags=red_flags,
    )
