"""
Signal Intelligence Engine — Signal Performance Analytics
===========================================================
Aggregates post-trade forward outcomes into empirical statistical metrics
across multiple operational dimensions.

Key Principles:
- Computes sample size, win rate, expectancy, profit factor, drawdown in R, MAE, MFE
- Strict anti-cheating: Does not claim statistical significance when sample size < 30
- Exposes clear warnings for under-sampled dimensions
"""
import logging
import math
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict

from backend.app.signal_engine.outcome_engine import SignalOutcome

logger = logging.getLogger(__name__)

MINIMUM_STATISTICAL_SAMPLE = 30


class PerformanceMetrics(BaseModel):
    """Statistical performance metrics for a specific dimension slice."""
    dimension_type: str
    dimension_value: str
    sample_size: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    average_r: float = 0.0
    median_r: float = 0.0
    expectancy: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_r: float = 0.0
    avg_mae_r: float = 0.0
    avg_mfe_r: float = 0.0
    target_1_hit_rate: float = 0.0
    target_2_hit_rate: float = 0.0
    target_3_hit_rate: float = 0.0
    avg_holding_candles: float = 0.0
    avg_holding_time_minutes: float = 0.0
    is_statistically_significant: bool = False
    sample_size_warning: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class PerformanceEngine:
    """
    Computes multi-dimensional performance statistics from verified outcomes.
    """

    @staticmethod
    def compute_metrics(
        outcomes: List[SignalOutcome],
        dimension_type: str = "ALL",
        dimension_value: str = "TOTAL",
    ) -> PerformanceMetrics:
        """
        Compute empirical performance metrics for a list of outcomes.
        """
        n = len(outcomes)
        if n == 0:
            return PerformanceMetrics(
                dimension_type=dimension_type,
                dimension_value=dimension_value,
                sample_size=0,
                is_statistically_significant=False,
                sample_size_warning="Zero observations available.",
            )

        wins = sum(1 for o in outcomes if o.is_win)
        losses = n - wins
        win_rate = wins / n

        r_values = [o.realized_r for o in outcomes]
        r_values_sorted = sorted(r_values)
        avg_r = sum(r_values) / n
        median_r = r_values_sorted[n // 2] if n % 2 != 0 else (r_values_sorted[n // 2 - 1] + r_values_sorted[n // 2]) / 2.0

        win_rs = [o.realized_r for o in outcomes if o.realized_r > 0]
        loss_rs = [abs(o.realized_r) for o in outcomes if o.realized_r <= 0]
        avg_win_r = (sum(win_rs) / len(win_rs)) if win_rs else 0.0
        avg_loss_r = (sum(loss_rs) / len(loss_rs)) if loss_rs else 0.0

        # Expectancy in R multiples
        expectancy = (win_rate * avg_win_r) - ((1.0 - win_rate) * avg_loss_r)

        # Profit Factor
        gross_wins = sum(o.gross_pnl for o in outcomes if o.gross_pnl > 0)
        gross_losses = abs(sum(o.gross_pnl for o in outcomes if o.gross_pnl < 0))
        if gross_losses > 0:
            profit_factor = gross_wins / gross_losses
        elif gross_wins > 0:
            profit_factor = 999.0
        else:
            profit_factor = 0.0

        # Max Drawdown in R (cumulative R curve)
        cum_r = 0.0
        peak_r = 0.0
        max_dd_r = 0.0
        for r in r_values:
            cum_r += r
            if cum_r > peak_r:
                peak_r = cum_r
            dd = peak_r - cum_r
            if dd > max_dd_r:
                max_dd_r = dd

        # Excursion & hit rates
        avg_mae_r = sum(o.mae_r for o in outcomes) / n
        avg_mfe_r = sum(o.mfe_r for o in outcomes) / n

        t1_hits = sum(1 for o in outcomes if o.status in ("TARGET_1", "TARGET_2", "TARGET_3"))
        t2_hits = sum(1 for o in outcomes if o.status in ("TARGET_2", "TARGET_3"))
        t3_hits = sum(1 for o in outcomes if o.status == "TARGET_3")

        t1_rate = t1_hits / n
        t2_rate = t2_hits / n
        t3_rate = t3_hits / n

        avg_holding_candles = sum(o.holding_candles for o in outcomes) / n
        avg_holding_mins = sum(o.holding_time_seconds / 60.0 for o in outcomes) / n

        is_significant = n >= MINIMUM_STATISTICAL_SAMPLE
        warning = None
        if not is_significant:
            warning = f"INSUFFICIENT SAMPLE SIZE (N={n} < {MINIMUM_STATISTICAL_SAMPLE}). Metrics must not be treated as reliable edge."

        return PerformanceMetrics(
            dimension_type=dimension_type,
            dimension_value=dimension_value,
            sample_size=n,
            wins=wins,
            losses=losses,
            win_rate=round(win_rate, 4),
            average_r=round(avg_r, 4),
            median_r=round(median_r, 4),
            expectancy=round(expectancy, 4),
            profit_factor=round(profit_factor, 2),
            max_drawdown_r=round(max_dd_r, 4),
            avg_mae_r=round(avg_mae_r, 4),
            avg_mfe_r=round(avg_mfe_r, 4),
            target_1_hit_rate=round(t1_rate, 4),
            target_2_hit_rate=round(t2_rate, 4),
            target_3_hit_rate=round(t3_rate, 4),
            avg_holding_candles=round(avg_holding_candles, 1),
            avg_holding_time_minutes=round(avg_holding_mins, 1),
            is_statistically_significant=is_significant,
            sample_size_warning=warning,
        )

    @classmethod
    def compute_multi_dimension(
        cls,
        outcomes: List[SignalOutcome],
    ) -> Dict[str, Dict[str, PerformanceMetrics]]:
        """
        Segment outcomes across direction and asset class.
        """
        results: Dict[str, Dict[str, PerformanceMetrics]] = {}

        # Overall
        results["TOTAL"] = {"TOTAL": cls.compute_metrics(outcomes, "TOTAL", "TOTAL")}

        # By Direction
        by_dir: Dict[str, List[SignalOutcome]] = {}
        for o in outcomes:
            by_dir.setdefault(o.direction, []).append(o)
        results["DIRECTION"] = {
            d: cls.compute_metrics(sub_list, "DIRECTION", d)
            for d, sub_list in by_dir.items()
        }

        # By Asset Class
        by_asset: Dict[str, List[SignalOutcome]] = {}
        for o in outcomes:
            by_asset.setdefault(o.asset_class, []).append(o)
        results["ASSET_CLASS"] = {
            a: cls.compute_metrics(sub_list, "ASSET_CLASS", a)
            for a, sub_list in by_asset.items()
        }

        return results


performance_engine = PerformanceEngine()
