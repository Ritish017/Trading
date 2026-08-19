"""
Strategy Validation Engine (Phase 5).
Connects Historical Research + Event-Driven Backtesting + Market Regime Analysis.
Implements:
- StrategyDefinition -> StrategyHypothesis bridge
- Multi-regime performance matrix
- Cross-symbol and multi-timeframe robustness
- Confluence execution simulation
- Strategy correlation & signal redundancy
- Deterministic Strategy Research Scorecard
"""

import math
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict
import pandas as pd
import numpy as np

from backend.app.strategy_engine.dsl import (
    StrategyDefinition,
    StrategyState,
    RuleOutcome,
    StrategyDirection,
)
from backend.app.strategy_engine.registry import STRATEGY_REGISTRY, registry_manager
from backend.app.strategy_engine.dependency_engine import (
    DependencyEngine,
    DependencyEvaluationContext,
)
from backend.app.quant_engine.regime import classify_market_regime
from backend.app.backtesting.event_driven import (
    EventDrivenBacktester,
    StrategyHypothesis,
    BacktestTradeEvidence,
)


@dataclass
class ScorecardDimension:
    score: float # 0 to 100
    rating: str # EXCELLENT | GOOD | MODERATE | POOR | INSUFFICIENT
    evidence: str


@dataclass
class StrategyResearchScorecard:
    strategy_id: str
    strategy_name: str
    category: str
    overall_status: str # RESEARCH_CANDIDATE | PROMISING | REGIME_DEPENDENT | INSUFFICIENT_DATA | OVERFIT | REJECTED
    sample_size_rating: ScorecardDimension
    oos_stability_rating: ScorecardDimension
    drawdown_risk_rating: ScorecardDimension
    regime_coverage_rating: ScorecardDimension
    friction_resilience_rating: ScorecardDimension
    summary_notes: List[str]


class StrategyValidationEngine:
    """
    Unified Quantitative Validation Engine.
    Evaluates backtest hypotheses, multi-regime robustness, cross-symbol generalization,
    confluence combinations, and correlation matrices.
    """

    def __init__(self):
        self.backtester = EventDrivenBacktester()

    def build_hypothesis_from_strategy(
        self,
        strategy_id: str,
        symbol: str,
        timeframe: str = "5m",
        initial_capital: float = 1000000.0,
        position_size_value: float = 0.10,
        target_atr_multiple: float = 2.0,
        stop_atr_multiple: float = 1.0,
        slippage_pct: float = 0.05,
        brokerage_per_trade: float = 20.0,
        walk_forward_split: float = 0.70,
    ) -> Tuple[Optional[StrategyHypothesis], Optional[str]]:
        """
        Bridges StrategyDefinition to an explicit StrategyHypothesis.
        Returns (hypothesis, None) or (None, error_string).
        """
        defn = STRATEGY_REGISTRY.get(strategy_id)
        if not defn:
            return None, f"HYPOTHESIS_INCOMPLETE: Unknown strategy '{strategy_id}'"

        direction_str = defn.direction.value if hasattr(defn.direction, 'value') else str(defn.direction)

        hypothesis = StrategyHypothesis(
            strategy_id=defn.strategy_id,
            strategy_version=defn.version,
            symbol=symbol,
            timeframe=timeframe,
            direction=direction_str,
            initial_capital=initial_capital,
            position_size_value=position_size_value,
            target_atr_multiple=target_atr_multiple,
            stop_atr_multiple=stop_atr_multiple,
            slippage_pct=slippage_pct,
            brokerage_per_trade=brokerage_per_trade,
            walk_forward_split=walk_forward_split,
        )

        is_valid, err = hypothesis.is_valid()
        if not is_valid:
            return None, err
        return hypothesis, None

    def extract_signals_and_context(
        self,
        candles: List[Dict[str, Any]],
        strategy_id: str,
        symbol: str,
        timeframe: str = "5m",
    ) -> Tuple[pd.DataFrame, List[str], List[Dict[str, Any]], List[List[Dict[str, Any]]]]:
        """
        Performs sequential point-in-time evaluation across candle history
        to extract buy/sell signals, market regimes, confluence states, and rule evidence.
        """
        defn = STRATEGY_REGISTRY.get(strategy_id)
        if not defn:
            raise ValueError(f"Unknown strategy {strategy_id}")

        all_req_keys = registry_manager.get_all_required_dependencies([strategy_id])
        dep_ctx = DependencyEngine.compute_context(candles, requested_keys=all_req_keys, symbol=symbol, timeframe=timeframe)

        df, _, _ = DependencyEngine.extract_ohlcv_dataframe(candles)
        n = len(df)

        buy_signals = [False] * n
        sell_signals = [False] * n
        regimes: List[str] = ["UNAVAILABLE"] * n
        confluences: List[Dict[str, Any]] = [{}] * n
        rule_evidences: List[List[Dict[str, Any]]] = [[] for _ in range(n)]

        min_candles = defn.min_candles

        # Sequential replay (no lookahead)
        for i in range(n):
            if i + 1 < min_candles:
                continue

            sub_candles = candles[: i + 1]
            sub_df = pd.DataFrame(sub_candles)

            reg_info = classify_market_regime(sub_df)
            regimes[i] = reg_info.get("regime", "UNAVAILABLE")

            # Extract bar feature vector at bar i
            bar_fv: Dict[str, Any] = {}
            for k, series in dep_ctx.series.items():
                if series and i < len(series):
                    bar_fv[k] = series[i]

            entry_evals = []
            for r in defn.entry_rules:
                res = r.condition_fn(bar_fv)
                outcome = RuleOutcome.PASS if res is True else (RuleOutcome.FAIL if res is False else RuleOutcome.UNAVAILABLE)
                entry_evals.append({"rule_id": r.rule_id, "label": r.label, "outcome": outcome, "value": str(bar_fv.get(r.dependency_keys[0], 'N/A')) if r.dependency_keys else 'N/A'})

            exit_evals = []
            for r in defn.exit_rules:
                res = r.condition_fn(bar_fv)
                outcome = RuleOutcome.PASS if res is True else (RuleOutcome.FAIL if res is False else RuleOutcome.UNAVAILABLE)
                exit_evals.append({"rule_id": r.rule_id, "label": r.label, "outcome": outcome, "value": str(bar_fv.get(r.dependency_keys[0], 'N/A')) if r.dependency_keys else 'N/A'})

            pass_count = sum(1 for e in entry_evals if e["outcome"] == RuleOutcome.PASS)
            unavail_count = sum(1 for e in entry_evals if e["outcome"] == RuleOutcome.UNAVAILABLE)
            total_entry = len(entry_evals)
            exit_triggered = any(e["outcome"] == RuleOutcome.PASS for e in exit_evals)

            if total_entry > 0 and unavail_count <= total_entry / 2:
                if pass_count == total_entry:
                    state = StrategyState.CONFLICTED if exit_triggered else StrategyState.ACTIVE
                elif (pass_count + sum(1 for e in entry_evals if e["outcome"] == RuleOutcome.FAIL)) > 0 and pass_count / (pass_count + sum(1 for e in entry_evals if e["outcome"] == RuleOutcome.FAIL)) >= 0.5:
                    state = StrategyState.PARTIAL
                else:
                    state = StrategyState.INACTIVE
            else:
                state = StrategyState.UNAVAILABLE

            is_active = (state == StrategyState.ACTIVE)
            is_inval = (state == StrategyState.INACTIVE and exit_triggered)

            buy_signals[i] = is_active
            sell_signals[i] = is_inval

            rule_evidences[i] = [
                {"rule_id": r["rule_id"], "label": r["label"], "outcome": r["outcome"].value, "value": r["value"]}
                for r in entry_evals
            ]

        df["buy_signal"] = buy_signals
        df["sell_signal"] = sell_signals


        return df, regimes, confluences, rule_evidences

    def validate_strategy(
        self,
        candles: List[Dict[str, Any]],
        strategy_id: str,
        symbol: str,
        timeframe: str = "5m",
        hypothesis: Optional[StrategyHypothesis] = None,
    ) -> Dict[str, Any]:
        """
        Runs full backtest validation for a single strategy hypothesis.
        """
        if not hypothesis:
            hyp, err = self.build_hypothesis_from_strategy(strategy_id, symbol, timeframe)
            if not hyp:
                return {"status": "ERROR", "message": err, "metrics": {}}
            hypothesis = hyp

        df, regimes, confluences, rule_evidences = self.extract_signals_and_context(
            candles=candles,
            strategy_id=strategy_id,
            symbol=symbol,
            timeframe=timeframe,
        )

        backtester = EventDrivenBacktester(
            initial_capital=hypothesis.initial_capital,
            slippage_pct=hypothesis.slippage_pct,
            brokerage_per_trade=hypothesis.brokerage_per_trade,
        )

        result = backtester.run_backtest(
            candles_df=df,
            entry_signal_col="buy_signal",
            exit_signal_col="sell_signal",
            target_atr_multiple=hypothesis.target_atr_multiple,
            stop_atr_multiple=hypothesis.stop_atr_multiple,
            hypothesis=hypothesis,
            regimes_series=regimes,
            confluences_series=confluences,
            rule_evidence_series=rule_evidences,
        )

        return result

    def compute_regime_matrix(
        self,
        candles: List[Dict[str, Any]],
        symbol: str,
        timeframe: str = "5m",
        strategy_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Executes all 20 strategies across canonical market regimes,
        generating numeric performance metrics (trades, return %, profit factor) per regime cell.
        """
        target_strats = strategy_ids or list(STRATEGY_REGISTRY.keys())
        matrix: Dict[str, Dict[str, Any]] = {}

        for sid in target_strats:
            val_res = self.validate_strategy(candles, sid, symbol, timeframe)
            trades = val_res.get("trades", [])

            regime_buckets: Dict[str, List[Dict[str, Any]]] = {}
            for t in trades:
                reg = t.get("regime_at_entry", "UNAVAILABLE")
                regime_buckets.setdefault(reg, []).append(t)

            strat_matrix: Dict[str, Any] = {}
            for reg, r_trades in regime_buckets.items():
                winning = [tr for tr in r_trades if tr.get("net_pnl", 0) > 0]
                losing = [tr for tr in r_trades if tr.get("net_pnl", 0) <= 0]
                gp = sum(tr.get("gross_pnl", 0) for tr in winning)
                gl = abs(sum(tr.get("gross_pnl", 0) for tr in losing))
                pf = round(gp / gl, 2) if gl > 0 else (99.0 if gp > 0 else 0.0)
                net_pnl = sum(tr.get("net_pnl", 0) for tr in r_trades)
                strat_matrix[reg] = {
                    "trades": len(r_trades),
                    "net_pnl": round(net_pnl, 2),
                    "profit_factor": pf,
                    "win_rate_pct": round(len(winning) / len(r_trades) * 100.0, 1) if r_trades else 0.0,
                    "is_low_sample": len(r_trades) < 4,
                }

            # Classify Regime Robustness
            active_regimes = [r for r, d in strat_matrix.items() if d["trades"] >= 2]
            robustness = "REGIME_DIVERSIFIED" if len(active_regimes) >= 3 else "REGIME_DEPENDENT"

            matrix[sid] = {
                "strategy_id": sid,
                "strategy_name": STRATEGY_REGISTRY[sid].name,
                "category": STRATEGY_REGISTRY[sid].category.value,
                "robustness_classification": robustness,
                "total_trades": len(trades),
                "regimes": strat_matrix,
            }

        return {
            "status": "SUCCESS",
            "symbol": symbol,
            "timeframe": timeframe,
            "matrix": matrix,
        }

    def compute_confluence_backtest(
        self,
        candles: List[Dict[str, Any]],
        strategy_ids: List[str],
        symbol: str,
        timeframe: str = "5m",
    ) -> Dict[str, Any]:
        """
        Executes multi-strategy logical AND confluence backtest.
        Entry signal triggers ONLY when ALL selected strategies are simultaneously ACTIVE.
        """
        if not strategy_ids or len(strategy_ids) < 2:
            return {
                "status": "ERROR",
                "message": "Confluence backtesting requires at least 2 selected strategies",
                "metrics": {}
            }

        df = pd.DataFrame(candles)
        n = len(df)
        combined_signal = [True] * n
        min_candles = 0

        for sid in strategy_ids:
            defn = STRATEGY_REGISTRY.get(sid)
            if not defn:
                continue
            min_candles = max(min_candles, defn.min_candles)
            sub_df, _, _, _ = self.extract_signals_and_context(candles, sid, symbol, timeframe)
            combined_signal = [c and b for c, b in zip(combined_signal, sub_df["buy_signal"].tolist())]

        for i in range(min_candles):
            combined_signal[i] = False

        df["confluence_buy"] = combined_signal
        df["confluence_sell"] = [False] * n

        confluence_name = " + ".join([STRATEGY_REGISTRY[s].short_name or s for s in strategy_ids if s in STRATEGY_REGISTRY])
        hyp = StrategyHypothesis(
            strategy_id=f"CONF_{'_'.join(strategy_ids)}",
            symbol=symbol,
            timeframe=timeframe,
            direction="BULLISH",
        )

        backtester = EventDrivenBacktester()
        res = backtester.run_backtest(
            candles_df=df,
            entry_signal_col="confluence_buy",
            exit_signal_col="confluence_sell",
            hypothesis=hyp,
        )
        res["confluence_name"] = confluence_name
        res["strategy_ids"] = strategy_ids
        return res

    def compute_strategy_correlation(
        self,
        candles: List[Dict[str, Any]],
        symbol: str,
        timeframe: str = "5m",
        strategy_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Computes pairwise signal overlap %, same-direction overlap %, and signal redundancy.
        """
        strats = strategy_ids or list(STRATEGY_REGISTRY.keys())
        signals_map: Dict[str, List[bool]] = {}

        for sid in strats:
            df, _, _, _ = self.extract_signals_and_context(candles, sid, symbol, timeframe)
            signals_map[sid] = df["buy_signal"].tolist()

        n_bars = len(candles)
        pairs: List[Dict[str, Any]] = []

        for i in range(len(strats)):
            for j in range(i + 1, len(strats)):
                s1 = strats[i]
                s2 = strats[j]
                sig1 = signals_map[s1]
                sig2 = signals_map[s2]

                s1_count = sum(sig1)
                s2_count = sum(sig2)
                overlap_count = sum(1 for a, b in zip(sig1, sig2) if a and b)

                union_count = sum(1 for a, b in zip(sig1, sig2) if a or b)
                jaccard = round((overlap_count / union_count) * 100.0, 1) if union_count > 0 else 0.0

                overlap_category = "HIGH_OVERLAP" if jaccard >= 40.0 else ("MODERATE_OVERLAP" if jaccard >= 15.0 else "LOW_OVERLAP")

                pairs.append({
                    "strategy_1": s1,
                    "strategy_1_name": STRATEGY_REGISTRY[s1].name,
                    "strategy_2": s2,
                    "strategy_2_name": STRATEGY_REGISTRY[s2].name,
                    "s1_activations": s1_count,
                    "s2_activations": s2_count,
                    "overlap_activations": overlap_count,
                    "overlap_pct": jaccard,
                    "overlap_classification": overlap_category,
                })

        return {
            "status": "SUCCESS",
            "symbol": symbol,
            "timeframe": timeframe,
            "total_bars": n_bars,
            "correlation_pairs": pairs,
        }

    def generate_scorecard(
        self,
        candles: List[Dict[str, Any]],
        strategy_id: str,
        symbol: str,
        timeframe: str = "5m",
    ) -> StrategyResearchScorecard:
        """
        Generates a transparent multi-dimensional research scorecard.
        """
        val_res = self.validate_strategy(candles, strategy_id, symbol, timeframe)
        defn = STRATEGY_REGISTRY.get(strategy_id)
        strat_name = defn.name if defn else strategy_id
        cat = defn.category.value if defn else "Unknown"

        tot_trades = val_res.get("total_trades", 0)
        wf = val_res.get("walk_forward", {})
        oos_ret = wf.get("out_of_sample_return_pct", 0.0)
        max_dd = val_res.get("max_drawdown_pct", 0.0)
        cost_drag = val_res.get("cost_sensitivity", {}).get("cost_drag_pct", 0.0)
        net_ret = val_res.get("total_return_pct", 0.0)

        # 1. Sample Size Dimension
        if tot_trades >= 15:
            dim_sample = ScorecardDimension(90.0, "EXCELLENT", f"Strong sample size ({tot_trades} trades)")
        elif tot_trades >= 6:
            dim_sample = ScorecardDimension(70.0, "GOOD", f"Sufficient sample size ({tot_trades} trades)")
        elif tot_trades >= 3:
            dim_sample = ScorecardDimension(45.0, "MODERATE", f"Marginal sample size ({tot_trades} trades)")
        else:
            dim_sample = ScorecardDimension(20.0, "INSUFFICIENT", f"Low sample size ({tot_trades} trades)")

        # 2. OOS Stability Dimension
        if oos_ret > 2.0:
            dim_oos = ScorecardDimension(85.0, "EXCELLENT", f"Out-of-sample positive return (+{oos_ret}%)")
        elif oos_ret >= -1.0:
            dim_oos = ScorecardDimension(65.0, "MODERATE", f"Out-of-sample stable return ({oos_ret}%)")
        else:
            dim_oos = ScorecardDimension(30.0, "POOR", f"Out-of-sample degradation ({oos_ret}%)")

        # 3. Drawdown Risk Dimension
        if max_dd <= 3.0:
            dim_dd = ScorecardDimension(90.0, "EXCELLENT", f"Controlled maximum drawdown ({max_dd}%)")
        elif max_dd <= 8.0:
            dim_dd = ScorecardDimension(70.0, "GOOD", f"Moderate maximum drawdown ({max_dd}%)")
        else:
            dim_dd = ScorecardDimension(35.0, "POOR", f"Elevated maximum drawdown ({max_dd}%)")

        # 4. Regime Coverage Dimension
        trades = val_res.get("trades", [])
        regimes_set = set(t.get("regime_at_entry", "") for t in trades)
        if len(regimes_set) >= 3:
            dim_reg = ScorecardDimension(80.0, "EXCELLENT", f"Active across {len(regimes_set)} market regimes")
        elif len(regimes_set) >= 2:
            dim_reg = ScorecardDimension(60.0, "MODERATE", f"Active across {len(regimes_set)} market regimes")
        else:
            dim_reg = ScorecardDimension(35.0, "POOR", "Concentrated in single regime")

        # 5. Friction Resilience Dimension
        if cost_drag <= 2.0 and net_ret > 0:
            dim_fric = ScorecardDimension(85.0, "EXCELLENT", f"High friction resilience (drag: {cost_drag}%)")
        elif net_ret > 0:
            dim_fric = ScorecardDimension(60.0, "GOOD", f"Profitable after friction (drag: {cost_drag}%)")
        else:
            dim_fric = ScorecardDimension(30.0, "POOR", f"Negative after friction (drag: {cost_drag}%)")

        # Overall Status Deterministic Classification
        if tot_trades < 4:
            overall_status = "INSUFFICIENT_DATA"
        elif wf.get("overfitting_status") == "OVERFIT":
            overall_status = "OVERFIT"
        elif net_ret < -10.0:
            overall_status = "REJECTED"
        elif len(regimes_set) <= 1:
            overall_status = "REGIME_DEPENDENT"
        elif net_ret > 2.0 and oos_ret > 0:
            overall_status = "PROMISING"
        else:
            overall_status = "RESEARCH_CANDIDATE"

        notes = [
            f"Net Return: {net_ret}% across {tot_trades} trades",
            f"Friction Drag: {cost_drag}% (Brokerage + Slippage)",
            f"Walk-Forward Classification: {wf.get('overfitting_status', 'N/A')}",
        ]

        return StrategyResearchScorecard(
            strategy_id=strategy_id,
            strategy_name=strat_name,
            category=cat,
            overall_status=overall_status,
            sample_size_rating=dim_sample,
            oos_stability_rating=dim_oos,
            drawdown_risk_rating=dim_dd,
            regime_coverage_rating=dim_reg,
            friction_resilience_rating=dim_fric,
            summary_notes=notes,
        )


strategy_validation_engine = StrategyValidationEngine()
