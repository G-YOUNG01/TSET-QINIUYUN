"""Image generation utilities using an external diffusion API."""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Dict

import httpx

from .config import ImageConfig
from .models import PanelPrompt


class ImageGenerator:
    """Calls an image generation API and saves the result to disk."""

    def __init__(self, config: ImageConfig) -> None:
        self._config = config

    def generate_panel(self, prompt: PanelPrompt, output_dir: Path) -> Path:
        """Generate a panel image and return its path."""

        api_key = self._config.api_key or os.getenv("IMAGE_API_KEY")
        if not api_key:
            raise RuntimeError("Missing image API key. Set config or IMAGE_API_KEY env var.")

        payload: Dict[str, object] = {
            "prompt": prompt.description,
            "style": prompt.style,
            "width": self._config.width,
            "height": self._config.height,
            "guidance_scale": self._config.guidance_scale,
            "negative_prompt": "low quality, blurry, distorted, text artifacts",
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        url = (self._config.api_base or "https://api.stability.ai/v2") + "/images/generate"
        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        image_b64 = data["artifacts"][0]["base64"]
        image_bytes = base64.b64decode(image_b64)
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"chapter{prompt.chapter_index:02d}_panel{prompt.panel_index:02d}.png"
        path = output_dir / filename
        path.write_bytes(image_bytes)
        return path
