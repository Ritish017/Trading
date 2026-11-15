"""
AMD Token Lab Client
Integration with AMD Instinct / Radeon GPU-accelerated Open Models via OpenAI-compatible REST API.
API Base: https://api.tokenlab.amd.com/v1
Key models: DeepSeek-V4-Flash, DeepSeek-V4.1-Flash, Qwen3.8-27B, Gemma-4-31B-IT, MiniCPM5-2B
"""

import os
import asyncio
import logging
import random
import time
from typing import Optional, Dict, Any, List
import httpx

logger = logging.getLogger(__name__)


class AMDTokenLabResponse:
    def __init__(
        self,
        text: str = "",
        status: str = "SUCCESS",
        model: str = "",
        tokens_used: int = 0,
        cost_points: float = 0.0,
        error: Optional[str] = None,
    ):
        self.text = text
        self.status = status
        self.model = model
        self.tokens_used = tokens_used
        self.cost_points = cost_points
        self.error = error


class AMDTokenLabClient:
    """
    Asynchronous and synchronous client for AMD Token Lab (https://api.tokenlab.amd.com/v1).
    Utilizes OpenAI-compatible chat completions interface.
    """

    DEFAULT_BASE_URL = "https://api.tokenlab.amd.com/v1"
    DEFAULT_MODEL = "DeepSeek-V4-Flash"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: str = DEFAULT_MODEL,
    ):
        self.api_key = api_key or os.getenv("AMD_API_KEY", "")
        self.base_url = (base_url or os.getenv("AMD_BASE_URL", self.DEFAULT_BASE_URL)).rstrip("/")
        self.default_model = default_model
        self._cached_models: List[str] = []
        self._cache_time: float = 0.0

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.startswith("tl-"))

    async def list_available_models_async(self) -> List[str]:
        """Fetches the list of models currently active on the AMD GPU cluster."""
        if not self.is_configured:
            return ["DeepSeek-V4-Flash", "DeepSeek-V4.1-Flash", "Qwen3.8-27B", "Gemma-4-31B-IT"]

        now = time.time()
        if self._cached_models and (now - self._cache_time) < 600:
            return self._cached_models

        url = f"{self.base_url}/models"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    models = [m.get("id") for m in data.get("data", []) if m.get("id")]
                    if models:
                        self._cached_models = models
                        self._cache_time = now
                        return models
        except Exception as e:
            logger.warning(f"[AMD TOKEN LAB] Failed to query models: {e}")

        return ["DeepSeek-V4-Flash", "DeepSeek-V4.1-Flash", "Qwen3.8-27B", "Gemma-4-31B-IT"]

    async def generate_chat_completion_async(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1500,
        timeout: float = 16.0,
        max_retries: int = 2,
    ) -> AMDTokenLabResponse:
        """
        Sends an asynchronous chat completion request to AMD Token Lab.
        Non-blocking, with jittered retry for 429/5xx responses.
        """
        if not self.is_configured:
            return AMDTokenLabResponse(
                text="",
                status="UNCONFIGURED",
                error="AMD_API_KEY is not configured or missing tl- prefix",
            )

        target_model = model or self.default_model
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        delay = 1.0
        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    res = await client.post(url, headers=headers, json=payload)
                    if res.status_code in (429, 502, 503, 504):
                        if attempt == max_retries:
                            res.raise_for_status()
                        jitter = random.uniform(0.2, 0.5)
                        await asyncio.sleep(delay + jitter)
                        delay *= 2.0
                        continue

                    res.raise_for_status()
                    data = res.json()
                    choices = data.get("choices", [])
                    if choices:
                        message = choices[0].get("message", {})
                        text = message.get("content", "") or ""
                        usage = data.get("usage", {})
                        total_tokens = usage.get("total_tokens", 0)
                        cost = usage.get("cost", 0.0)
                        return AMDTokenLabResponse(
                            text=text,
                            status="SUCCESS",
                            model=target_model,
                            tokens_used=total_tokens,
                            cost_points=cost,
                        )
                    return AMDTokenLabResponse(
                        text="",
                        status="EMPTY_RESPONSE",
                        model=target_model,
                    )
            except Exception as e:
                logger.warning(
                    f"[AMD TOKEN LAB] Attempt {attempt}/{max_retries} failed for {target_model}: {e}"
                )
                if attempt == max_retries:
                    return AMDTokenLabResponse(
                        text="",
                        status="UNAVAILABLE",
                        error=str(e),
                        model=target_model,
                    )
                await asyncio.sleep(delay)
                delay *= 2.0

        return AMDTokenLabResponse(
            text="",
            status="UNAVAILABLE",
            error="MAX_RETRIES_EXCEEDED",
            model=target_model,
        )

    def generate_chat_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1500,
        timeout: float = 15.0,
    ) -> AMDTokenLabResponse:
        """Synchronous chat completion."""
        if not self.is_configured:
            return AMDTokenLabResponse(text="", status="UNCONFIGURED", error="AMD_API_KEY missing")

        target_model = model or self.default_model
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            with httpx.Client(timeout=timeout) as client:
                res = client.post(url, headers=headers, json=payload)
                res.raise_for_status()
                data = res.json()
                choices = data.get("choices", [])
                if choices:
                    text = choices[0].get("message", {}).get("content", "") or ""
                    usage = data.get("usage", {})
                    return AMDTokenLabResponse(
                        text=text,
                        status="SUCCESS",
                        model=target_model,
                        tokens_used=usage.get("total_tokens", 0),
                        cost_points=usage.get("cost", 0.0),
                    )
                return AMDTokenLabResponse(text="", status="EMPTY_RESPONSE", model=target_model)
        except Exception as e:
            logger.warning(f"[AMD TOKEN LAB SYNC] Error calling {target_model}: {e}")
            return AMDTokenLabResponse(text="", status="UNAVAILABLE", error=str(e), model=target_model)
