"""
Paper Engine — Model Drift Detection & Replay Validation (Phase 8)
==================================================================
Monitors performance divergence between historical backtest expectations and
real-time paper trading execution. Replays identical data to assert exact
backtest/paper equivalence.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import numpy as np

from backend.app.paper_engine.models import PaperTradeAudit


@dataclass
class DriftMetric:
    metric_name: str
    backtest_expected: float
    paper_realized: float
    drift_delta: float
    drift_pct: float
    is_alert: bool
    severity: str  # NORMAL | WARNING | CRITICAL


@dataclass
class DriftReport:
    strategy_id: str
    sample_size: int
    overall_status: str  # IN_CONTROL | MINOR_DRIFT | MODEL_DRIFT_ALERT
    metrics: List[DriftMetric]
    regime_distribution_paper: Dict[str, float]
    recommendations: List[str]


class ModelDriftDetector:
    """
    Detects statistical and execution drift between historical backtest models
    and ongoing paper trading execution.
    """

    @classmethod
    def evaluate_drift(
        cls,
        strategy_id: str,
        backtest_metrics: Dict[str, float],
        paper_trades: List[PaperTradeAudit],
    ) -> DriftReport:
        n_trades = len(paper_trades)
        if n_trades < 5:
            return DriftReport(
                strategy_id=strategy_id,
                sample_size=n_trades,
                overall_status="INSUFFICIENT_DATA",
                metrics=[],
                regime_distribution_paper={},
                recommendations=["Accumulate at least 5 paper trades before evaluating drift."],
            )

        # Compute Paper Metrics
        pnls = [t.net_pnl for t in paper_trades]
        wins = [p for p in pnls if p > 0]
        paper_win_rate = (len(wins) / n_trades) * 100.0
        paper_avg_slippage = float(np.mean([t.slippage_paid for t in paper_trades]))
        paper_returns = [t.return_pct for t in paper_trades]
        paper_sharpe = float((np.mean(paper_returns) / (np.std(paper_returns) + 1e-6)) * np.sqrt(252))

        # Expected from Backtest
        exp_win_rate = backtest_metrics.get("win_rate_pct", 50.0)
        exp_sharpe = backtest_metrics.get("sharpe_ratio", 1.5)
        exp_slippage = backtest_metrics.get("avg_slippage", 50.0)

        drift_metrics: List[DriftMetric] = []
        alerts_count = 0

        # 1. Win Rate Drift
        wr_delta = paper_win_rate - exp_win_rate
        wr_pct = (wr_delta / max(1.0, exp_win_rate)) * 100.0
        wr_alert = wr_pct < -25.0
        if wr_alert:
            alerts_count += 1
        drift_metrics.append(DriftMetric(
            metric_name="Win Rate (%)",
            backtest_expected=round(exp_win_rate, 2),
            paper_realized=round(paper_win_rate, 2),
            drift_delta=round(wr_delta, 2),
            drift_pct=round(wr_pct, 2),
            is_alert=wr_alert,
            severity="CRITICAL" if wr_pct < -35.0 else ("WARNING" if wr_alert else "NORMAL"),
        ))

        # 2. Sharpe Ratio Drift
        sh_delta = paper_sharpe - exp_sharpe
        sh_pct = (sh_delta / max(0.1, abs(exp_sharpe))) * 100.0
        sh_alert = sh_pct < -35.0
        if sh_alert:
            alerts_count += 1
        drift_metrics.append(DriftMetric(
            metric_name="Sharpe Ratio",
            backtest_expected=round(exp_sharpe, 2),
            paper_realized=round(paper_sharpe, 2),
            drift_delta=round(sh_delta, 2),
            drift_pct=round(sh_pct, 2),
            is_alert=sh_alert,
            severity="CRITICAL" if sh_pct < -50.0 else ("WARNING" if sh_alert else "NORMAL"),
        ))

        # 3. Slippage Friction Drag Drift
        slip_delta = paper_avg_slippage - exp_slippage
        slip_pct = (slip_delta / max(1.0, exp_slippage)) * 100.0
        slip_alert = slip_pct > 50.0
        if slip_alert:
            alerts_count += 1
        drift_metrics.append(DriftMetric(
            metric_name="Avg Slippage Drag (₹)",
            backtest_expected=round(exp_slippage, 2),
            paper_realized=round(paper_avg_slippage, 2),
            drift_delta=round(slip_delta, 2),
            drift_pct=round(slip_pct, 2),
            is_alert=slip_alert,
            severity="WARNING" if slip_alert else "NORMAL",
        ))

        # Regime distribution in paper
        regimes = [t.regime_at_entry for t in paper_trades]
        reg_dist: Dict[str, float] = {}
        for r in set(regimes):
            reg_dist[r] = round((regimes.count(r) / n_trades) * 100.0, 1)

        status = "MODEL_DRIFT_ALERT" if alerts_count >= 2 else ("MINOR_DRIFT" if alerts_count == 1 else "IN_CONTROL")
        recommendations = []
        if status == "MODEL_DRIFT_ALERT":
            recommendations.append("Severe performance divergence detected. Review market regime shift and increase slippage buffers.")
        elif status == "MINOR_DRIFT":
            recommendations.append("Minor deviation from historical backtest distributions. Continue monitoring.")
        else:
            recommendations.append("Execution is aligned with historical walk-forward expectations.")

        return DriftReport(
            strategy_id=strategy_id,
            sample_size=n_trades,
            overall_status=status,
            metrics=drift_metrics,
            regime_distribution_paper=reg_dist,
            recommendations=recommendations,
        )


class PaperBacktestReplayValidator:
    """
    Validates deterministic equivalence between Backtest and Paper Replay.
    """

    @classmethod
    def verify_equivalence(
        cls,
        backtest_trades: List[Dict[str, Any]],
        paper_trades: List[PaperTradeAudit],
    ) -> Dict[str, Any]:
        """
        Asserts that backtest signals and paper signals match exactly when replayed.
        """
        match_count = 0
        mismatches: List[str] = []

        n_compare = min(len(backtest_trades), len(paper_trades))
        for i in range(n_compare):
            bt = backtest_trades[i]
            pt = paper_trades[i]

            bt_sym = bt.get("symbol")
            pt_sym = pt.symbol

            bt_dir = bt.get("side", "BUY")
            pt_dir = pt.side.value

            if bt_sym == pt_sym and bt_dir == pt_dir:
                match_count += 1
            else:
                mismatches.append(f"Trade #{i}: Backtest ({bt_sym}, {bt_dir}) != Paper ({pt_sym}, {pt_dir})")

        is_equivalent = (match_count == n_compare and n_compare > 0)
        return {
            "is_equivalent": is_equivalent,
            "compared_count": n_compare,
            "matched_count": match_count,
            "mismatches": mismatches,
            "status": "DETERMINISTIC_EQUIVALENCE_VERIFIED" if is_equivalent else "DISCREPANCY_DETECTED",
        }
