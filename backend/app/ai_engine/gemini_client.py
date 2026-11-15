import os
import asyncio
import random
import logging
from typing import Optional, Dict, Any, List
import httpx

logger = logging.getLogger(__name__)


class GeminiResponse:
    def __init__(self, text: str = "", status: str = "SUCCESS", error: Optional[str] = None, model: str = ""):
        self.text = text
        self.status = status
        self.error = error
        self.model = model


class GeminiModels:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._cached_models: List[str] = []
        self._cache_time: float = 0.0

    def clean_model_name(self, model: str) -> str:
        if model.startswith("models/"):
            model = model[len("models/"):]
        # Automatic alias mapping for Google Generative Language API
        if "3.8" in model or "3." in model:
            return "gemini-2.5-flash"
        return model

    async def list_available_models_async(self) -> List[str]:
        """
        Dynamically discovers all models available from the Gemini API key
        that support content generation.
        """
        if not self.api_key:
            return ["gemini-2.5-flash", "gemini-2.5-pro"]

        import time
        now = time.time()
        if self._cached_models and (now - self._cache_time) < 300:
            return self._cached_models

        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    models = [
                        self.clean_model_name(m.get("name", ""))
                        for m in data.get("models", [])
                        if "generateContent" in m.get("supportedGenerationMethods", [])
                    ]
                    if models:
                        self._cached_models = models
                        self._cache_time = now
                        return models
        except Exception as e:
            logger.warning(f"[GEMINI CLIENT] Failed to fetch models list: {e}")

        return ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-flash"]

    def list_available_models(self) -> List[str]:
        if not self.api_key:
            return ["gemini-2.5-flash", "gemini-2.5-pro"]

        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
        try:
            with httpx.Client(timeout=6.0) as client:
                res = client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    models = [
                        self.clean_model_name(m.get("name", ""))
                        for m in data.get("models", [])
                        if "generateContent" in m.get("supportedGenerationMethods", [])
                    ]
                    if models:
                        self._cached_models = models
                        return models
        except Exception as e:
            logger.warning(f"[GEMINI CLIENT] Sync model list fetch failed: {e}")

        return ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-flash"]

    def get_best_flash_model(self) -> str:
        """Picks the newest high-performance flash model available."""
        available = self._cached_models or self.list_available_models()
        candidates = ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash", "gemini-1.5-flash"]
        for c in candidates:
            if c in available:
                return c
        return "gemini-3.8-flash"

    def get_best_reasoning_model(self) -> str:
        """Picks the best reasoning/pro model available for deep analysis & rule synthesis."""
        available = self._cached_models or self.list_available_models()
        candidates = ["gemini-3.8-flash", "gemini-2.5-pro", "gemini-pro-latest", "gemini-1.5-pro", "gemini-2.5-flash"]
        for c in candidates:
            if c in available:
                return c
        return "gemini-3.8-flash"

    async def generate_content_async(
        self,
        model: str = "gemini-2.5-flash",
        contents: str = "",
        timeout: float = 12.0,
        max_retries: int = 2,
    ) -> GeminiResponse:
        """
        Asynchronous, non-blocking call to Google Gemini REST API.
        Includes exponential backoff with jitter on 429 rate limit or 5xx server errors.
        Never blocks the FastAPI event loop.
        """
        if not self.api_key:
            return GeminiResponse(text="", status="UNAVAILABLE", error="GEMINI_API_KEY_NOT_CONFIGURED")

        model_clean = self.clean_model_name(model)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_clean}:generateContent?key={self.api_key}"
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
                        return GeminiResponse(text=text, status="SUCCESS", model=model_clean)
                    return GeminiResponse(text="", status="EMPTY_RESPONSE", model=model_clean)
            except Exception as e:
                logger.warning(f"[GEMINI ASYNC CLIENT] Attempt {attempt}/{max_retries} failed for {model_clean}: {e}")
                if attempt == max_retries:
                    return GeminiResponse(text="", status="UNAVAILABLE", error=str(e), model=model_clean)
                await asyncio.sleep(delay)
                delay *= 2.0

        return GeminiResponse(text="", status="UNAVAILABLE", error="MAX_RETRIES_EXCEEDED", model=model_clean)

    def generate_content(self, model: str = "gemini-2.5-flash", contents: str = "") -> GeminiResponse:
        """
        Safe synchronous caller with bounded timeout.
        """
        if not self.api_key:
            return GeminiResponse(text="", status="UNAVAILABLE", error="GEMINI_API_KEY_NOT_CONFIGURED")

        model_clean = self.clean_model_name(model)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_clean}:generateContent?key={self.api_key}"
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
                    return GeminiResponse(text=text, status="SUCCESS", model=model_clean)
                return GeminiResponse(text="", status="EMPTY_RESPONSE", model=model_clean)
        except Exception as e:
            logger.warning(f"[GEMINI SYNC CALL] Request failed for {model_clean}: {e}")
            return GeminiResponse(text="", status="UNAVAILABLE", error=str(e), model=model_clean)


class GeminiClient:
    """Lightweight drop-in replacement for google.genai.Client using pure HTTP REST."""
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.models = GeminiModels(api_key=self.api_key)

    def update_api_key(self, api_key: str):
        self.api_key = api_key
        self.models = GeminiModels(api_key=api_key)


try:
    from google import genai
except ImportError:
    class genai:  # type: ignore
        Client = GeminiClient
