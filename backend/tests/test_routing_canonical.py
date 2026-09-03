import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app

def test_fastapi_route_table_zero_duplicates():
    """Verify that every (method, path) route in FastAPI is unique."""
    routes = {}
    duplicates = []
    for r in app.routes:
        methods = getattr(r, "methods", None) or {"GET"}
        for m in methods:
            key = (m, r.path)
            if key in routes:
                duplicates.append(key)
            routes[key] = r

    assert len(duplicates) == 0, f"Found duplicate routes registered in FastAPI: {duplicates}"

def test_paper_positions_route_is_singular():
    """Verify that GET /api/paper/positions is registered exactly once."""
    matching = [
        r for r in app.routes 
        if getattr(r, "path", None) == "/api/paper/positions" and "GET" in (getattr(r, "methods", None) or set())
    ]
    assert len(matching) == 1, f"Expected exactly 1 GET /api/paper/positions route, found {len(matching)}"

@pytest.mark.asyncio
async def test_canonical_paper_positions_http_payload():
    """Execute HTTP GET /api/paper/positions and verify canonical unified portfolio payload."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/paper/positions")
        assert resp.status_code == 200
        data = resp.json()

        # Must contain all unified portfolio fields
        assert "positions" in data
        assert isinstance(data["positions"], list)
        assert "available_capital" in data
        assert isinstance(data["available_capital"], (int, float))
        assert "capital" in data
        assert "performance" in data
        assert isinstance(data["performance"], dict)
        assert "total_unrealized_pnl" in data
        assert "total_realized_pnl" in data
