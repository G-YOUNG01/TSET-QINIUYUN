"""Automated quality inspection powered by an LLM."""
from __future__ import annotations

import json
from typing import Dict

from .llm_client import LLMClient
from .models import PanelAsset, PanelReview

QUALITY_PROMPT = """
You are a senior comic art reviewer. Inspect the panel information and decide if it needs human review.
Return strict JSON:
{
  "status": "PASS" | "REVIEW",
  "issues": ["issue one", "issue two"]
}
Consider clarity, consistency with prompts, dialogue tone, and potential safety issues.
Panel description: {description}
Panel dialogue: {dialogue}
Panel style guidance: {style}
Narration script: {narration}
""".strip()


class QualityInspector:
    """Delegates panel review to an LLM based inspector."""

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def evaluate(self, asset: PanelAsset) -> PanelReview:
        dialogue = " | ".join(asset.prompt.dialogue) if asset.prompt.dialogue else "(无对话)"
        prompt = QUALITY_PROMPT.format(
            description=asset.prompt.description,
            dialogue=dialogue,
            style=asset.prompt.style or "(未指定)",
            narration=asset.narration_script or "(无旁白)",
        )
        messages = [
            {"role": "system", "content": "You perform quality assurance for generated comic panels."},
            {"role": "user", "content": prompt},
        ]
        try:
            completion = self._client.generate(messages)
            payload: Dict[str, object] = json.loads(completion)
            status = str(payload.get("status", "REVIEW")).upper()
            issues = [str(item) for item in payload.get("issues", []) if item]
            if status not in {"PASS", "REVIEW"}:
                status = "REVIEW"
            return PanelReview(status=status, issues=issues)
        except Exception as exc:  # noqa: BLE001 - fallback to review state
            return PanelReview(status="REVIEW", issues=[f"LLM 质检失败: {exc}"])
