"""Create panel prompts from scenes."""
from __future__ import annotations

import json
from typing import List

from .llm_client import LLMClient
from .models import PanelPrompt, Scene


PANEL_PROMPT_TEMPLATE = """
You are creating a comic storyboard. Turn the following scene summary and beats into 2-4 panels.
Return strict JSON with:
{
  "panels": [
    {
      "description": "visual description",
      "dialogue": ["bubble 1", "bubble 2"],
      "style": "art style guidance"
    }
  ]
}
Scene summary: {summary}
Beats: {beats}
""".strip()


class StoryboardBuilder:
    """Uses an LLM to turn scenes into detailed panel prompts."""

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def build(self, scene: Scene) -> List[PanelPrompt]:
        prompt = PANEL_PROMPT_TEMPLATE.format(
            summary=scene.summary,
            beats=scene.beats,
        )
        messages = [
            {"role": "system", "content": "You write concise comic panel prompts."},
            {"role": "user", "content": prompt},
        ]
        completion = self._client.generate(messages)
        payload = json.loads(completion)
        panel_prompts: List[PanelPrompt] = []
        for panel_index, panel in enumerate(payload["panels"], start=1):
            panel_prompts.append(
                PanelPrompt(
                    chapter_index=scene.chapter_index,
                    scene_index=scene.scene_index,
                    panel_index=panel_index,
                    description=panel["description"].strip(),
                    dialogue=[line.strip() for line in panel.get("dialogue", [])],
                    style=panel.get("style", "").strip(),
                )
            )
        return panel_prompts
