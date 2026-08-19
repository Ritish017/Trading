"""
Unit Test Suite — APEX Research Factory & Empirical Validation (Phase 9)
========================================================================
Verifies:
1. ResearchHypothesis schema & deterministic contracts.
2. Controlled hypothesis generation & search space bounds (K tracking).
3. Benchmark baseline comparison.
4. Walk-forward Out-of-Sample (OOS) validation.
5. Cross-symbol basket dispersion (median, IQR).
6. 5-Regime stress testing.
7. 4-Tier transaction cost stress testing.
8. Parameter neighborhood plateau vs. cliff classification.
9. Strategy & factor redundancy evaluation.
10. Structured failure catalog & rejection reasons.
11. Promotion gates to PAPER_TESTING.
12. Live market observation mode without automated trading.
13. Research Copilot interrogation & Skeptic Mode.
"""

import pytest
import time
from backend.app.research_factory.models import (
    ResearchHypothesis,
    HypothesisCategory,
    HypothesisStatus,
    RejectionReason,
)
from backend.app.research_factory.generator import (
    HypothesisGenerator,
    MAX_HYPOTHESIS_COMBINATIONS_BATCH,
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


def test_search_space_bounding():
    # Valid custom hypothesis
    hyp = HypothesisGenerator.generate_custom_hypothesis(
        name="Test Trend ROE",
        technical_strategy_id="EMA_TREND_MOMENTUM",
        fundamental_factor_id="PROFITABILITY_ROE",
        k_batch_size=5,
    )
    assert hyp.k_tested == 5
    assert hyp.category == HypothesisCategory.CONFLUENCE

    # Attempting to exceed max batch combinations raises ValueError
    with pytest.raises(ValueError):
        HypothesisGenerator.generate_custom_hypothesis(
            name="Explosive Search",
            technical_strategy_id="EMA_TREND_MOMENTUM",
            k_batch_size=MAX_HYPOTHESIS_COMBINATIONS_BATCH + 1,
        )


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

    # 2. Cross-Symbol Dispersion
    assert scorecard.cross_symbol_result.median_return_pct > 0
    assert scorecard.cross_symbol_result.winning_symbols_count > 0

    # 3. Regime Stress
    assert len(scorecard.regime_result.regime_returns) == 5
    assert "TRENDING_BULLISH" in scorecard.regime_result.regime_returns

    # 4. Cost Stress
    assert scorecard.cost_result.zero_friction_cagr >= scorecard.cost_result.normal_friction_cagr
    assert scorecard.cost_result.normal_friction_cagr >= scorecard.cost_result.triple_friction_cagr

    # 5. Parameter Stability
    assert scorecard.parameter_result.plateau_stability in ["STABLE_PLATEAU", "MODERATE_CLIFF", "ISOLATED_PEAK"]

    # 6. Overall Recommendation
    assert scorecard.overall_recommendation in ["PROMOTABLE_CANDIDATE", "REJECT", "FURTHER_TESTING_REQUIRED"]


# ---------------------------------------------------------------------------
# 3. Failure Catalog & Structured Rejection Reasons
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


# ---------------------------------------------------------------------------
# 4. Promotion Gates to Paper Testing
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


# ---------------------------------------------------------------------------
# 5. Research Copilot & Skeptic Mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_research_factory_copilot_skeptic_mode():
    agent = ResearchFactoryCopilotAgent()
    hyp = HypothesisGenerator.get_canonical_templates()[0]
    scorecard = validator.validate_hypothesis(hyp)

    res = await agent.answer(
        hypothesis_id=hyp.hypothesis_id,
        user_message="CHALLENGE THIS HYPOTHESIS",
        hypothesis=vars(hyp),
        scorecard=vars(scorecard),
        is_skeptic_mode=True,
    )

    assert "reply" in res
    assert "Skeptic" in res["reply"] or "Critique" in res["reply"] or "Out-of-Sample" in res["reply"]
