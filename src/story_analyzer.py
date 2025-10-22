"""Analyze chapters and produce structured scenes using an LLM."""
from __future__ import annotations

import json
from typing import List

from .llm_client import LLMClient
from .models import Chapter, Scene


SCENE_PROMPT_TEMPLATE = """
You are an experienced comic script writer. Break the following chapter into at most 6 scenes.
For each scene provide a one paragraph summary and a list of 3-5 key visual beats.
Respond with strict JSON in the format:
{
  "scenes": [
    {
      "summary": "...",
      "beats": ["beat1", "beat2"]
    }
  ]
}
Chapter title: {title}
Chapter text:
{chapter_text}
""".strip()


class SceneExtractor:
    """Uses an LLM to convert a chapter into scene descriptors."""

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def extract(self, chapter: Chapter) -> List[Scene]:
        prompt = SCENE_PROMPT_TEMPLATE.format(title=chapter.title, chapter_text=chapter.text)
        messages = [
            {"role": "system", "content": "You transform novel chapters into comic-ready scenes."},
            {"role": "user", "content": prompt},
        ]
        completion = self._client.generate(messages)
        payload = json.loads(completion)
        scenes: List[Scene] = []
        for idx, scene_data in enumerate(payload["scenes"], start=1):
            scenes.append(
                Scene(
                    chapter_index=chapter.index,
          scene_index=idx,
                    summary=scene_data["summary"].strip(),
                    beats=[beat.strip() for beat in scene_data["beats"]],
                )
            )
        return scenes
