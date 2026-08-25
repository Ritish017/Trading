import os
import logging
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger(__name__)

class GeminiResponse:
    def __init__(self, text: str = ""):
        self.text = text

class GeminiModels:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def generate_content(self, model: str = "gemini-2.5-flash", contents: str = "") -> GeminiResponse:
        """Call Google Gemini REST API using httpx without heavy grpc/protobuf dependencies."""
        if not self.api_key:
            return GeminiResponse(text="")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{
                "parts": [{"text": contents}]
            }]
        }
        try:
            with httpx.Client(timeout=30.0) as client:
                res = client.post(url, json=payload)
                res.raise_for_status()
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates and "content" in candidates[0] and "parts" in candidates[0]["content"]:
                    parts = candidates[0]["content"]["parts"]
                    text = "".join(p.get("text", "") for p in parts)
                    return GeminiResponse(text=text)
                return GeminiResponse(text="")
        except Exception as e:
            logger.error(f"[GEMINI REST CLIENT ERROR] {e}")
            raise

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
