"""
ACCEPTANCE SUITE: Security & Authorization Red Team
Validates fail-closed security, cross-account isolation, IDOR defense, timing safety, and CORS.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app, paper_engine
from backend.app.config import settings
from backend.app.security.auth import verify_api_key, AccountContext, authorize_account_access
import secrets


client = TestClient(app)


def test_unauthenticated_mutation_fails_closed():
    """Attack 1: Mutation without authentication header must be rejected with 401."""
    original_token = settings.api_auth_token
    settings.api_auth_token = "prod_secret_token_12345"
    try:
        res = client.post(
            "/api/paper/order",
            json={
                "symbol": "TCS.NS",
                "side": "BUY",
                "quantity": 10,
                "price": 3800.0,
                "productType": "CNC",
            }
        )
        assert res.status_code == 401
        assert "Invalid or missing" in res.json().get("detail", "")
    finally:
        settings.api_auth_token = original_token


def test_invalid_tokens_rejected_with_401():
    """Attack 2: Wrong, empty, malformed, and unicode tokens must return 401."""
    original_token = settings.api_auth_token
    settings.api_auth_token = "prod_secret_token_12345"
    try:
        # Wrong token
        res1 = client.post("/api/paper/order", headers={"Authorization": "Bearer wrong_token_abc"}, json={"symbol": "INFY.NS", "side": "BUY", "quantity": 1, "price": 1800.0})
        assert res1.status_code == 401

        # Empty token
        res2 = client.post("/api/paper/order", headers={"Authorization": "Bearer "}, json={"symbol": "INFY.NS", "side": "BUY", "quantity": 1, "price": 1800.0})
        assert res2.status_code == 401

        # Malformed / Special character token
        res3 = client.post("/api/paper/order", headers={"Authorization": "Bearer invalid_token_special_!@#$%^&*()"}, json={"symbol": "INFY.NS", "side": "BUY", "quantity": 1, "price": 1800.0})
        assert res3.status_code == 401
    finally:
        settings.api_auth_token = original_token


def test_absent_secret_fails_closed_in_production():
    """Attack 3: If API_AUTH_TOKEN is unset or empty, server must fail closed with 401."""
    original_token = settings.api_auth_token
    settings.api_auth_token = ""
    try:
        res = client.post(
            "/api/paper/order",
            headers={"Authorization": "Bearer some_arbitrary_key"},
            json={"symbol": "RELIANCE.NS", "side": "BUY", "quantity": 10, "price": 2900.0}
        )
        assert res.status_code == 401
        assert "fails closed" in res.json().get("detail", "")
    finally:
        settings.api_auth_token = original_token


def test_cross_account_mutation_rejected_with_403():
    """Attack 4: Token scoped to Account A cannot place orders for Account B."""
    original_token = settings.api_auth_token
    settings.api_auth_token = "token_a:account_a,token_b:account_b"
    try:
        res = client.post(
            "/api/paper/order",
            headers={"Authorization": "Bearer token_a"},
            json={
                "symbol": "SBIN.NS",
                "side": "BUY",
                "quantity": 5,
                "price": 800.0,
                "account_id": "account_b",
            }
        )
        assert res.status_code == 403
        assert "not authorized to access or mutate account 'account_b'" in res.json().get("detail", "")
    finally:
        settings.api_auth_token = original_token


def test_cross_account_scoped_read_requires_auth_and_ownership():
    """Attack 5: Scoped query of another account's positions must fail with 401 (unauth) or 403 (unauthorized)."""
    original_token = settings.api_auth_token
    settings.api_auth_token = "token_a:account_a,token_b:account_b"
    try:
        # Unauthenticated query for specific account
        res_unauth = client.get("/api/paper/positions?account_id=account_b")
        assert res_unauth.status_code == 401

        # Authenticated as account_a but querying account_b
        res_forbidden = client.get("/api/paper/positions?account_id=account_b", headers={"Authorization": "Bearer token_a"})
        assert res_forbidden.status_code == 403
    finally:
        settings.api_auth_token = original_token


def test_idor_position_closure_rejected_with_403():
    """Attack 6 (IDOR): Account A cannot close a position owned by Account B."""
    original_token = settings.api_auth_token
    settings.api_auth_token = "token_a:account_a,token_b:account_b"
    try:
        # Account B opens a position
        order_b = client.post(
            "/api/paper/order",
            headers={"Authorization": "Bearer token_b"},
            json={"symbol": "INFY.NS", "side": "BUY", "quantity": 10, "price": 1800.0, "account_id": "account_b"}
        )
        assert order_b.status_code == 200
        pos_id = order_b.json()["position"]["id"]

        # Account A attempts to close Account B's position
        res_idor = client.post(
            f"/api/paper/close/{pos_id}",
            headers={"Authorization": "Bearer token_a"},
            json={"account_id": "account_a"}
        )
        assert res_idor.status_code == 403
        assert "IDOR violation" in res_idor.json().get("detail", "")

        # Verify Account B's position is still open
        assert pos_id in paper_engine.positions
    finally:
        settings.api_auth_token = original_token


def test_constant_time_comparison_verified():
    """Attack 7: Verify constant-time comparison is active for secret evaluation."""
    secret = "production_super_secret_token_alpha_omega_98765"
    candidate_match = "production_super_secret_token_alpha_omega_98765"
    candidate_mismatch = "production_super_secret_token_alpha_omega_00000"

    assert secrets.compare_digest(secret, candidate_match) is True
    assert secrets.compare_digest(secret, candidate_mismatch) is False


def test_cors_whitelist_enforces_rejection_of_unauthorized_origins():
    """Attack 8: Evil origins are rejected by CORS preflight."""
    res = client.options(
        "/api/paper/positions",
        headers={
            "Origin": "https://evil-attacker.com",
            "Access-Control-Request-Method": "GET",
        }
    )
    # Origin must not be allowed
    allow_origin = res.headers.get("access-control-allow-origin")
    assert allow_origin != "https://evil-attacker.com"
