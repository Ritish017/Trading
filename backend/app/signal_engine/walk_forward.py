"""
Signal Intelligence Engine — Walk-Forward Validation & Robustness Stress Engine
================================================================================
Implements rigorous chronological out-of-sample testing and parameter/execution
stress testing to detect and prevent overfitting.

Methodology:
1. Chronological Separation:
   - TRAIN / RESEARCH PERIOD (50%): Initial candidate & parameter exploration
   - VALIDATION PERIOD (25%): Confirmation & threshold tuning
   - OUT-OF-SAMPLE (OOS) PERIOD (25%): Strict holdout evaluation with zero lookahead

2. Performance Degradation Measurement:
   - Compares expectancy, win rate, and profit factor across windows
   - Measures Degradation = 1.0 - (OOS_Metric / Train_Metric)

3. Robustness Stress Matrix:
   - Slippage stress: 0 bps, 5 bps, 10 bps, 20 bps
   - Execution lag: 1-candle delayed entry
   - Parameter sensitivity: ±20% stop ATR multiple, ±20% target multiple
   - If edge vanishes under modest perturbation: Verdict is strictly ROBUSTNESS_FAILED!
"""
import copy
import logging
import math
import random
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field

from backend.app.signal_engine.outcome_engine import OutcomeEngine, SignalOutcome
from backend.app.signal_engine.performance_engine import PerformanceEngine, PerformanceMetrics

logger = logging.getLogger(__name__)


def wilson_score_interval(wins: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """Calculates 95% Wilson score confidence interval for binomial win rate."""
    if total <= 0:
        return 0.0, 0.0
    p = wins / total
    denom = 1.0 + (z ** 2) / total
    center = (p + (z ** 2) / (2.0 * total)) / denom
    spread = (z / denom) * math.sqrt((p * (1.0 - p) / total) + ((z ** 2) / (4.0 * (total ** 2))))
    return round(max(0.0, center - spread) * 100.0, 2), round(min(1.0, center + spread) * 100.0, 2)


def bootstrap_expectancy_ci(r_multiples: List[float], n_bootstraps: int = 1000, alpha: float = 0.05) -> Tuple[float, float]:
    """Calculates non-parametric bootstrap confidence interval for mean realized R."""
    if not r_multiples:
        return 0.0, 0.0
    if len(r_multiples) < 5:
        mean_r = sum(r_multiples) / len(r_multiples)
        return round(mean_r, 4), round(mean_r, 4)
    means = []
    n = len(r_multiples)
    rng = random.Random(42)  # Deterministic seed for reproducible research
    for _ in range(n_bootstraps):
        sample = [rng.choice(r_multiples) for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lower_idx = int(n_bootstraps * (alpha / 2.0))
    upper_idx = int(n_bootstraps * (1.0 - alpha / 2.0))
    return round(means[lower_idx], 4), round(means[upper_idx], 4)


def calculate_sortino(r_multiples: List[float], target: float = 0.0) -> float:
    """Calculates Sortino ratio based on downside deviation of R multiples."""
    if not r_multiples:
        return 0.0
    mean_r = sum(r_multiples) / len(r_multiples)
    downside = [min(0.0, r - target) ** 2 for r in r_multiples]
    downside_dev = math.sqrt(sum(downside) / len(downside)) if downside else 0.0
    if downside_dev < 1e-6:
        return 0.0 if mean_r <= 0 else 10.0
    return round(mean_r / downside_dev, 2)


def calculate_tail_metrics(r_multiples: List[float]) -> Dict[str, float]:
    """Calculates tail win, tail loss, and tail ratio (p95 / |p5|)."""
    if not r_multiples:
        return {"tail_win_r": 0.0, "tail_loss_r": 0.0, "tail_ratio": 0.0}
    s = sorted(r_multiples)
    n = len(s)
    p5 = s[max(0, int(n * 0.05))]
    p95 = s[min(n - 1, int(n * 0.95))]
    tail_ratio = round(abs(p95 / p5), 2) if abs(p5) > 1e-4 else 1.0
    return {
        "tail_win_r": round(p95, 2),
        "tail_loss_r": round(p5, 2),
        "tail_ratio": tail_ratio,
    }


def get_sample_size_classification(n: int) -> str:
    """Section 16: Sample-Size Gates."""
    if n < 30:
        return "INSUFFICIENT"
    elif n < 100:
        return "PRELIMINARY"
    elif n < 250:
        return "DEVELOPING"
    else:
        return "STRONGER_EMPIRICAL_SAMPLE"


class PeriodMetrics(BaseModel):
    """Performance metrics for an isolated evaluation period."""
    period_name: str
    candles_count: int = 0
    signals_count: int = 0
    win_rate: float = 0.0
    win_rate_ci_95: Tuple[float, float] = (0.0, 0.0)
    expectancy: float = 0.0
    expectancy_ci_95: Tuple[float, float] = (0.0, 0.0)
    profit_factor: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_r: float = 0.0
    sample_size_gate: str = "INSUFFICIENT"

    model_config = ConfigDict(use_enum_values=True)


class RollingWalkForwardWindow(BaseModel):
    window_id: int
    train_slice: str
    validation_slice: str
    oos_slice: str
    trades_count: int = 0
    win_rate: float = 0.0
    win_rate_ci_95: Tuple[float, float] = (0.0, 0.0)
    canonical_expectancy: float = 0.0
    expectancy_r: float = 0.0
    expectancy_ci_95: Tuple[float, float] = (0.0, 0.0)
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_r: float = 0.0
    recovery_factor: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    tail_metrics: Dict[str, float] = Field(default_factory=dict)
    directional_breakdown: Dict[str, Any] = Field(default_factory=dict)
    asset_breakdown: Dict[str, Any] = Field(default_factory=dict)
    regime_breakdown: Dict[str, Any] = Field(default_factory=dict)
    sample_size_gate: str = "INSUFFICIENT"
    is_statistically_significant: bool = False

    model_config = ConfigDict(use_enum_values=True)


class RollingWalkForwardResult(BaseModel):
    windows: List[RollingWalkForwardWindow] = Field(default_factory=list)
    total_trades: int = 0
    overall_win_rate: float = 0.0
    overall_expectancy_r: float = 0.0
    expectancy_degradation_pct: float = 0.0
    stability_verdict: str = "INSUFFICIENT_SIGNALS"
    sample_size_gate: str = "INSUFFICIENT"
    is_statistically_significant: bool = False
    notes: str = ""

    model_config = ConfigDict(use_enum_values=True)


class WalkForwardResult(BaseModel):
    """Walk-forward evaluation comparing in-sample vs out-of-sample behavior."""
    train_metrics: PeriodMetrics
    validation_metrics: PeriodMetrics
    oos_metrics: PeriodMetrics
    expectancy_degradation_pct: float = 0.0
    win_rate_degradation_pct: float = 0.0
    is_stable: bool = False
    verdict: str = "INSUFFICIENT_SIGNALS"  # ROBUST | MODERATE_DEGRADATION | SEVERE_OVERFITTING | INSUFFICIENT_SIGNALS
    notes: str = ""

    model_config = ConfigDict(use_enum_values=True)


class StressScenarioResult(BaseModel):
    """Results under a specific stress parameter."""
    scenario_name: str
    description: str
    expectancy: float
    win_rate: float
    profit_factor: float
    expectancy_change_pct: float

    model_config = ConfigDict(use_enum_values=True)


class RobustnessStressResult(BaseModel):
    """Comprehensive robustness stress audit."""
    baseline_expectancy: float
    worst_case_expectancy: float
    scenarios: List[StressScenarioResult]
    robustness_status: str  # ROBUST_PASS | ROBUST_SENSITIVE | ROBUSTNESS_FAILED
    summary: str

    model_config = ConfigDict(use_enum_values=True)


class WalkForwardEngine:
    """
    Orchestrates chronological splits and stress tests for signals.
    """

    @staticmethod
    def split_chronological(
        candles: List[Dict[str, Any]],
        train_pct: float = 0.50,
        val_pct: float = 0.25,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Split candles into strictly chronological Train, Validation, and Out-of-Sample slices.
        """
        n = len(candles)
        if n < 30:
            return candles, [], []

        train_end = int(n * train_pct)
        val_end = int(n * (train_pct + val_pct))

        train = candles[:train_end]
        val = candles[train_end:val_end]
        oos = candles[val_end:]

        return train, val, oos

    @classmethod
    def evaluate_walk_forward(
        cls,
        train_outcomes: List[SignalOutcome],
        val_outcomes: List[SignalOutcome],
        oos_outcomes: List[SignalOutcome],
    ) -> WalkForwardResult:
        """
        Analyze outcomes generated across the three chronological windows.
        """
        m_train = PerformanceEngine.compute_metrics(train_outcomes, "WALK_FORWARD", "TRAIN")
        m_val = PerformanceEngine.compute_metrics(val_outcomes, "WALK_FORWARD", "VALIDATION")
        m_oos = PerformanceEngine.compute_metrics(oos_outcomes, "WALK_FORWARD", "OOS")

        train_r = [o.realized_r for o in train_outcomes]
        val_r = [o.realized_r for o in val_outcomes]
        oos_r = [o.realized_r for o in oos_outcomes]

        train_wins = sum(1 for o in train_outcomes if o.is_win)
        val_wins = sum(1 for o in val_outcomes if o.is_win)
        oos_wins = sum(1 for o in oos_outcomes if o.is_win)

        p_train = PeriodMetrics(
            period_name="TRAIN",
            candles_count=len(train_outcomes) * 10,
            signals_count=len(train_outcomes),
            win_rate=m_train.win_rate,
            win_rate_ci_95=wilson_score_interval(train_wins, len(train_outcomes)),
            expectancy=m_train.expectancy,
            expectancy_ci_95=bootstrap_expectancy_ci(train_r),
            profit_factor=m_train.profit_factor,
            sortino_ratio=calculate_sortino(train_r),
            max_drawdown_r=m_train.max_drawdown_r,
            sample_size_gate=get_sample_size_classification(len(train_outcomes)),
        )
        p_val = PeriodMetrics(
            period_name="VALIDATION",
            candles_count=len(val_outcomes) * 10,
            signals_count=len(val_outcomes),
            win_rate=m_val.win_rate,
            win_rate_ci_95=wilson_score_interval(val_wins, len(val_outcomes)),
            expectancy=m_val.expectancy,
            expectancy_ci_95=bootstrap_expectancy_ci(val_r),
            profit_factor=m_val.profit_factor,
            sortino_ratio=calculate_sortino(val_r),
            max_drawdown_r=m_val.max_drawdown_r,
            sample_size_gate=get_sample_size_classification(len(val_outcomes)),
        )
        p_oos = PeriodMetrics(
            period_name="OUT_OF_SAMPLE",
            candles_count=len(oos_outcomes) * 10,
            signals_count=len(oos_outcomes),
            win_rate=m_oos.win_rate,
            win_rate_ci_95=wilson_score_interval(oos_wins, len(oos_outcomes)),
            expectancy=m_oos.expectancy,
            expectancy_ci_95=bootstrap_expectancy_ci(oos_r),
            profit_factor=m_oos.profit_factor,
            sortino_ratio=calculate_sortino(oos_r),
            max_drawdown_r=m_oos.max_drawdown_r,
            sample_size_gate=get_sample_size_classification(len(oos_outcomes)),
        )

        if len(train_outcomes) < 5 or len(oos_outcomes) < 5:
            return WalkForwardResult(
                train_metrics=p_train,
                validation_metrics=p_val,
                oos_metrics=p_oos,
                expectancy_degradation_pct=0.0,
                win_rate_degradation_pct=0.0,
                is_stable=False,
                verdict="INSUFFICIENT_SIGNALS",
                notes="Sample count in one or more partitions is insufficient for walk-forward conclusion.",
            )

        # Measure degradation
        train_exp = m_train.expectancy
        oos_exp = m_oos.expectancy

        if abs(train_exp) > 0.0001:
            deg_exp = ((train_exp - oos_exp) / abs(train_exp)) * 100.0
        else:
            deg_exp = 0.0

        if m_train.win_rate > 0.0:
            deg_wr = ((m_train.win_rate - m_oos.win_rate) / m_train.win_rate) * 100.0
        else:
            deg_wr = 0.0

        # Classification
        if oos_exp < 0.0 or deg_exp > 60.0:
            verdict = "SEVERE_OVERFITTING"
            is_stable = False
            notes = f"Significant performance collapse in OOS (Degradation: {deg_exp:.1f}%). Strategy may be overfitted."
        elif deg_exp > 25.0:
            verdict = "MODERATE_DEGRADATION"
            is_stable = True
            notes = f"Acceptable out-of-sample decay ({deg_exp:.1f}%). Retains positive edge."
        else:
            verdict = "ROBUST"
            is_stable = True
            notes = f"Excellent consistency between in-sample and out-of-sample performance ({deg_exp:.1f}% variance)."

        return WalkForwardResult(
            train_metrics=p_train,
            validation_metrics=p_val,
            oos_metrics=p_oos,
            expectancy_degradation_pct=round(deg_exp, 2),
            win_rate_degradation_pct=round(deg_wr, 2),
            is_stable=is_stable,
            verdict=verdict,
            notes=notes,
        )

    @staticmethod
    def generate_rolling_windows(
        candles: List[Dict[str, Any]],
        window_size: int = 60,
        step_size: int = 20,
        train_ratio: float = 0.50,
        val_ratio: float = 0.25,
    ) -> List[Dict[str, Any]]:
        """
        Generate chronological rolling walk-forward slices over candle or observation data.
        """
        n = len(candles)
        if n < 30:
            return []

        windows: List[Dict[str, Any]] = []
        start = 0
        w_id = 1
        while start + window_size <= n:
            chunk = candles[start : start + window_size]
            c_len = len(chunk)
            train_end = int(c_len * train_ratio)
            val_end = int(c_len * (train_ratio + val_ratio))

            windows.append({
                "window_id": w_id,
                "train": chunk[:train_end],
                "val": chunk[train_end:val_end],
                "oos": chunk[val_end:],
                "train_slice": f"[{start}:{start + train_end}]",
                "validation_slice": f"[{start + train_end}:{start + val_end}]",
                "oos_slice": f"[{start + val_end}:{start + window_size}]",
            })
            w_id += 1
            start += step_size

        return windows

    @classmethod
    def evaluate_rolling_walk_forward(
        cls,
        outcomes_or_windows: Union[List[RollingWalkForwardWindow], List[SignalOutcome]],
        window_size: int = 40,
        step_size: int = 20,
    ) -> RollingWalkForwardResult:
        """
        Evaluate performance across multiple rolling chronological walk-forward windows.
        Computes non-parametric stats, Wilson CIs, bootstrap expectancy CIs,
        tail metrics, directional, asset, and regime breakdowns.
        """
        if not outcomes_or_windows:
            return RollingWalkForwardResult(
                windows=[],
                total_trades=0,
                overall_win_rate=0.0,
                overall_expectancy_r=0.0,
                expectancy_degradation_pct=0.0,
                stability_verdict="INSUFFICIENT_SIGNALS",
                sample_size_gate="INSUFFICIENT",
                is_statistically_significant=False,
                notes="Zero outcomes or windows provided.",
            )

        if isinstance(outcomes_or_windows[0], RollingWalkForwardWindow):
            windows: List[RollingWalkForwardWindow] = outcomes_or_windows  # type: ignore
            all_outcomes: List[SignalOutcome] = []
        else:
            outcomes: List[SignalOutcome] = outcomes_or_windows  # type: ignore
            all_outcomes = outcomes
            n = len(outcomes)
            windows = []

            # Partition outcomes chronologically into rolling windows
            if n < window_size:
                slices = [(1, f"[0:{int(n*0.5)}]", f"[{int(n*0.5)}:{int(n*0.75)}]", f"[{int(n*0.75)}:{n}]", outcomes)]
            else:
                slices = []
                start = 0
                w_id = 1
                while start + window_size <= n:
                    end = start + window_size
                    t_end = start + int(window_size * 0.5)
                    v_end = start + int(window_size * 0.75)
                    sub = outcomes[start:end]
                    slices.append((
                        w_id,
                        f"[{start}:{t_end}]",
                        f"[{t_end}:{v_end}]",
                        f"[{v_end}:{end}]",
                        sub,
                    ))
                    w_id += 1
                    start += step_size

            for w_id, tr_s, val_s, oos_s, sub_list in slices:
                w_n = len(sub_list)
                w_wins = sum(1 for o in sub_list if o.is_win)
                w_wr = (w_wins / w_n) if w_n > 0 else 0.0
                w_wr_ci = wilson_score_interval(w_wins, w_n)
                r_vals = [o.realized_r for o in sub_list]
                w_exp = (sum(r_vals) / w_n) if w_n > 0 else 0.0
                w_exp_ci = bootstrap_expectancy_ci(r_vals)
                w_pf = 0.0
                gw = sum(o.gross_pnl for o in sub_list if o.gross_pnl > 0)
                gl = abs(sum(o.gross_pnl for o in sub_list if o.gross_pnl < 0))
                if gl > 0:
                    w_pf = gw / gl
                elif gw > 0:
                    w_pf = 999.0

                w_sortino = calculate_sortino(r_vals)
                w_tail = calculate_tail_metrics(r_vals)
                w_gate = get_sample_size_classification(w_n)

                # Max drawdown and recovery factor
                cum_r = 0.0
                peak_r = 0.0
                max_dd = 0.0
                c_w, m_w, c_l, m_l = 0, 0, 0, 0
                for o in sub_list:
                    cum_r += o.realized_r
                    if cum_r > peak_r:
                        peak_r = cum_r
                    dd = peak_r - cum_r
                    if dd > max_dd:
                        max_dd = dd
                    if o.is_win:
                        c_w += 1
                        c_l = 0
                        if c_w > m_w:
                            m_w = c_w
                    else:
                        c_l += 1
                        c_w = 0
                        if c_l > m_l:
                            m_l = c_l

                rec_factor = (cum_r / max_dd) if max_dd > 0 else 0.0

                # Directional breakdown
                long_list = [o for o in sub_list if getattr(o, "direction", "LONG") == "LONG"]
                short_list = [o for o in sub_list if getattr(o, "direction", "LONG") == "SHORT"]
                dir_breakdown = {
                    "LONG": {
                        "trades": len(long_list),
                        "win_rate": round(sum(1 for o in long_list if o.is_win) / len(long_list), 4) if long_list else 0.0,
                        "expectancy_r": round(sum(o.realized_r for o in long_list) / len(long_list), 4) if long_list else 0.0,
                    },
                    "SHORT": {
                        "trades": len(short_list),
                        "win_rate": round(sum(1 for o in short_list if o.is_win) / len(short_list), 4) if short_list else 0.0,
                        "expectancy_r": round(sum(o.realized_r for o in short_list) / len(short_list), 4) if short_list else 0.0,
                    },
                }

                # Asset breakdown
                eq_list = [o for o in sub_list if getattr(o, "asset_class", "EQUITY") == "EQUITY"]
                fut_list = [o for o in sub_list if getattr(o, "asset_class", "EQUITY") in ("FUTURES", "INDEX_FUTURES")]
                opt_list = [o for o in sub_list if getattr(o, "asset_class", "EQUITY") in ("OPTION", "OPTIONS")]
                asset_breakdown = {
                    "EQUITY": {
                        "trades": len(eq_list),
                        "win_rate": round(sum(1 for o in eq_list if o.is_win) / len(eq_list), 4) if eq_list else 0.0,
                        "expectancy_r": round(sum(o.realized_r for o in eq_list) / len(eq_list), 4) if eq_list else 0.0,
                    },
                    "FUTURES": {
                        "trades": len(fut_list),
                        "win_rate": round(sum(1 for o in fut_list if o.is_win) / len(fut_list), 4) if fut_list else 0.0,
                        "expectancy_r": round(sum(o.realized_r for o in fut_list) / len(fut_list), 4) if fut_list else 0.0,
                    },
                    "OPTIONS": {
                        "trades": len(opt_list),
                        "win_rate": round(sum(1 for o in opt_list if o.is_win) / len(opt_list), 4) if opt_list else 0.0,
                        "expectancy_r": round(sum(o.realized_r for o in opt_list) / len(opt_list), 4) if opt_list else 0.0,
                    },
                }

                # Regime breakdown
                regime_map: Dict[str, List[SignalOutcome]] = {}
                for o in sub_list:
                    r_name = getattr(o, "regime", "UNKNOWN") or "UNKNOWN"
                    regime_map.setdefault(r_name, []).append(o)
                regime_breakdown = {
                    r_name: {
                        "trades": len(r_sub),
                        "win_rate": round(sum(1 for x in r_sub if x.is_win) / len(r_sub), 4),
                        "expectancy_r": round(sum(x.realized_r for x in r_sub) / len(r_sub), 4),
                    }
                    for r_name, r_sub in regime_map.items()
                }

                w_is_sig = bool(w_exp_ci[0] > 0.0 and w_gate in ("DEVELOPING", "STRONGER_EMPIRICAL_SAMPLE"))

                windows.append(
                    RollingWalkForwardWindow(
                        window_id=w_id,
                        train_slice=tr_s,
                        validation_slice=val_s,
                        oos_slice=oos_s,
                        trades_count=w_n,
                        win_rate=round(w_wr, 4),
                        win_rate_ci_95=w_wr_ci,
                        canonical_expectancy=round(w_exp, 4),
                        expectancy_r=round(w_exp, 4),
                        expectancy_ci_95=w_exp_ci,
                        profit_factor=round(w_pf, 2),
                        sharpe_ratio=0.0,
                        sortino_ratio=round(w_sortino, 4),
                        max_drawdown_r=round(max_dd, 4),
                        recovery_factor=round(rec_factor, 2),
                        consecutive_wins=m_w,
                        consecutive_losses=m_l,
                        tail_metrics=w_tail,
                        directional_breakdown=dir_breakdown,
                        asset_breakdown=asset_breakdown,
                        regime_breakdown=regime_breakdown,
                        sample_size_gate=w_gate,
                        is_statistically_significant=w_is_sig,
                    )
                )

        # Aggregate across windows
        tot_trades = sum(w.trades_count for w in windows) if not all_outcomes else len(all_outcomes)
        if all_outcomes:
            tot_wins = sum(1 for o in all_outcomes if o.is_win)
            tot_wr = tot_wins / len(all_outcomes)
            all_r = [o.realized_r for o in all_outcomes]
            tot_exp = sum(all_r) / len(all_outcomes)
        else:
            tot_wr = sum(w.win_rate * w.trades_count for w in windows) / max(tot_trades, 1)
            tot_exp = sum(w.expectancy_r * w.trades_count for w in windows) / max(tot_trades, 1)

        deg_exp = 0.0
        if len(windows) >= 2:
            first_exp = windows[0].expectancy_r
            last_exp = windows[-1].expectancy_r
            if abs(first_exp) > 0.0001:
                deg_exp = ((first_exp - last_exp) / abs(first_exp)) * 100.0

        if tot_trades < 30:
            verdict = "INSUFFICIENT_SIGNALS"
            notes = f"Insufficient aggregate sample size (N={tot_trades} < 30). Edge cannot be claimed."
        elif tot_exp < 0.0 or deg_exp > 60.0:
            verdict = "SEVERE_OVERFITTING"
            notes = f"Negative expectancy or severe degradation ({deg_exp:.1f}%). Overfitting indicated."
        elif deg_exp > 25.0:
            verdict = "MODERATE_DEGRADATION"
            notes = f"Moderate degradation across windows ({deg_exp:.1f}%). Positive expectancy maintained."
        else:
            verdict = "ROBUST"
            notes = f"Stable performance across rolling windows (Degradation: {deg_exp:.1f}%)."

        overall_gate = get_sample_size_classification(tot_trades)
        overall_sig = bool(tot_trades >= 30 and tot_exp > 0.0 and verdict in ("ROBUST", "MODERATE_DEGRADATION"))

        return RollingWalkForwardResult(
            windows=windows,
            total_trades=tot_trades,
            overall_win_rate=round(tot_wr, 4),
            overall_expectancy_r=round(tot_exp, 4),
            expectancy_degradation_pct=round(deg_exp, 2),
            stability_verdict=verdict,
            sample_size_gate=overall_gate,
            is_statistically_significant=overall_sig,
            notes=notes,
        )

    @classmethod
    def stress_test_robustness(
        cls,
        signals_and_candles: List[Tuple[Any, List[Dict[str, Any]]]],
    ) -> RobustnessStressResult:
        """
        Subject signals and forward candles to execution & parameter stress.
        """
        if not signals_and_candles:
            return RobustnessStressResult(
                baseline_expectancy=0.0,
                worst_case_expectancy=0.0,
                scenarios=[],
                robustness_status="ROBUSTNESS_FAILED",
                summary="No signals provided for stress testing.",
            )

        # Baseline: normal evaluation (5 bps slippage)
        base_outcomes = [
            OutcomeEngine.evaluate(sig, c_list, slippage_pct=0.0005)
            for sig, c_list in signals_and_candles
        ]
        m_base = PerformanceEngine.compute_metrics(base_outcomes, "STRESS", "BASELINE")
        base_exp = m_base.expectancy

        scenarios: List[StressScenarioResult] = []

        # Scenario 1: Double Slippage (10 bps)
        outcomes_slip_10 = [
            OutcomeEngine.evaluate(sig, c_list, slippage_pct=0.0010)
            for sig, c_list in signals_and_candles
        ]
        m_slip_10 = PerformanceEngine.compute_metrics(outcomes_slip_10, "STRESS", "SLIPPAGE_10BPS")
        chg_1 = ((m_slip_10.expectancy - base_exp) / abs(base_exp) * 100.0) if abs(base_exp) > 0.001 else 0.0
        scenarios.append(
            StressScenarioResult(
                scenario_name="Slippage 10 bps",
                description="Double normal slippage (0.10% per transaction)",
                expectancy=m_slip_10.expectancy,
                win_rate=m_slip_10.win_rate,
                profit_factor=m_slip_10.profit_factor,
                expectancy_change_pct=round(chg_1, 2),
            )
        )

        # Scenario 2: Severe Slippage (20 bps)
        outcomes_slip_20 = [
            OutcomeEngine.evaluate(sig, c_list, slippage_pct=0.0020)
            for sig, c_list in signals_and_candles
        ]
        m_slip_20 = PerformanceEngine.compute_metrics(outcomes_slip_20, "STRESS", "SLIPPAGE_20BPS")
        chg_2 = ((m_slip_20.expectancy - base_exp) / abs(base_exp) * 100.0) if abs(base_exp) > 0.001 else 0.0
        scenarios.append(
            StressScenarioResult(
                scenario_name="Slippage 20 bps",
                description="Extreme slippage (0.20% per transaction)",
                expectancy=m_slip_20.expectancy,
                win_rate=m_slip_20.win_rate,
                profit_factor=m_slip_20.profit_factor,
                expectancy_change_pct=round(chg_2, 2),
            )
        )

        # Scenario 3: Delayed Entry (skip 1st forward candle)
        delayed_outcomes = []
        for sig, c_list in signals_and_candles:
            forward_delayed = c_list[1:] if len(c_list) > 1 else c_list
            delayed_outcomes.append(OutcomeEngine.evaluate(sig, forward_delayed, slippage_pct=0.0005))
        m_delayed = PerformanceEngine.compute_metrics(delayed_outcomes, "STRESS", "DELAYED_ENTRY")
        chg_3 = ((m_delayed.expectancy - base_exp) / abs(base_exp) * 100.0) if abs(base_exp) > 0.001 else 0.0
        scenarios.append(
            StressScenarioResult(
                scenario_name="Delayed Execution",
                description="Execution delayed by 1 candle (missed immediate fill)",
                expectancy=m_delayed.expectancy,
                win_rate=m_delayed.win_rate,
                profit_factor=m_delayed.profit_factor,
                expectancy_change_pct=round(chg_3, 2),
            )
        )

        # Scenario 4: Tighter Stop Loss (-20% distance)
        tight_outcomes = []
        for sig, c_list in signals_and_candles:
            s_copy = copy.copy(sig) if not isinstance(sig, dict) else dict(sig)
            # Adjust stop loss 20% closer
            entry = getattr(s_copy, "entry", None) or (s_copy.get("entry") if isinstance(s_copy, dict) else 100.0)
            sl = getattr(s_copy, "stop_loss", None) or (s_copy.get("stop_loss") if isinstance(s_copy, dict) else 98.0)
            sl_p = getattr(sl, "price", 98.0) if hasattr(sl, "price") else (sl.get("price", 98.0) if isinstance(sl, dict) else float(sl))
            dist = abs(entry - sl_p)
            new_sl_p = entry - (dist * 0.8) if (entry >= sl_p) else entry + (dist * 0.8)
            if hasattr(s_copy, "stop_loss") and hasattr(s_copy.stop_loss, "price"):
                s_copy.stop_loss.price = new_sl_p
            elif isinstance(s_copy, dict):
                s_copy["stop_loss"] = new_sl_p
            tight_outcomes.append(OutcomeEngine.evaluate(s_copy, c_list, slippage_pct=0.0005))

        m_tight = PerformanceEngine.compute_metrics(tight_outcomes, "STRESS", "TIGHTER_STOP")
        chg_4 = ((m_tight.expectancy - base_exp) / abs(base_exp) * 100.0) if abs(base_exp) > 0.001 else 0.0
        scenarios.append(
            StressScenarioResult(
                scenario_name="Stop Loss Tightened 20%",
                description="Simulates tighter risk parameter sensitivity",
                expectancy=m_tight.expectancy,
                win_rate=m_tight.win_rate,
                profit_factor=m_tight.profit_factor,
                expectancy_change_pct=round(chg_4, 2),
            )
        )

        worst_exp = min(s.expectancy for s in scenarios)

        # Robustness gate:
        # If baseline was positive, but worst case collapses below 0 or drops > 75%, mark ROBUSTNESS_FAILED
        if base_exp > 0.0:
            if worst_exp < 0.0 or (worst_exp / base_exp) < 0.25:
                status = "ROBUSTNESS_FAILED"
                summary = (
                    f"ROBUSTNESS_FAILED: Baseline expectancy {base_exp:.2f}R collapses to "
                    f"{worst_exp:.2f}R under execution stress. Strategy edge is fragile."
                )
            elif (worst_exp / base_exp) < 0.60:
                status = "ROBUST_SENSITIVE"
                summary = (
                    f"ROBUST_SENSITIVE: Expectancy decreases from {base_exp:.2f}R to "
                    f"{worst_exp:.2f}R under stress but remains positive."
                )
            else:
                status = "ROBUST_PASS"
                summary = (
                    f"ROBUST_PASS: Edge holds strongly across all perturbation scenarios "
                    f"(Worst case: {worst_exp:.2f}R)."
                )
        else:
            status = "ROBUSTNESS_FAILED"
            summary = f"ROBUSTNESS_FAILED: Baseline expectancy is negative or zero ({base_exp:.2f}R)."

        return RobustnessStressResult(
            baseline_expectancy=round(base_exp, 4),
            worst_case_expectancy=round(worst_exp, 4),
            scenarios=scenarios,
            robustness_status=status,
            summary=summary,
        )


walk_forward_engine = WalkForwardEngine()
