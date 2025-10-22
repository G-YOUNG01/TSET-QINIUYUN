"""Assign panel layout frames based on the number of panels."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

from .models import LayoutFrame, PanelPrompt

PanelKey = Tuple[int, int, int]


@dataclass
class PanelPlacement:
    """Mapping from panel index to a normalized frame."""

    key: PanelKey
    frame: LayoutFrame


class LayoutEngine:
    """Provides simple heuristic-based panel layout templates."""

    def assign_layouts(self, prompts: Iterable[PanelPrompt]) -> Dict[PanelKey, LayoutFrame]:
        prompts = list(prompts)
        count = len(prompts)
        if not count:
            return {}

        frames = self._template_for(count)
        placements: Dict[PanelKey, LayoutFrame] = {}
        for prompt, frame in zip(prompts, frames, strict=False):
            key = (prompt.chapter_index, prompt.scene_index, prompt.panel_index)
            placements[key] = frame
        return placements

    def _template_for(self, count: int) -> Tuple[LayoutFrame, ...]:
        templates = {
            1: (LayoutFrame(0.0, 0.0, 1.0, 1.0),),
            2: (
                LayoutFrame(0.0, 0.0, 0.5, 1.0),
                LayoutFrame(0.5, 0.0, 0.5, 1.0),
            ),
            3: (
                LayoutFrame(0.0, 0.0, 0.5, 0.5),
                LayoutFrame(0.5, 0.0, 0.5, 0.5),
                LayoutFrame(0.0, 0.5, 1.0, 0.5),
            ),
            4: (
                LayoutFrame(0.0, 0.0, 0.5, 0.5),
                LayoutFrame(0.5, 0.0, 0.5, 0.5),
                LayoutFrame(0.0, 0.5, 0.5, 0.5),
                LayoutFrame(0.5, 0.5, 0.5, 0.5),
            ),
        }
        if count in templates:
            return templates[count]
        return self._build_grid(count)

    def _build_grid(self, count: int) -> Tuple[LayoutFrame, ...]:
        columns = 2 if count <= 6 else 3
        rows = math.ceil(count / columns)
        width = 1.0 / columns
        height = 1.0 / rows
        frames = []
        for idx in range(count):
            row = idx // columns
            col = idx % columns
            frames.append(
                LayoutFrame(
                    x=col * width,
                    y=row * height,
                    width=width,
                    height=height,
                )
            )
        return tuple(frames)
