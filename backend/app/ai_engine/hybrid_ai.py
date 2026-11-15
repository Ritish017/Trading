"""
Hybrid AI Engine
Orchestrates Gemini (gemini-3.8-flash) and AMD Token Lab (DeepSeek-V4-Flash)
with automatic failover, load distribution, and multi-model discovery.
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from backend.app.ai_engine.gemini_client import GeminiClient, GeminiResponse
from backend.app.ai_engine.amd_tokenlab_client import AMDTokenLabClient, AMDTokenLabResponse

logger = logging.getLogger(__name__)


class HybridAIResponse:
    def __init__(
        self,
        text: str = "",
        status: str = "SUCCESS",
        provider: str = "gemini",
        model: str = "",
        tokens_used: int = 0,
        cost_points: float = 0.0,
        error: Optional[str] = None,
    ):
        self.text = text
        self.status = status
        self.provider = provider  # "gemini" or "amd_tokenlab"
        self.model = model
        self.tokens_used = tokens_used
        self.cost_points = cost_points
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "status": self.status,
            "provider": self.provider,
            "model": self.model,
            "tokens_used": self.tokens_used,
            "cost_points": self.cost_points,
            "error": self.error,
        }


class HybridAIEngine:
    """
    Unified AI engine combining Google Gemini and AMD Token Lab.
    Provides intelligent routing, quota conservation, and automatic fallback.
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        amd_api_key: Optional[str] = None,
        preferred_provider: str = "auto",  # "auto", "gemini", "amd"
        gemini_preferred_model: str = "gemini-3.8-flash",
        amd_preferred_model: str = "DeepSeek-V4-Flash",
    ):
        self.gemini_client = GeminiClient(api_key=gemini_api_key)
        self.amd_client = AMDTokenLabClient(api_key=amd_api_key, default_model=amd_preferred_model)
        self.preferred_provider = preferred_provider
        self.gemini_preferred_model = gemini_preferred_model
        self.amd_preferred_model = amd_preferred_model

    async def get_system_telemetry(self) -> Dict[str, Any]:
        """Returns the status and available models across all configured AI providers."""
        gemini_configured = bool(self.gemini_client.api_key)
        amd_configured = self.amd_client.is_configured

        gemini_models = []
        if gemini_configured:
            try:
                gemini_models = await self.gemini_client.models.list_available_models_async()
            except Exception:
                gemini_models = [self.gemini_preferred_model, "gemini-2.5-flash", "gemini-2.5-pro"]

        amd_models = []
        if amd_configured:
            try:
                amd_models = await self.amd_client.list_available_models_async()
            except Exception:
                amd_models = [self.amd_preferred_model, "Qwen3.8-27B", "Gemma-4-31B-IT"]

        return {
            "providers": {
                "gemini": {
                    "configured": gemini_configured,
                    "primary_model": self.gemini_preferred_model,
                    "available_models": gemini_models[:8],
                },
                "amd_tokenlab": {
                    "configured": amd_configured,
                    "primary_model": self.amd_preferred_model,
                    "base_url": self.amd_client.base_url,
                    "available_models": amd_models,
                },
            },
            "active_routing": self.preferred_provider,
        }

    async def generate_completion_async(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        prefer_provider: Optional[str] = None,
        timeout: float = 14.0,
    ) -> HybridAIResponse:
        """
        Executes an AI completion request with seamless dual-provider failover.
        Routes to Gemini or AMD Token Lab, failing over automatically if one hits quota/rate limits.
        """
        route = prefer_provider or self.preferred_provider

        # If user explicitly chooses AMD or if preferred is AMD
        if route == "amd" and self.amd_client.is_configured:
            amd_res = await self.amd_client.generate_chat_completion_async(
                prompt=prompt,
                system_prompt=system_prompt,
                model=self.amd_preferred_model,
                timeout=timeout,
            )
            if amd_res.status == "SUCCESS":
                return HybridAIResponse(
                    text=amd_res.text,
                    status="SUCCESS",
                    provider="amd_tokenlab",
                    model=amd_res.model,
                    tokens_used=amd_res.tokens_used,
                    cost_points=amd_res.cost_points,
                )
            logger.warning(f"[HYBRID AI] AMD call failed ({amd_res.error}), falling back to Gemini...")

        # Default / Auto: Try Gemini first (gemini-3.8-flash)
        if self.gemini_client.api_key:
            target_gemini_model = self.gemini_preferred_model
            combined_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            gemini_res = await self.gemini_client.models.generate_content_async(
                model=target_gemini_model,
                contents=combined_prompt,
                timeout=min(5.0, timeout),
                max_retries=1,
            )
            if gemini_res.status == "SUCCESS" and gemini_res.text:
                return HybridAIResponse(
                    text=gemini_res.text,
                    status="SUCCESS",
                    provider="gemini",
                    model=gemini_res.model,
                )
            
            logger.warning(
                f"[HYBRID AI] Gemini {target_gemini_model} returned {gemini_res.status} ({gemini_res.error}). "
                "Triggering instantaneous zero-downtime failover to AMD Token Lab (DeepSeek-V4-Flash)..."
            )

        # Fallback to AMD Token Lab
        if self.amd_client.is_configured:
            amd_res = await self.amd_client.generate_chat_completion_async(
                prompt=prompt,
                system_prompt=system_prompt,
                model=self.amd_preferred_model,
                timeout=max(25.0, timeout),
            )
            if amd_res.status == "SUCCESS":
                return HybridAIResponse(
                    text=amd_res.text,
                    status="SUCCESS",
                    provider="amd_tokenlab (fallback)",
                    model=amd_res.model,
                    tokens_used=amd_res.tokens_used,
                    cost_points=amd_res.cost_points,
                )

        return HybridAIResponse(
            text="",
            status="UNAVAILABLE",
            provider="none",
            error="Both Gemini and AMD Token Lab endpoints were unreachable or unconfigured.",
        )


# Global singleton instance
hybrid_ai = HybridAIEngine()
