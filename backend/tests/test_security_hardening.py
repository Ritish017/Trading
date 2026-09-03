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
