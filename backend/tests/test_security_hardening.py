import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.config import settings

@pytest.fixture
def client():
    return TestClient(app)


def test_cors_explicit_origins_configured(client):
    """Verify CORS middleware exposes explicit origins, never wildcard origin with credentials."""
    response = client.options(
        "/api/paper/positions",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        }
    )
    assert response.status_code == 200
    allow_origin = response.headers.get("access-control-allow-origin")
    assert allow_origin != "*"
    assert allow_origin in settings.cors_allowed_origins


def test_cors_evil_origin_rejected(client):
    """Verify unauthorized evil origins are not granted Access-Control-Allow-Origin."""
    response = client.options(
        "/api/paper/positions",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        }
    )
    allow_origin = response.headers.get("access-control-allow-origin")
    assert allow_origin != "https://evil.example"


def test_api_auth_token_fail_closed_mode(client, monkeypatch):
    """
    FAIL-CLOSED AUDIT: When API_AUTH_TOKEN is not configured (None or empty),
    mutations MUST FAIL CLOSED with 401 Unauthorized.
    A warning is not sufficient; bypass is strictly forbidden.
    """
    monkeypatch.setattr(settings, "api_auth_token", None)

    order_payload = {
        "symbol": "RELIANCE.NS",
        "productType": "CNC",
        "side": "BUY",
        "quantity": 10,
        "price": 2500.0,
    }
    # No auth
    res = client.post("/api/paper/order", json=order_payload)
    assert res.status_code == 401
    assert "Server fails closed" in res.json()["detail"]

    # Even with an arbitrary header, when unconfigured on server, it must fail closed
    res = client.post(
        "/api/paper/order",
        headers={"X-API-Key": "some-token"},
        json=order_payload
    )
    assert res.status_code == 401
    assert "Server fails closed" in res.json()["detail"]


def test_unauthenticated_paper_order_rejected_when_token_configured(client, monkeypatch):
    """When API_AUTH_TOKEN is configured, anonymous mutating requests must be rejected with 401."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")
    
    order_payload = {
        "symbol": "RELIANCE.NS",
        "productType": "CNC",
        "side": "BUY",
        "quantity": 10,
        "price": 2500.0,
    }
    
    # Anonymous request
    res = client.post("/api/paper/order", json=order_payload)
    assert res.status_code == 401
    assert "Invalid or missing API authentication token" in res.json()["detail"]


def test_invalid_bearer_token_rejected(client, monkeypatch):
    """Invalid bearer tokens must be rejected with 401."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")
    
    res = client.post(
        "/api/paper/reset",
        headers={"Authorization": "Bearer wrong-token"},
        json={"initialCapital": 1000000.0}
    )
    assert res.status_code == 401


def test_malformed_auth_header_rejected(client, monkeypatch):
    """Malformed auth headers must be rejected with 401."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")

    res = client.post(
        "/api/paper/reset",
        headers={"Authorization": "NotBearer"},
        json={"initialCapital": 1000000.0}
    )
    assert res.status_code == 401


def test_authenticated_paper_order_with_api_key_header(client, monkeypatch):
    """Valid X-API-Key token allows order execution."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")
    
    order_payload = {
        "symbol": "TCS.NS",
        "productType": "CNC",
        "side": "BUY",
        "quantity": 5,
        "price": 3500.0,
    }
    
    res = client.post(
        "/api/paper/order",
        headers={"X-API-Key": "secret-test-token-xyz"},
        json=order_payload
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "FILLED"
    assert data["position"]["symbol"] == "TCS.NS"


def test_authenticated_paper_reset_with_bearer_token(client, monkeypatch):
    """Valid Bearer token allows portfolio reset."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")
    
    res = client.post(
        "/api/paper/reset",
        headers={"Authorization": "Bearer secret-test-token-xyz"},
        json={"initialCapital": 500000.0}
    )
    assert res.status_code == 200
    summary = res.json()
    assert summary["available_capital"] == 500000.0
    assert summary["positions"] == []


def test_authenticated_paper_capital_endpoint(client, monkeypatch):
    """POST /api/paper/capital updates capital under authentication."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")

    res = client.post(
        "/api/paper/capital",
        headers={"X-API-Key": "secret-test-token-xyz"},
        json={"capital": 750000.0}
    )
    assert res.status_code == 200
    assert res.json()["capital"] == 750000.0


def test_unauthenticated_research_factory_rejected(client, monkeypatch):
    """Mutating research factory endpoints must be protected."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")
    
    res = client.post(
        "/api/research-factory/generate",
        json={
            "name": "Test Hyp",
            "technical_strategy_id": "EMA_GOLDEN_CROSS",
            "fundamental_factor_id": "ROCE_GROWTH",
            "regime_filter": "TRENDING_BULLISH",
            "universe": "NIFTY50"
        }
    )
    assert res.status_code == 401


def test_cross_account_authorization_isolation(client, monkeypatch):
    """
    AUTHORIZATION ISOLATION TEST:
    Account A must not be allowed to access, place orders for, close positions of,
    or reset Account B. Any such attempt must be rejected with 403 Forbidden.
    """
    # Configure two scoped tokens
    monkeypatch.setattr(settings, "api_auth_token", "token_a:account_A,token_b:account_B")

    order_payload_for_b = {
        "symbol": "INFY.NS",
        "productType": "CNC",
        "side": "BUY",
        "quantity": 10,
        "price": 1400.0,
        "account_id": "account_B",  # Target Account B!
    }

    # 1. Account A attempts to place order for Account B -> 403 Forbidden
    res = client.post(
        "/api/paper/order",
        headers={"X-API-Key": "token_a"},
        json=order_payload_for_b
    )
    assert res.status_code == 403
    assert "is not authorized" in res.json()["detail"]

    # 2. Account A attempts to reset Account B -> 403 Forbidden
    res = client.post(
        "/api/paper/reset",
        headers={"X-API-Key": "token_a"},
        json={"initialCapital": 1000000.0, "account_id": "account_B"}
    )
    assert res.status_code == 403
    assert "is not authorized" in res.json()["detail"]

    # 3. Account A attempts to update capital for Account B -> 403 Forbidden
    res = client.post(
        "/api/paper/capital",
        headers={"X-API-Key": "token_a"},
        json={"capital": 500000.0, "account_id": "account_B"}
    )
    assert res.status_code == 403
    assert "is not authorized" in res.json()["detail"]

    # 4. Account A attempts to close position on Account B -> 403 Forbidden
    res = client.post(
        "/api/paper/close/POS_TEST_B",
        headers={"X-API-Key": "token_a"},
        json={"close_price": 1500.0, "account_id": "account_B"}
    )
    assert res.status_code == 403
    assert "is not authorized" in res.json()["detail"]

    # 5. Account A operating on Account A succeeds -> 200 OK
    res = client.post(
        "/api/paper/capital",
        headers={"X-API-Key": "token_a"},
        json={"capital": 600000.0, "account_id": "account_A"}
    )
    assert res.status_code == 200


# ===========================================================================
# Endpoint Authentication Hardening Tests (Milestone 1 R1/R5)
# ===========================================================================

from backend.app.signal_engine.signal_store import signal_store as apex_signal_store
from backend.app.signal_engine.models import (
    SignalDecision,
    SignalDirection,
    SignalState,
    SignalQualityGrade,
    StopLossResult,
    TargetLevel,
    PositionSizing,
)


def test_unauthenticated_paper_positions_rejected(client, monkeypatch):
    """FAIL-CLOSED: Unauthenticated GET /api/paper/positions must return 401."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")
    res = client.get("/api/paper/positions")
    assert res.status_code == 401
    assert "Invalid or missing API authentication token" in res.json()["detail"]


def test_authenticated_paper_positions_succeeds(client, monkeypatch):
    """GET /api/paper/positions with valid X-API-Key returns portfolio summary."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")
    res = client.get(
        "/api/paper/positions",
        headers={"X-API-Key": "secret-test-token-xyz"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "positions" in data
    assert "available_capital" in data
    assert "capital" in data


def test_cross_account_positions_query_rejected(client, monkeypatch):
    """Cross-account GET /api/paper/positions?account_id=... must return 403."""
    monkeypatch.setattr(settings, "api_auth_token", "token_a:account_a,token_b:account_b")
    res = client.get(
        "/api/paper/positions?account_id=account_b",
        headers={"X-API-Key": "token_a"}
    )
    assert res.status_code == 403
    assert "is not authorized" in res.json()["detail"]


def test_unauthenticated_signal_paper_trade_rejected(client, monkeypatch):
    """Anonymous POST /api/signals/{id}/paper-trade must return 401."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")
    res = client.post(
        "/api/signals/test_sig_001/paper-trade",
        json={"signal_id": "test_sig_001"}
    )
    assert res.status_code == 401


def test_signal_paper_trade_cross_account_rejected(client, monkeypatch):
    """Account A cannot execute a signal trade for Account B (403 Forbidden)."""
    monkeypatch.setattr(settings, "api_auth_token", "token_a:account_a,token_b:account_b")

    sig = SignalDecision(
        signal_id="sig_auth_cross",
        symbol="SBIN.NS",
        direction=SignalDirection.LONG,
        state=SignalState.QUALIFIED,
        quality_grade=SignalQualityGrade.A,
        entry=800.0,
        stop_loss=StopLossResult(price=780.0, method="ATR"),
        targets=[TargetLevel(price=840.0, level=1, method="RR", method_description="1:2 RR")],
        position_size=PositionSizing(
            method="FIXED_RISK",
            capital=1000000.0,
            risk_per_trade_pct=1.0,
            max_risk_amount=10000.0,
            entry_price=800.0,
            stop_price=780.0,
            risk_per_share=20.0,
            quantity=10,
            capital_required=8000.0,
            maximum_loss=200.0,
        ),
    )
    apex_signal_store.upsert_signal(sig)

    res = client.post(
        "/api/signals/sig_auth_cross/paper-trade",
        headers={"X-API-Key": "token_a"},
        json={"signal_id": "sig_auth_cross", "account_id": "account_b"}
    )
    assert res.status_code == 403
    assert "is not authorized" in res.json()["detail"]


def test_signal_paper_trade_unqualified_rejected(client, monkeypatch):
    """Signals not in QUALIFIED state must be rejected with 400."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")

    sig = SignalDecision(
        signal_id="sig_unqualified",
        symbol="INFY.NS",
        direction=SignalDirection.LONG,
        state=SignalState.CANDIDATE,  # Not QUALIFIED!
        quality_grade=SignalQualityGrade.A,
        entry=1800.0,
        stop_loss=StopLossResult(price=1750.0, method="ATR"),
    )
    apex_signal_store.upsert_signal(sig)

    res = client.post(
        "/api/signals/sig_unqualified/paper-trade",
        headers={"X-API-Key": "secret-test-token-xyz"},
        json={"signal_id": "sig_unqualified"}
    )
    assert res.status_code == 400
    assert "Only QUALIFIED signals can be executed" in res.json()["detail"]


def test_signal_paper_trade_expired_rejected(client, monkeypatch):
    """Expired signals must be rejected with 400."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")

    sig = SignalDecision(
        signal_id="sig_expired",
        symbol="RELIANCE.NS",
        direction=SignalDirection.LONG,
        state=SignalState.QUALIFIED,
        quality_grade=SignalQualityGrade.A,
        entry=2800.0,
        stop_loss=StopLossResult(price=2750.0, method="ATR"),
        expiry="2020-01-01T00:00:00Z",  # Expired in past
    )
    apex_signal_store.upsert_signal(sig)

    res = client.post(
        "/api/signals/sig_expired/paper-trade",
        headers={"X-API-Key": "secret-test-token-xyz"},
        json={"signal_id": "sig_expired"}
    )
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


def test_signal_paper_trade_malformed_timestamp_rejected(client, monkeypatch):
    """FAIL-CLOSED: Malformed expiry timestamps must be rejected with 400."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")

    for malformed in ["not-a-valid-timestamp", "2026-99-99T99:99:99", "abc123xyz"]:
        sig = SignalDecision(
            signal_id=f"sig_malformed_{abs(hash(malformed))}",
            symbol="RELIANCE.NS",
            direction=SignalDirection.LONG,
            state=SignalState.QUALIFIED,
            quality_grade=SignalQualityGrade.A,
            entry=2800.0,
            stop_loss=StopLossResult(price=2750.0, method="ATR"),
            expiry=malformed,
        )
        apex_signal_store.upsert_signal(sig)

        res = client.post(
            f"/api/signals/{sig.signal_id}/paper-trade",
            headers={"X-API-Key": "secret-test-token-xyz"},
            json={"signal_id": sig.signal_id}
        )
        assert res.status_code == 400
        assert "invalid or expired signal timestamp" in res.json()["detail"].lower()


def test_signal_paper_trade_naive_past_timestamp_rejected(client, monkeypatch):
    """FAIL-CLOSED: Offset-naive past timestamp must be parsed and rejected with 400."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")

    sig = SignalDecision(
        signal_id="sig_naive_past",
        symbol="RELIANCE.NS",
        direction=SignalDirection.LONG,
        state=SignalState.QUALIFIED,
        quality_grade=SignalQualityGrade.A,
        entry=2800.0,
        stop_loss=StopLossResult(price=2750.0, method="ATR"),
        expiry="2020-01-01 12:00:00",
    )
    apex_signal_store.upsert_signal(sig)

    res = client.post(
        "/api/signals/sig_naive_past/paper-trade",
        headers={"X-API-Key": "secret-test-token-xyz"},
        json={"signal_id": "sig_naive_past"}
    )
    assert res.status_code == 400
    assert "invalid or expired signal timestamp" in res.json()["detail"].lower()


def test_signal_paper_trade_aware_utc_past_timestamp_rejected(client, monkeypatch):
    """FAIL-CLOSED: Offset-aware UTC past timestamps must be rejected with 400."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")

    for aware_past in ["2020-01-01T12:00:00Z", "2020-01-01T12:00:00+00:00"]:
        sig = SignalDecision(
            signal_id=f"sig_aware_past_{abs(hash(aware_past))}",
            symbol="RELIANCE.NS",
            direction=SignalDirection.LONG,
            state=SignalState.QUALIFIED,
            quality_grade=SignalQualityGrade.A,
            entry=2800.0,
            stop_loss=StopLossResult(price=2750.0, method="ATR"),
            expiry=aware_past,
        )
        apex_signal_store.upsert_signal(sig)

        res = client.post(
            f"/api/signals/{sig.signal_id}/paper-trade",
            headers={"X-API-Key": "secret-test-token-xyz"},
            json={"signal_id": sig.signal_id}
        )
        assert res.status_code == 400
        assert "invalid or expired signal timestamp" in res.json()["detail"].lower()


def test_signal_paper_trade_future_valid_timestamp_accepted(client, monkeypatch):
    """Signals with valid future expiry timestamp pass validation and fill order."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")

    sig = SignalDecision(
        signal_id="sig_future_valid",
        symbol="TCS.NS",
        direction=SignalDirection.LONG,
        state=SignalState.QUALIFIED,
        quality_grade=SignalQualityGrade.A,
        entry=3800.0,
        stop_loss=StopLossResult(price=3700.0, method="ATR"),
        targets=[TargetLevel(price=4000.0, level=1, method="RR", method_description="1:2 RR")],
        position_size=PositionSizing(
            method="FIXED_RISK",
            capital=1000000.0,
            risk_per_trade_pct=1.0,
            max_risk_amount=10000.0,
            entry_price=3800.0,
            stop_price=3700.0,
            risk_per_share=100.0,
            quantity=5,
            capital_required=19000.0,
            maximum_loss=500.0,
        ),
        expiry="2035-01-01T12:00:00Z",
    )
    apex_signal_store.upsert_signal(sig)

    res = client.post(
        "/api/signals/sig_future_valid/paper-trade",
        headers={"X-API-Key": "secret-test-token-xyz"},
        json={"signal_id": "sig_future_valid"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["order_result"]["status"] == "FILLED"


def test_authenticated_signal_paper_trade_succeeds(client, monkeypatch):
    """Valid QUALIFIED signal executed by authenticated caller fills order."""
    monkeypatch.setattr(settings, "api_auth_token", "secret-test-token-xyz")

    sig = SignalDecision(
        signal_id="sig_valid_exec",
        symbol="TCS.NS",
        direction=SignalDirection.LONG,
        state=SignalState.QUALIFIED,
        quality_grade=SignalQualityGrade.A,
        entry=3800.0,
        stop_loss=StopLossResult(price=3700.0, method="ATR"),
        targets=[TargetLevel(price=4000.0, level=1, method="RR", method_description="1:2 RR")],
        position_size=PositionSizing(
            method="FIXED_RISK",
            capital=1000000.0,
            risk_per_trade_pct=1.0,
            max_risk_amount=10000.0,
            entry_price=3800.0,
            stop_price=3700.0,
            risk_per_share=100.0,
            quantity=5,
            capital_required=19000.0,
            maximum_loss=500.0,
        ),
    )
    apex_signal_store.upsert_signal(sig)

    res = client.post(
        "/api/signals/sig_valid_exec/paper-trade",
        headers={"X-API-Key": "secret-test-token-xyz"},
        json={"signal_id": "sig_valid_exec"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["order_result"]["status"] == "FILLED"
    assert data["signal"]["state"] == "TRIGGERED"

