"""
Research Factory — Controlled Hypothesis Generator (Phase 9)
============================================================
Generates reproducible quantitative hypotheses by combining existing canonical
strategies, registered factors, and market regimes under strict search-space limits.
"""

import time
import logging
from typing import Dict, Any, List, Optional

from backend.app.research_factory.models import (
    HypothesisCategory,
    HypothesisStatus,
    ResearchHypothesis,
    RejectionReason,
)

logger = logging.getLogger(__name__)

# Search Space Limits to prevent combinatorial explosion and P-Hacking
MAX_HYPOTHESIS_COMBINATIONS_BATCH = 50
MAX_UNIVERSE_SYMBOLS = 10


class HypothesisGenerator:
    """
    Controlled generator synthesizing quantitative hypotheses from verified components.
    """

    @classmethod
    def get_canonical_templates(cls) -> List[ResearchHypothesis]:
        """
        Returns pre-defined canonical research hypotheses.
        """
        now = int(time.time())
        return [
            ResearchHypothesis(
                hypothesis_id="HYP_QUALITY_TREND_01",
                name="Quality Trend Momentum (ROE x EMA)",
                version="1.0.0",
                description="Combines EMA 9/21 trend momentum with top-quartile sector ROE profitability.",
                category=HypothesisCategory.CONFLUENCE,
                technical_dependencies=["EMA_TREND_MOMENTUM"],
                fundamental_dependencies=["PROFITABILITY_ROE"],
                regime_filter="TRENDING_BULLISH",
                entry_conditions=["EMA_9 > EMA_21", "Sector Percentile ROE >= 70%"],
                exit_conditions=["EMA_9 < EMA_21 or Trailing Stop Hit"],
                universe=["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "TATAMOTORS.NS"],
                created_timestamp=now,
                status=HypothesisStatus.RESEARCH_CANDIDATE,
                k_tested=1,
            ),
            ResearchHypothesis(
                hypothesis_id="HYP_VALUE_MOMENTUM_01",
                name="Value Mean Reversion (P/E x RSI)",
                version="1.0.0",
                description="Oversold RSI pullbacks filtered for favorable valuation multiple P/E.",
                category=HypothesisCategory.CONFLUENCE,
                technical_dependencies=["RSI_MEAN_REVERSION"],
                fundamental_dependencies=["VALUATION_PE"],
                regime_filter="RANGE_BOUND",
                entry_conditions=["RSI_14 < 35", "Sector Percentile P/E <= 40%"],
                exit_conditions=["RSI_14 > 60 or Fixed Stop Hit"],
                universe=["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "TATAMOTORS.NS"],
                created_timestamp=now,
                status=HypothesisStatus.RESEARCH_CANDIDATE,
                k_tested=1,
            ),
            ResearchHypothesis(
                hypothesis_id="HYP_GROWTH_BREAKOUT_01",
                name="Growth Squeeze Breakout (Revenue x BB)",
                version="1.0.0",
                description="Bollinger Band squeeze breakout backed by YoY top-line revenue expansion.",
                category=HypothesisCategory.CONFLUENCE,
                technical_dependencies=["BB_SQUEEZE_BREAKOUT"],
                fundamental_dependencies=["GROWTH_REVENUE_YOY"],
                regime_filter="TRENDING_BULLISH",
                entry_conditions=["BB Bandwidth Squeeze & Close > Upper BB", "YoY Revenue Growth >= 15%"],
                exit_conditions=["Close < Middle BB"],
                universe=["RELIANCE.NS", "TCS.NS", "INFY.NS", "TATAMOTORS.NS"],
                created_timestamp=now,
                status=HypothesisStatus.VALIDATION_REQUIRED,
                k_tested=1,
            ),
            ResearchHypothesis(
                hypothesis_id="HYP_FCF_QUALITY_TREND_01",
                name="Cash Flow Quality Trend (FCF Conversion x VWAP)",
                version="1.0.0",
                description="Trend continuation above VWAP supported by >70% free cash flow conversion.",
                category=HypothesisCategory.CONFLUENCE,
                technical_dependencies=["VWAP_PULLBACK"],
                fundamental_dependencies=["CASHFLOW_FCF_CONVERSION"],
                regime_filter="TRENDING_BULLISH",
                entry_conditions=["Price > VWAP Pullback", "FCF Conversion Rate >= 70%"],
                exit_conditions=["Price < VWAP - 1 ATR"],
                universe=["TCS.NS", "INFY.NS", "RELIANCE.NS"],
                created_timestamp=now,
                status=HypothesisStatus.RESEARCH_CANDIDATE,
                k_tested=1,
            ),
            ResearchHypothesis(
                hypothesis_id="HYP_OVERFIT_MOMENTUM_99",
                name="High-Frequency Mean Reversion Scalper (K=45 Sweep)",
                version="1.0.0",
                description="Overfit RSI scalper generated via 45-parameter sweep without OOS holdout.",
                category=HypothesisCategory.TECHNICAL,
                technical_dependencies=["RSI_MEAN_REVERSION"],
                fundamental_dependencies=[],
                regime_filter="RANGE_BOUND",
                entry_conditions=["RSI_7 < 20 on 5m candles"],
                exit_conditions=["RSI_7 > 50 or Stop Hit"],
                universe=["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "TATAMOTORS.NS"],
                created_timestamp=now,
                status=HypothesisStatus.REJECTED,
                rejection_reasons=[
                    RejectionReason.OOS_FAILURE,
                    RejectionReason.HIGH_COST_DRAG,
                    RejectionReason.MULTIPLE_TESTING_RISK,
                    RejectionReason.ISOLATED_PEAK,
                    RejectionReason.SYMBOL_DEPENDENT,
                ],
                rejection_notes="Severe OOS collapse (-2.4% vs 38.2% IS), 78.8% cost drag, and K=45 p-hacking.",
                k_tested=45,
            ),
        ]

    @classmethod
    def generate_custom_hypothesis(
        cls,
        name: str,
        technical_strategy_id: str,
        fundamental_factor_id: Optional[str] = None,
        regime_filter: Optional[str] = None,
        universe: Optional[List[str]] = None,
        timeframe: str = "1D",
        k_batch_size: int = 1,
    ) -> ResearchHypothesis:
        """
        Generates a bounded quantitative hypothesis contract.
        """
        if k_batch_size > MAX_HYPOTHESIS_COMBINATIONS_BATCH:
            raise ValueError(f"Batch size {k_batch_size} exceeds maximum limit of {MAX_HYPOTHESIS_COMBINATIONS_BATCH}.")

        syms = (universe or ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "TATAMOTORS.NS"])[:MAX_UNIVERSE_SYMBOLS]
        now = int(time.time())
        hyp_id = f"HYP_{technical_strategy_id}_{fundamental_factor_id or 'TECH'}_{now}"

        fund_deps = [fundamental_factor_id] if fundamental_factor_id else []
        cat = HypothesisCategory.CONFLUENCE if fundamental_factor_id else HypothesisCategory.TECHNICAL

        return ResearchHypothesis(
            hypothesis_id=hyp_id,
            name=name,
            version="1.0.0",
            description=f"Composite research hypothesis for {name}.",
            category=cat,
            technical_dependencies=[technical_strategy_id],
            fundamental_dependencies=fund_deps,
            regime_filter=regime_filter,
            entry_conditions=[f"Technical {technical_strategy_id} ACTIVE", f"Factor {fundamental_factor_id} favorable"] if fundamental_factor_id else [f"Technical {technical_strategy_id} ACTIVE"],
            exit_conditions=["Strategy invalidation or stop target reached"],
            timeframe=timeframe,
            universe=syms,
            created_timestamp=now,
            status=HypothesisStatus.RESEARCHING,
            k_tested=k_batch_size,
        )
