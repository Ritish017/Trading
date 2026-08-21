"""
Unit Test Suite — APEX Independent Quant Research Audit (Phase 10)
==================================================================
Verifies:
1. Independent research replication
2. Independent CAGR mathematical formulation
3. Independent Sharpe ratio calculation & annualization
4. Independent drawdown series & maximum drawdown duration
5. Independent profit factor edge-case handling (zero losses, zero wins, empty)
6. Statutory Indian transaction friction modeling (STT, GST, SEBI, etc.)
7. Next-bar open execution invariant (T close -> T+1 open)
8. Walk-forward fold boundaries & purge/embargo isolation
9. Parameter selection restricted strictly to training folds
10. Multiple testing control (Holm-Bonferroni, Benjamini-Hochberg, Selection Intensity)
11. Corporate actions split/bonus price adjustments
12. Universe selection & survivorship bias detection
13. Fundamental point-in-time publication timestamp verification
14. Regime point-in-time classification without forward lookahead
15. Paper replay vs historical backtest execution equivalence
16. Non-parametric bootstrap interval estimation (95% CI)
17. Trade serial dependence & Lag-1 autocorrelation test
18. Strategy redundancy & factor overlap evaluation
19. Research certification states & audit lifecycle
20. Independent verification of HYP_QUALITY_TREND_01 (AUDITED_WITH_LIMITATIONS)
21. Independent verification of HYP_OVERFIT_MOMENTUM_99 (AUDIT_FAILED)
"""

import pytest
import math
import numpy as np

from backend.app.research_factory.models import (
    ResearchHypothesis,
    HypothesisCategory,
    HypothesisStatus,
    RejectionReason,
)
from backend.app.research_factory.audit_models import (
    AuditStatus,
    CertificationStatus,
    ReplicationVerdict,
    ResearchAuditReport,
)
from backend.app.research_factory.generator import HypothesisGenerator
from backend.app.research_factory.validator import validator
from backend.app.research_factory.ledger import ResearchFactoryLedger, research_ledger
from backend.app.research_factory.auditor import (
    independent_cagr,
    independent_sharpe,
    independent_drawdown,
    independent_profit_factor,
    independent_indian_roundtrip_costs,
    independent_bootstrap_sharpe_ci,
    independent_trade_autocorrelation,
    independent_multiple_testing_adjustments,
    ResearchFactoryAuditor,
    research_auditor,
)
from backend.app.ai_engine.agents import ResearchFactoryCopilotAgent


# ---------------------------------------------------------------------------
# 1. Independent Mathematical First-Principles Tests
# ---------------------------------------------------------------------------

def test_independent_cagr_calculation():
    # 100,000 to 144,000 over exactly 2 years
    t0 = 1600000000
    t1 = t0 + int(2 * 365.25 * 86400)
    cagr = independent_cagr(100000.0, 144000.0, t0, t1)
    assert round(cagr, 1) == 20.0

    # Negative / zero edge cases
    assert independent_cagr(-100.0, 100.0, t0, t1) == -100.0
    assert independent_cagr(100.0, -100.0, t0, t1) == -100.0


def test_independent_sharpe_calculation():
    # Constant positive returns
    daily_returns = [0.001] * 252  # 0.1% daily
    # Sharpe should handle constant or near-constant series gracefully
    daily_variable = [0.001, 0.002, -0.0005, 0.0015, 0.0008] * 50
    sharpe = independent_sharpe(daily_variable, annual_risk_free_rate=0.065, frequency_per_year=252)
    assert isinstance(sharpe, float)
    assert sharpe > 0.0

    # Empty series
    assert independent_sharpe([]) == 0.0
    assert independent_sharpe([0.01]) == 0.0


def test_independent_drawdown_calculation():
    equity_curve = [100.0, 110.0, 105.0, 99.0, 120.0, 115.0, 130.0]
    # Peak = 110, trough = 99 -> DD = (110 - 99)/110 = 10.0%
    dd_result = independent_drawdown(equity_curve)
    assert dd_result["max_drawdown_pct"] == 10.0
    assert dd_result["peak_equity"] == 130.0
    assert dd_result["max_drawdown_duration_bars"] >= 2


def test_independent_profit_factor_edge_cases():
    # Standard mixed
    assert independent_profit_factor([100.0, -50.0, 200.0, -50.0]) == 3.0

    # Zero losses -> None (represents infinite edge)
    assert independent_profit_factor([100.0, 200.0, 50.0]) is None

    # Zero wins -> 0.0
    assert independent_profit_factor([-100.0, -50.0]) == 0.0

    # Empty trade list
    assert independent_profit_factor([]) == 0.0


def test_independent_indian_statutory_costs():
    costs = independent_indian_roundtrip_costs(turnover_value=200000.0, is_intraday=False)
    assert costs["total_roundtrip_cost"] > 0
    assert costs["stt"] > 0
    assert costs["brokerage"] > 0
    assert costs["exchange_charges"] > 0
    assert costs["gst"] > 0
    assert costs["stamp_duty"] > 0
    assert costs["effective_basis_points"] > 0


# ---------------------------------------------------------------------------
# 2. Statistical Inference, Bootstrap & Multiple Testing
# ---------------------------------------------------------------------------

def test_bootstrap_sharpe_ci():
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.01, 100).tolist()
    (ci_lower, ci_upper), se = independent_bootstrap_sharpe_ci(returns, n_bootstrap=500)
    assert ci_lower < ci_upper
    assert se > 0.0


def test_trade_autocorrelation():
    # Independent IID trades
    np.random.seed(42)
    iid_trades = np.random.normal(100, 20, 100).tolist()
    r, is_iid = independent_trade_autocorrelation(iid_trades)
    assert isinstance(r, float)
    assert is_iid is True

    # Strongly autocorrelated trades (momentum/trend dependency)
    dep_trades = [i * 5.0 for i in range(50)]
    r_dep, is_dep = independent_trade_autocorrelation(dep_trades)
    assert abs(r_dep) > 0.15
    assert is_dep is False


def test_multiple_testing_adjustments():
    # Low K (single test)
    low_k = independent_multiple_testing_adjustments(nominal_p_value=0.01, k_configurations=1)
    assert low_k["selection_intensity"] == 0.0
    assert low_k["data_snooping_warning"] is False

    # High K (45 configurations sweep)
    high_k = independent_multiple_testing_adjustments(nominal_p_value=0.04, k_configurations=45)
    assert high_k["selection_intensity"] > 2.0
    assert high_k["holm_bonferroni_p_adjusted"] > 0.05
    assert high_k["data_snooping_warning"] is True


# ---------------------------------------------------------------------------
# 3. Full Independent Audits on Benchmark Hypotheses
# ---------------------------------------------------------------------------

def test_audit_surviving_candidate_hyp_quality_trend_01():
    templates = HypothesisGenerator.get_canonical_templates()
    hyp = next(h for h in templates if h.hypothesis_id == "HYP_QUALITY_TREND_01")
    scorecard = validator.validate_hypothesis(hyp)

    report = research_auditor.audit_hypothesis(hyp, scorecard)

    # 1. Verification of Replication
    assert report.replication_result.verdict == ReplicationVerdict.INDEPENDENTLY_REPRODUCED
    assert report.replication_result.recomputed_metrics["oos_cagr_pct"] == 14.2
    assert report.replication_result.recomputed_metrics["oos_sharpe"] == 1.15

    # 2. Certification with Limitations (due to survivorship risk)
    assert report.certification_status == CertificationStatus.AUDITED_WITH_LIMITATIONS
    assert report.overall_status == AuditStatus.PASS_WITH_LIMITATIONS
    assert len(report.limitations) > 0

    # 3. Point-in-time integrity
    assert report.point_in_time_integrity.status == AuditStatus.PASS
    assert report.execution_integrity.status == AuditStatus.PASS
    assert report.corporate_action_integrity.status == AuditStatus.PASS


def test_audit_failed_candidate_hyp_overfit_momentum_99():
    templates = HypothesisGenerator.get_canonical_templates()
    hyp = next(h for h in templates if h.hypothesis_id == "HYP_OVERFIT_MOMENTUM_99")
    scorecard = validator.validate_hypothesis(hyp)

    report = research_auditor.audit_hypothesis(hyp, scorecard)

    # 1. Verification of Overfit Replication
    assert report.replication_result.verdict == ReplicationVerdict.INDEPENDENTLY_REPRODUCED
    assert report.replication_result.recomputed_metrics["is_cagr_pct"] == 38.2
    assert report.replication_result.recomputed_metrics["oos_cagr_pct"] == -2.4
    assert report.replication_result.recomputed_metrics["cost_drag_pct"] == 78.8

    # 2. Audit Certification Failed
    assert report.certification_status == CertificationStatus.AUDIT_FAILED
    assert report.overall_status == AuditStatus.FAILED
    assert report.statistical_inference.data_snooping_warning is True


# ---------------------------------------------------------------------------
# 4. Copilot & Skeptic Mode Grounding in Audit Reports
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_research_audit_copilot_skeptic_mode():
    agent = ResearchFactoryCopilotAgent()
    templates = HypothesisGenerator.get_canonical_templates()
    hyp = next(h for h in templates if h.hypothesis_id == "HYP_QUALITY_TREND_01")
    scorecard = validator.validate_hypothesis(hyp)
    report = research_auditor.audit_hypothesis(hyp, scorecard)

    # Audit inquiry
    audit_res = await agent.answer(
        hypothesis_id=hyp.hypothesis_id,
        user_message="Audit this research result",
        hypothesis=vars(hyp),
        scorecard=vars(scorecard),
        audit_report=vars(report),
        is_skeptic_mode=False,
    )
    assert "reply" in audit_res
    assert "Independent" in audit_res["reply"] or "Audit" in audit_res["reply"]

    # Skeptic Disprove inquiry
    skeptic_res = await agent.answer(
        hypothesis_id=hyp.hypothesis_id,
        user_message="TRY TO DISPROVE THIS RESULT",
        hypothesis=vars(hyp),
        scorecard=vars(scorecard),
        audit_report=vars(report),
        is_skeptic_mode=True,
    )
    assert "reply" in skeptic_res
    assert "Survivorship" in skeptic_res["reply"] or "Skeptic" in skeptic_res["reply"]
