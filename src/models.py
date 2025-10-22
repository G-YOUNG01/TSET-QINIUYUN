"""Core domain models for the novel-to-comic pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence


@dataclass
class Chapter:
    """Single chapter of the novel."""

    index: int
    title: str
    text: str


@dataclass
class Scene:
    """High-level scene extracted from a chapter."""

    chapter_index: int
    scene_index: int
    summary: str
    beats: List[str]


@dataclass
class PanelPrompt:
    """Prompt and instructions to render a comic panel."""

    chapter_index: int
    scene_index: int
    panel_index: int
    description: str
    dialogue: List[str] = field(default_factory=list)
    style: str = ""


@dataclass
class PanelAsset:
    """Generated comic panel asset metadata."""

    prompt: PanelPrompt
    image_path: Path
    narration_script: str
    audio_path: Optional[Path] = None
    layout: Optional["LayoutFrame"] = None
    review: Optional["PanelReview"] = None


@dataclass
class ChapterBundle:
    """Aggregated artifacts for a processed chapter."""

    chapter: Chapter
    scenes: Sequence[Scene]
    panels: Sequence[PanelAsset]
    metadata_path: Path


@dataclass
class LayoutFrame:
    """Normalized layout frame used for panel positioning."""

    x: float
    y: float
    width: float
    height: float


@dataclass
class PanelReview:
    """Automated review outcome for a generated panel."""

    status: str
    issues: List[str] = field(default_factory=list)

