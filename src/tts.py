"""Text-to-speech helper."""
from __future__ import annotations

import os
from pathlib import Path

import httpx

from .config import TTSConfig


class SpeechSynthesizer:
    """Wrap a TTS REST API to synthesize narration."""

    def __init__(self, config: TTSConfig) -> None:
        self._config = config

    def synthesize(self, text: str, output_path: Path) -> Path:
        """Create audio narration for a panel script."""

        api_key = self._config.api_key or os.getenv("TTS_API_KEY")
        if not api_key:
            raise RuntimeError("Missing TTS API key. Set config or TTS_API_KEY env var.")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "voice": self._config.voice,
            "model": self._config.model,
            "text": text,
            "speaking_rate": self._config.speaking_rate,
        }
        url = (self._config.api_base or "https://api.elevenlabs.io/v1") + "/text-to-speech"
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.content
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)
        return output_path
