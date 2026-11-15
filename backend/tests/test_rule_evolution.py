"""
Unit & Integration Tests for J.A.R.V.I.S. Adaptive Rule Evolution & InstaBox Deployer
"""

import pytest
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.signal_engine.rule_evolution_engine import (
    RuleEvolutionEngine, DynamicTradingRule, TradeMemoryEntry
)
from backend.app.cloud.instabox_deployer import InstaBoxDeployer
from backend.app.ai_engine.gemini_client import GeminiClient, GeminiResponse


@pytest.fixture
def mock_gemini_client():
    client = MagicMock()
    client.api_key = "AIzaSyTestMockKey"
    client.models = MagicMock()
    client.models.get_best_flash_model.return_value = "gemini-2.5-flash"
    client.models.get_best_reasoning_model.return_value = "gemini-2.5-pro"
    client.models.list_available_models_async = AsyncMock(return_value=[
        "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"
    ])
    client.models.generate_content_async = AsyncMock(return_value=GeminiResponse(
        text="""{
            "rule_id": "RULE_106",
            "name": "Adaptive Vega Defense",
            "regime": "HIGH_IV_RANGE_BOUND",
            "confidence": 0.91,
            "action_type": "ALLOW",
            "rule_description": "Filters wings to prevent vega spikes during monetary policy events.",
            "condition_logic": "iv_percentile > 70 and abs(basis_velocity) < 0.5",
            "jarvis_insight": "Synthesized to lock in profits prior to IV contraction."
        }""",
        status="SUCCESS",
        model="gemini-2.5-pro"
    ))
    return client


def test_rule_engine_initialization_and_seed_rules():
    engine = RuleEvolutionEngine()
    assert len(engine.rules) >= 5
    assert "RULE_101" in engine.rules
    assert "RULE_104" in engine.rules
    assert "RULE_105" in engine.rules

    # RULE_105 should enforce ₹10k capital budget
    rule_105 = engine.rules["RULE_105"]
    assert "₹10,000" in rule_105.name or "10,000" in rule_105.rule_description
    assert rule_105.status == "ACTIVE"


def test_evaluate_signal_micro_cap_veto():
    engine = RuleEvolutionEngine()
    
    # Trade with excessive debit on 10k capital should trigger RULE_105 veto
    is_approved, applied, reason = engine.evaluate_signal_against_rules(
        regime="LOW_IV_TRENDING",
        sentiment_score=0.4,
        basis_velocity=2.0,
        oi_pattern="LONG_BUILDUP",
        iv_percentile=30.0,
        capital=10000.0,
        net_premium_or_debit=5500.0  # Exceeds ₹3,500 budget
    )
    assert is_approved is False
    assert "RULE_105" in reason or "budget" in reason

    # Within budget should be approved
    is_approved_ok, applied_ok, reason_ok = engine.evaluate_signal_against_rules(
        regime="LOW_IV_TRENDING",
        sentiment_score=0.4,
        basis_velocity=2.0,
        oi_pattern="LONG_BUILDUP",
        iv_percentile=30.0,
        capital=10000.0,
        net_premium_or_debit=1500.0
    )
    assert is_approved_ok is True
    assert "RULE_102" in applied_ok


def test_trade_memory_and_feedback_loop():
    engine = RuleEvolutionEngine()
    initial_trades = len(engine.journal)

    # Record trade entry
    entry_id = engine.record_trade_entry(
        symbol="NIFTY 50",
        strategy_name="BULL_CALL_DEBIT_SPREAD",
        regime="LOW_IV_TRENDING",
        sentiment_score=0.45,
        basis_velocity=2.2,
        oi_pattern="LONG_BUILDUP",
        entry_cost=1200.0,
        applied_rules=["RULE_102"],
        notes="High conviction momentum entry"
    )
    assert entry_id.startswith("mem_")
    assert len(engine.journal) == initial_trades + 1

    # Record exit as winner
    engine.record_trade_exit(entry_id, exit_pnl=650.0, is_winner=True)
    assert engine.rules["RULE_102"].win_count >= 1


@pytest.mark.asyncio
async def test_evolve_rules_with_gemini(mock_gemini_client):
    engine = RuleEvolutionEngine(gemini_client=mock_gemini_client)
    res = await engine.evolve_rules_with_gemini()
    assert res["status"] in ("SUCCESS", "FALLBACK_SYNTHESIZED")
    assert "new_rule" in res
    assert res["new_rule"]["rule_id"] in engine.rules


@pytest.mark.asyncio
async def test_instabox_deployer_methods():
    deployer = InstaBoxDeployer(api_key="ibk_testmockkey")
    assert deployer.api_key == "ibk_testmockkey"
    headers = deployer._headers(with_idempotency=True)
    assert "Idempotency-Key" in headers
    assert "X-API-Key" in headers

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"machines": [{"name": "apex-quant-lab", "id": "m_test123"}]})
        machines = await deployer.list_machines()
        assert len(machines) == 1
        assert machines[0]["name"] == "apex-quant-lab"
