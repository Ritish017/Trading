import os
import asyncio
import random
import logging
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger(__name__)


class GeminiResponse:
    def __init__(self, text: str = "", status: str = "SUCCESS", error: Optional[str] = None):
        self.text = text
        self.status = status
        self.error = error


class GeminiModels:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate_content_async(
        self,
        model: str = "gemini-2.5-flash",
        contents: str = "",
        timeout: float = 15.0,
        max_retries: int = 3,
    ) -> GeminiResponse:
        """
        Asynchronous, non-blocking call to Google Gemini REST API.
        Includes exponential backoff with jitter on 429 rate limit or 5xx server errors.
        Never blocks the FastAPI event loop.
        """
        if not self.api_key:
            return GeminiResponse(text="", status="UNAVAILABLE", error="GEMINI_API_KEY_NOT_CONFIGURED")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{
                "parts": [{"text": contents}]
            }]
        }

        delay = 1.0
        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    res = await client.post(url, json=payload)
                    if res.status_code == 429 or res.status_code >= 500:
                        if attempt == max_retries:
                            res.raise_for_status()
                        jitter = random.uniform(0.1, 0.4)
                        await asyncio.sleep(delay + jitter)
                        delay *= 2.0
                        continue

                    res.raise_for_status()
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0] and "parts" in candidates[0]["content"]:
                        parts = candidates[0]["content"]["parts"]
                        text = "".join(p.get("text", "") for p in parts)
                        return GeminiResponse(text=text, status="SUCCESS")
                    return GeminiResponse(text="", status="EMPTY_RESPONSE")
            except Exception as e:
                logger.warning(f"[GEMINI ASYNC CLIENT] Attempt {attempt}/{max_retries} failed: {e}")
                if attempt == max_retries:
                    return GeminiResponse(text="", status="UNAVAILABLE", error=str(e))
                await asyncio.sleep(delay)
                delay *= 2.0

        return GeminiResponse(text="", status="UNAVAILABLE", error="MAX_RETRIES_EXCEEDED")

    def generate_content(self, model: str = "gemini-2.5-flash", contents: str = "") -> GeminiResponse:
        """
        Safe synchronous caller with bounded timeout.
        """
        if not self.api_key:
            return GeminiResponse(text="", status="UNAVAILABLE", error="GEMINI_API_KEY_NOT_CONFIGURED")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
        payload = {"contents": [{"parts": [{"text": contents}]}]}
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, json=payload)
                res.raise_for_status()
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates and "content" in candidates[0] and "parts" in candidates[0]["content"]:
                    parts = candidates[0]["content"]["parts"]
                    text = "".join(p.get("text", "") for p in parts)
                    return GeminiResponse(text=text, status="SUCCESS")
                return GeminiResponse(text="", status="EMPTY_RESPONSE")
        except Exception as e:
            logger.warning(f"[GEMINI SYNC CALL] Request failed: {e}")
            return GeminiResponse(text="", status="UNAVAILABLE", error=str(e))


class GeminiClient:
    """Lightweight drop-in replacement for google.genai.Client using pure HTTP REST."""
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.models = GeminiModels(api_key=self.api_key)


try:
    from google import genai
except ImportError:
    class genai:  # type: ignore
        Client = GeminiClient
