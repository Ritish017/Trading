import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.config import settings

@pytest.mark.asyncio
async def test_order_negative_quantity_rejected(monkeypatch):
    """Verify negative quantities are rejected with 422 Unprocessable Entity."""
    monkeypatch.setattr(settings, "api_auth_token", "test-secret-token")
    headers = {"X-API-Key": "test-secret-token"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/paper/order", json={
            "symbol": "INFY.NS",
            "quantity": -10,
            "price": 1500.0,
            "side": "BUY",
        }, headers=headers)
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_order_zero_quantity_rejected(monkeypatch):
    """Verify zero quantity is rejected with 422."""
    monkeypatch.setattr(settings, "api_auth_token", "test-secret-token")
    headers = {"X-API-Key": "test-secret-token"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/paper/order", json={
            "symbol": "INFY.NS",
            "quantity": 0,
            "price": 1500.0,
            "side": "BUY",
        }, headers=headers)
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_order_negative_and_zero_price_rejected(monkeypatch):
    """Verify negative and zero prices are rejected with 422."""
    monkeypatch.setattr(settings, "api_auth_token", "test-secret-token")
    headers = {"X-API-Key": "test-secret-token"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Negative price
        res1 = await ac.post("/api/paper/order", json={
            "symbol": "INFY.NS",
            "quantity": 5,
            "price": -1500.0,
            "side": "BUY",
        }, headers=headers)
        assert res1.status_code == 422

        # Zero price
        res2 = await ac.post("/api/paper/order", json={
            "symbol": "INFY.NS",
            "quantity": 5,
            "price": 0.0,
            "side": "BUY",
        }, headers=headers)
        assert res2.status_code == 422


@pytest.mark.asyncio
async def test_order_huge_quantity_margin_rejection(monkeypatch):
    """Verify exorbitant quantity is safely rejected by margin calculation without crash."""
    monkeypatch.setattr(settings, "api_auth_token", "test-secret-token")
    headers = {"X-API-Key": "test-secret-token"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/paper/order", json={
            "symbol": "RELIANCE.NS",
            "quantity": 100_000_000,  # 100M shares = trillions INR
            "price": 2500.0,
            "side": "BUY",
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "REJECTED"
        assert "Insufficient margin" in data.get("reason", "")


@pytest.mark.asyncio
async def test_order_empty_and_oversized_symbol_rejected(monkeypatch):
    """Verify empty or excessively long tickers are rejected with 422."""
    monkeypatch.setattr(settings, "api_auth_token", "test-secret-token")
    headers = {"X-API-Key": "test-secret-token"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Empty symbol
        res1 = await ac.post("/api/paper/order", json={
            "symbol": "",
            "quantity": 1,
            "price": 100.0,
            "side": "BUY",
        }, headers=headers)
        assert res1.status_code == 422

        # Oversized symbol (> 50 chars)
        res2 = await ac.post("/api/paper/order", json={
            "symbol": "X" * 100,
            "quantity": 1,
            "price": 100.0,
            "side": "BUY",
        }, headers=headers)
        assert res2.status_code == 422


@pytest.mark.asyncio
async def test_injection_strings_sanitized(monkeypatch):
    """Verify SQL injection and path traversal strings in parameters do not cause 500 error."""
    monkeypatch.setattr(settings, "api_auth_token", "test-secret-token")
    headers = {"X-API-Key": "test-secret-token"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # SQL Injection in order symbol
        res1 = await ac.post("/api/paper/order", json={
            "symbol": "'; DROP TABLE paper_orders; --",
            "quantity": 1,
            "price": 100.0,
            "side": "BUY",
        }, headers=headers)
        assert res1.status_code in [200, 400, 422]  # Handled safely, never 500!

        # Path traversal in research command center
        res2 = await ac.get("/api/research-command-center/..%2F..%2Fetc%2Fpasswd", headers=headers)
        assert res2.status_code in [404, 400, 422]  # Handled safely, never 500!


@pytest.mark.asyncio
async def test_negative_capital_update_rejected(monkeypatch):
    """Verify negative capital update is rejected with 400."""
    monkeypatch.setattr(settings, "api_auth_token", "test-secret-token")
    headers = {"X-API-Key": "test-secret-token"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/paper/capital", json={
            "capital": -50000.0
        }, headers=headers)
        assert res.status_code == 400
        assert "strictly positive" in res.json().get("detail", "")
