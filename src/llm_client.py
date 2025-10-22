"""Simple wrapper for interacting with an LLM provider."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List

import httpx

from .config import LLMConfig


@dataclass
class LLMClient:
    """Minimal HTTP client to call a JSON LLM API."""

    config: LLMConfig

    def generate(self, messages: List[Dict[str, str]]) -> str:
        """Call the LLM and return the assistant content."""

        api_key = self.config.api_key or os.getenv("LLM_API_KEY")
        if not api_key:
            raise RuntimeError("Missing LLM API key. Set config or LLM_API_KEY env var.")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        url = (self.config.api_base or "https://api.openai.com/v1") + "/chat/completions"
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"].strip()
