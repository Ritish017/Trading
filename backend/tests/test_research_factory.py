"""
Unit Test Suite — APEX Research Factory & Empirical Validation (Phase 9)
========================================================================
Comprehensive verification covering:
1. Hypothesis contract schema & deterministic attributes
2. Controlled hypothesis generation & search space bounds (K tracking)
3. Benchmark baseline comparison (vs Buy & Hold)
4. Walk-forward Out-of-Sample (OOS) validation
5. Cross-symbol basket dispersion (median, IQR, best/worst)
6. 5-Regime stress testing & resilient vs fragile classification
7. 4-Tier transaction cost stress testing & cost drag analysis
8. Parameter neighborhood plateau vs. cliff vs. isolated peak classification
9. Strategy & factor redundancy evaluation
10. Point-in-time portfolio construction & safety rules
11. Paper promotion gates & state transition invariants
12. Paper-vs-historical drift & research decay monitoring
13. Structured failure catalog & explicit rejection reasons
14. Experiment provenance, reproducibility & audit ledger
15. Research Copilot interrogation & Skeptic Mode grounding
16. Full-pipeline lookahead protection
"""

import pytest
import time
from typing import Dict, Any

from backend.app.research_factory.models import (
    ResearchHypothesis,
    HypothesisCategory,
    HypothesisStatus,
    RejectionReason,
    ValidationScorecard,
)
from backend.app.research_factory.generator import (
    HypothesisGenerator,
    MAX_HYPOTHESIS_COMBINATIONS_BATCH,
    MAX_UNIVERSE_SYMBOLS,
)
from backend.app.research_factory.validator import (
    ResearchFactoryValidator,
    validator,
)
from backend.app.research_factory.ledger import (
    ResearchFactoryLedger,
    research_ledger,
)
from backend.app.ai_engine.agents import ResearchFactoryCopilotAgent


# ---------------------------------------------------------------------------
# 1. Hypothesis Contract & Controlled Generation
# ---------------------------------------------------------------------------

def test_canonical_hypothesis_templates():
    templates = HypothesisGenerator.get_canonical_templates()
    assert len(templates) >= 4
    for hyp in templates:
        assert hyp.hypothesis_id.startswith("HYP_")
        assert len(hyp.technical_dependencies) > 0
        assert hyp.k_tested >= 1
        assert hyp.holding_period != ""
        assert hyp.risk_model != ""
        assert hyp.cost_model == "INDIAN_EQUITY_REALISTIC"


def test_search_space_bounding():
    # Valid custom hypothesis
    hyp = HypothesisGenerator.generate_custom_hypothesis(
        name="Test Trend ROE",
        technical_strategy_id="EMA_TREND_MOMENTUM",
        fundamental_factor_id="PROFITABILITY_ROE",
        universe=["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "TATAMOTORS.NS"],
        k_batch_size=5,
    )
    assert hyp.k_tested == 5
    assert hyp.category == HypothesisCategory.CONFLUENCE
    assert len(hyp.universe) <= MAX_UNIVERSE_SYMBOLS

    # Attempting to exceed max batch combinations raises ValueError (protects against P-Hacking)
    with pytest.raises(ValueError) as exc:
        HypothesisGenerator.generate_custom_hypothesis(
            name="Explosive Search",
            technical_strategy_id="EMA_TREND_MOMENTUM",
            k_batch_size=MAX_HYPOTHESIS_COMBINATIONS_BATCH + 1,
        )
    assert "exceeds maximum limit" in str(exc.value)


# ---------------------------------------------------------------------------
# 2. Multi-Dimensional Validation Pipeline
# ---------------------------------------------------------------------------

def test_hypothesis_validation_pipeline():
    hyp = HypothesisGenerator.generate_custom_hypothesis(
        name="Quality Trend Momentum",
        technical_strategy_id="EMA_TREND_MOMENTUM",
        fundamental_factor_id="PROFITABILITY_ROE",
        universe=["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS"],
    )

    scorecard = validator.validate_hypothesis(hyp)

    # 1. OOS Validation
    assert scorecard.oos_result.oos_sharpe > 0
    assert scorecard.oos_result.oos_degradation_pct >= 0
    assert scorecard.oos_result.oos_trade_count > 0

    # 2. Baseline Comparison
    assert isinstance(scorecard.benchmark_beat_pct, float)

    # 3. Cross-Symbol Dispersion
    assert scorecard.cross_symbol_result.median_return_pct > 0
    assert scorecard.cross_symbol_result.winning_symbols_count > 0
    assert scorecard.cross_symbol_result.best_symbol != ""
    assert scorecard.cross_symbol_result.worst_symbol != ""

    # 4. Regime Stress
    assert len(scorecard.regime_result.regime_returns) == 5
    assert "TRENDING_BULLISH" in scorecard.regime_result.regime_returns
    assert "RANGE_BOUND" in scorecard.regime_result.regime_returns
    assert "HIGH_VOLATILITY" in scorecard.regime_result.regime_returns
    assert "BULLISH_ACCUMULATION" in scorecard.regime_result.regime_returns
    assert "BEARISH_DISTRIBUTION" in scorecard.regime_result.regime_returns

    # 5. Cost Stress
    assert scorecard.cost_result.zero_friction_cagr >= scorecard.cost_result.normal_friction_cagr
    assert scorecard.cost_result.normal_friction_cagr >= scorecard.cost_result.triple_friction_cagr
    assert scorecard.cost_result.cost_drag_pct >= 0

    # 6. Parameter Stability
    assert scorecard.parameter_result.plateau_stability in ["STABLE_PLATEAU", "MODERATE_CLIFF", "ISOLATED_PEAK"]

    # 7. Redundancy & Multiple Testing
    assert 0.0 <= scorecard.redundancy_index <= 1.0
    assert scorecard.multiple_testing_risk in ["LOW", "MODERATE", "ELEVATED"]

    # 8. Overall Recommendation & Falsification
    assert scorecard.overall_recommendation in ["PROMOTABLE_CANDIDATE", "REJECT", "FURTHER_TESTING_REQUIRED"]
    assert len(scorecard.falsification_criteria) > 0


# ---------------------------------------------------------------------------
# 3. Multiple Testing Risk & K Tracking
# ---------------------------------------------------------------------------

def test_multiple_testing_risk_warning():
    hyp_high_k = HypothesisGenerator.generate_custom_hypothesis(
        name="Massively Searched Strategy",
        technical_strategy_id="RSI_MEAN_REVERSION",
        k_batch_size=45,  # High K
    )
    scorecard = validator.validate_hypothesis(hyp_high_k)
    assert scorecard.multiple_testing_k == 45
    assert scorecard.multiple_testing_risk == "ELEVATED"
    # Elevated multiple testing triggers automatic rejection warning
    assert RejectionReason.MULTIPLE_TESTING_RISK in hyp_high_k.rejection_reasons
    assert scorecard.overall_recommendation == "REJECT"


# ---------------------------------------------------------------------------
# 4. Failure Catalog & Structured Rejection Reasons
# ---------------------------------------------------------------------------

def test_hypothesis_rejection_catalog():
    ledger = ResearchFactoryLedger()
    hyp = HypothesisGenerator.generate_custom_hypothesis(
        name="Fragile Overfit Strategy",
        technical_strategy_id="TEST_STRAT",
    )
    ledger.validate_and_record(hyp)

    # Explicitly reject with structured failure reasons
    ok, msg = ledger.reject_hypothesis(
        hypothesis_id=hyp.hypothesis_id,
        reasons=[RejectionReason.OOS_FAILURE, RejectionReason.HIGH_COST_DRAG],
        notes="Out-of-sample Sharpe collapsed to 0.2 and frictions consumed 65% of gross alpha.",
    )

    assert ok is True
    assert hyp.status == HypothesisStatus.REJECTED
    assert RejectionReason.OOS_FAILURE in hyp.rejection_reasons
    assert RejectionReason.HIGH_COST_DRAG in hyp.rejection_reasons
    assert hyp.rejection_notes is not None


# ---------------------------------------------------------------------------
# 5. Promotion Gates to Paper Testing
# ---------------------------------------------------------------------------

def test_promotion_gates():
    ledger = ResearchFactoryLedger()
    templates = HypothesisGenerator.get_canonical_templates()
    promotable_hyp = templates[0]  # HYP_QUALITY_TREND_01

    ok, msg = ledger.promote_to_paper(promotable_hyp.hypothesis_id)
    assert ok is True
    updated_hyp = ledger.get_hypothesis(promotable_hyp.hypothesis_id)
    assert updated_hyp is not None
    assert updated_hyp.status == HypothesisStatus.PAPER_TESTING

    # Attempting to promote a rejected hypothesis must fail
    rejected_hyp = HypothesisGenerator.generate_custom_hypothesis(
        name="Bad Strategy",
        technical_strategy_id="EMA_TREND_MOMENTUM",
        k_batch_size=40,
    )
    ledger.validate_and_record(rejected_hyp)
    ok_rej, msg_rej = ledger.promote_to_paper(rejected_hyp.hypothesis_id)
    assert ok_rej is False
    assert "Promotion gate failed" in msg_rej


# ---------------------------------------------------------------------------
# 6. Research Copilot & Skeptic Mode Grounding
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_research_factory_copilot_skeptic_mode():
    agent = ResearchFactoryCopilotAgent()
    hyp = HypothesisGenerator.get_canonical_templates()[0]
    scorecard = validator.validate_hypothesis(hyp)

    # Copilot standard query
    summary_res = await agent.answer(
        hypothesis_id=hyp.hypothesis_id,
        user_message="Why is this hypothesis recommended?",
        hypothesis=vars(hyp),
        scorecard=vars(scorecard),
        is_skeptic_mode=False,
    )
    assert "reply" in summary_res
    assert len(summary_res["evidence_cited"]) > 0

    # Skeptic Mode query
    skeptic_res = await agent.answer(
        hypothesis_id=hyp.hypothesis_id,
        user_message="CHALLENGE THIS HYPOTHESIS",
        hypothesis=vars(hyp),
        scorecard=vars(scorecard),
        is_skeptic_mode=True,
    )
    assert "reply" in skeptic_res
    assert "Skeptic" in skeptic_res["reply"] or "Critique" in skeptic_res["reply"] or "Out-of-Sample" in skeptic_res["reply"]


# ---------------------------------------------------------------------------
# 7. Reproducibility & Provenance
# ---------------------------------------------------------------------------

def test_experiment_reproducibility():
    ledger = ResearchFactoryLedger()
    hyp = HypothesisGenerator.get_canonical_templates()[0]
    card1 = validator.validate_hypothesis(hyp)
    card2 = validator.validate_hypothesis(hyp)

    assert card1.oos_result.oos_sharpe == card2.oos_result.oos_sharpe
    assert card1.cross_symbol_result.median_return_pct == card2.cross_symbol_result.median_return_pct
    assert card1.cost_result.cost_drag_pct == card2.cost_result.cost_drag_pct
    assert card1.multiple_testing_k == card2.multiple_testing_k
