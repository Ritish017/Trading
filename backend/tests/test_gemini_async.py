import pytest
import asyncio
from backend.app.ai_engine.gemini_client import GeminiModels, GeminiResponse

@pytest.mark.asyncio
async def test_gemini_models_unconfigured_key_returns_unavailable():
    """Verify that unconfigured API key safely returns typed UNAVAILABLE without hanging or raising."""
    models = GeminiModels(api_key="")
    resp = await models.generate_content_async(model="gemini-2.5-flash", contents="Test prompt")
    assert isinstance(resp, GeminiResponse)
    assert resp.status == "UNAVAILABLE"
    assert resp.text == ""
    assert "NOT_CONFIGURED" in (resp.error or "")

@pytest.mark.asyncio
async def test_gemini_models_sync_call_does_not_block():
    """Verify synchronous generate_content returns safely without throwing."""
    models = GeminiModels(api_key="")
    resp = models.generate_content(model="gemini-2.5-flash", contents="Test prompt")
    assert isinstance(resp, GeminiResponse)
    assert resp.status == "UNAVAILABLE"
