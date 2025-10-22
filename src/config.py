"""Application configuration models and helpers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class LLMConfig:
    """Holds model and provider information for LLM calls."""

    model: str
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048


@dataclass
class ImageConfig:
    """Parameters needed for image generation."""

    model: str
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    width: int = 768
    height: int = 1024
    guidance_scale: float = 7.0


@dataclass
class TTSConfig:
    """Configuration for text-to-speech provider."""

    voice: str
    model: str
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    speaking_rate: float = 1.0


@dataclass
class PipelineConfig:
    """Root configuration for the generation pipeline."""

    output_dir: Path
    llm: LLMConfig
    image: ImageConfig
    tts: Optional[TTSConfig] = None
    chapter_concurrency: int = 1
    panel_concurrency: int = 2
    database_path: Optional[Path] = None
    enable_quality: bool = False

    def ensure_output_dirs(self) -> None:
        """Create expected output folders if they are missing."""

        sub_dirs = ["storyboards", "panels", "audio", "metadata"]
        for sub in sub_dirs:
            path = self.output_dir / sub
            path.mkdir(parents=True, exist_ok=True)
