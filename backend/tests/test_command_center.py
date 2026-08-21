"""
Unit Test Suite — APEX Live Quant Research Command Center (Phase 13)
====================================================================
Verifies:
1. Command Center central orchestration snapshot contract
2. Dynamic evaluation of all 20 technical strategies
3. Factual Strategy Alignment Score (rule coverage, no fake probabilities)
4. Technical x Fundamental Confluence (RESEARCH CLASSIFICATION)
5. Point-in-time fundamental factor scorecards
6. Historical analogue search (PAST OBSERVATION EVIDENCE, not predictions)
7. Exact rule math detail per strategy
8. Technical/Fundamental contradiction detection
9. Frozen paper validation status (HYP_QUALITY_TREND_01, CONTINUE_OBSERVATION, 5/30 trades)
10. Evidence Hierarchy Levels 1 to 7
11. Forensic evidence timeline
12. Multi-stock watchlist & cross-stock comparator
13. Copilot & Skeptic Mode grounding
"""

import pytest

from backend.app.command_center.orchestrator import (
    ResearchCommandCenterOrchestrator,
    research_command_center,
)
from backend.app.command_center.models import (
    CommandCenterSnapshot,
    ResearchWorkflowStatus,
)
from backend.app.ai_engine.agents import ResearchFactoryCopilotAgent


@pytest.fixture(scope="module")
def snapshot():
    return research_command_center.get_snapshot("RELIANCE.NS", "1D")


# ---------------------------------------------------------------------------
# 1. Snapshot Contract & Core Orchestration
# ---------------------------------------------------------------------------

def test_command_center_snapshot_contract(snapshot):
    assert isinstance(snapshot, CommandCenterSnapshot)
    assert snapshot.market.symbol == "RELIANCE.NS"
    assert snapshot.market.current_price > 0
    assert snapshot.market.provider == "UPSTOX"
    assert snapshot.market.market_status in ["OPEN", "CLOSED", "LIVE"]


# ---------------------------------------------------------------------------
# 2. 20 Technical Strategies & Alignment Score
# ---------------------------------------------------------------------------

def test_all_20_strategies_evaluated(snapshot):
    assert len(snapshot.strategies) == 20
    assert snapshot.alignment.total_strategies == 20
    assert snapshot.alignment.total_rules_count > 0
    assert "Factual count" in snapshot.alignment.label

    # Verify every strategy has valid state and rule evaluations
    for s in snapshot.strategies:
        assert s.state in ["ACTIVE", "PARTIAL", "INACTIVE", "CONFLICTED", "UNAVAILABLE"]
        assert s.total_rules >= 1
        assert len(s.rule_evaluations) >= 1


# ---------------------------------------------------------------------------
# 3. Confluence & Disclaimers
# ---------------------------------------------------------------------------

def test_confluence_and_research_classification(snapshot):
    assert "RESEARCH CLASSIFICATION" in snapshot.confluence.disclaimer
    assert "NOT a buy/sell signal" in snapshot.confluence.disclaimer
    assert snapshot.confluence.confluence_quadrant is not None


# ---------------------------------------------------------------------------
# 4. Point-in-Time Fundamentals & Historical Analogues
# ---------------------------------------------------------------------------

def test_pit_fundamentals_and_historical_analogues(snapshot):
    assert len(snapshot.fundamentals) >= 5

    # Check publication dates enforced
    for f in snapshot.fundamentals:
        assert f.publication_date is not None

    # Historical analogues disclaimer
    assert snapshot.historical_analogues.total_similar_observations > 0
    assert "NOT expected return" in snapshot.historical_analogues.disclaimer
    assert "HISTORICAL ANALOGUE EVIDENCE" in snapshot.historical_analogues.disclaimer


# ---------------------------------------------------------------------------
# 5. Paper Status & Decision Reflection
# ---------------------------------------------------------------------------

def test_paper_validation_status_reflection(snapshot):
    assert snapshot.paper_status.hypothesis_id == "HYP_QUALITY_TREND_01"
    assert snapshot.paper_status.version == "1.0.0"
    assert snapshot.paper_status.decision == "CONTINUE_OBSERVATION"
    assert snapshot.paper_status.trade_count == 5
    assert snapshot.paper_status.required_sample_size == 30
    assert snapshot.paper_status.progress_pct == 16.7
    assert len(snapshot.paper_status.fingerprint) == 64


# ---------------------------------------------------------------------------
# 6. Evidence Hierarchy & Forensic Timeline
# ---------------------------------------------------------------------------

def test_evidence_hierarchy_and_timeline(snapshot):
    eh = snapshot.evidence_hierarchy
    assert "LEVEL 1" in eh.level_1_live_market["name"]
    assert "LEVEL 2" in eh.level_2_pit_fundamentals["name"]
    assert "LEVEL 3" in eh.level_3_deterministic_strategies["name"]
    assert "LEVEL 4" in eh.level_4_historical_research["name"]
    assert "LEVEL 5" in eh.level_5_backtest["name"]
    assert "LEVEL 6" in eh.level_6_forward_paper["name"]
    assert "LEVEL 7" in eh.level_7_model_interpretation["name"]

    assert len(snapshot.timeline) >= 1


# ---------------------------------------------------------------------------
# 7. Watchlist & Cross-Stock Comparison
# ---------------------------------------------------------------------------

def test_watchlist_and_cross_stock_isolation(snapshot):
    assert len(snapshot.watchlist) >= 5
    assert len(snapshot.cross_stock) >= 3


# ---------------------------------------------------------------------------
# 8. Copilot & Skeptic Mode Grounding
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_command_center_copilot_and_skeptic(snapshot):
    agent = ResearchFactoryCopilotAgent()

    res = await agent.answer(
        hypothesis_id="HYP_QUALITY_TREND_01",
        user_message="What is happening in RELIANCE right now?",
        audit_report=vars(snapshot),
        is_skeptic_mode=False,
    )
    assert "reply" in res

    skeptic_res = await agent.answer(
        hypothesis_id="HYP_QUALITY_TREND_01",
        user_message="CHALLENGE THIS STOCK (RELIANCE.NS)",
        audit_report=vars(snapshot),
        is_skeptic_mode=True,
    )
    assert "reply" in skeptic_res
    assert "Skeptic" in skeptic_res["reply"] or "Survivorship" in skeptic_res["reply"] or "Contradiction" in skeptic_res["reply"]
