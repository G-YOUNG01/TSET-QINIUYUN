"""Orchestrates the novel-to-comic generation pipeline."""
from __future__ import annotations

import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, List

from .config import PipelineConfig
from .image_generation import ImageGenerator
from .layout import LayoutEngine
from .llm_client import LLMClient
from .models import Chapter, ChapterBundle, PanelAsset, PanelPrompt
from .quality import QualityInspector
from .storage import RecordStore
from .story_analyzer import SceneExtractor
from .storyboard import StoryboardBuilder
from .tts import SpeechSynthesizer


class ComicPipeline:
    """Coordinate LLM scene extraction, panel prompt creation, and asset generation."""

    def __init__(self, config: PipelineConfig) -> None:
        self._config = config
        llm_client = LLMClient(config.llm)
        self._scene_extractor = SceneExtractor(llm_client)
        self._storyboard_builder = StoryboardBuilder(llm_client)
        self._image_generator = ImageGenerator(config.image)
        self._speech = SpeechSynthesizer(config.tts) if config.tts else None
        self._layout_engine = LayoutEngine()
        self._quality = QualityInspector(llm_client) if config.enable_quality else None
        self._store = RecordStore(config.database_path) if config.database_path else None

    def run(self, chapters: Iterable[Chapter]) -> List[ChapterBundle]:
        """Process all chapters into comic assets."""

        self._config.ensure_output_dirs()
        bundles: List[ChapterBundle] = []
        for chapter in chapters:
            bundle = self._process_chapter(chapter)
            bundles.append(bundle)
        return bundles

    def _process_chapter(self, chapter: Chapter) -> ChapterBundle:
        scenes = self._scene_extractor.extract(chapter)
        panel_prompts: List[PanelPrompt] = []
        for scene in scenes:
            panel_prompts.extend(self._storyboard_builder.build(scene))

        panel_assets = self._generate_assets(chapter, panel_prompts)
        self._apply_layouts(panel_assets)
        self._apply_quality(panel_assets)
        metadata_path = self._write_metadata(chapter, scenes, panel_assets)
        bundle = ChapterBundle(
            chapter=chapter,
            scenes=scenes,
            panels=panel_assets,
            metadata_path=metadata_path,
        )
        if self._store:
            self._store.log_chapter(bundle)
        return bundle

    def _generate_assets(self, chapter: Chapter, prompts: List[PanelPrompt]) -> List[PanelAsset]:
        panels_dir = self._config.output_dir / "panels" / f"chapter{chapter.index:02d}"
        audio_dir = self._config.output_dir / "audio" / f"chapter{chapter.index:02d}"

        assets: List[PanelAsset] = []
        with ThreadPoolExecutor(max_workers=self._config.panel_concurrency) as executor:
            future_map = {
                executor.submit(self._image_generator.generate_panel, prompt, panels_dir): prompt
                for prompt in prompts
            }
            for future in as_completed(future_map):
                prompt = future_map[future]
                image_path = future.result()
                narration = self._compose_narration(prompt)
                audio_path = None
                if self._speech and narration:
                    filename = f"chapter{prompt.chapter_index:02d}_panel{prompt.panel_index:02d}.mp3"
                    audio_path = self._speech.synthesize(narration, audio_dir / filename)
                assets.append(
                    PanelAsset(
                        prompt=prompt,
                        image_path=image_path,
                        narration_script=narration,
                        audio_path=audio_path,
                    )
                )
        return sorted(assets, key=lambda asset: (asset.prompt.scene_index, asset.prompt.panel_index))

    def _apply_layouts(self, assets: List[PanelAsset]) -> None:
        """Assign layout frames scene by scene."""

        scene_map = defaultdict(list)
        for asset in assets:
            scene_map[asset.prompt.scene_index].append(asset)
        for scene_assets in scene_map.values():
            placements = self._layout_engine.assign_layouts([asset.prompt for asset in scene_assets])
            for asset in scene_assets:
                key = (
                    asset.prompt.chapter_index,
                    asset.prompt.scene_index,
                    asset.prompt.panel_index,
                )
                asset.layout = placements.get(key)

    def _apply_quality(self, assets: List[PanelAsset]) -> None:
        """Run automated QA if enabled."""

        if not self._quality:
            return
        for asset in assets:
            asset.review = self._quality.evaluate(asset)

    def _compose_narration(self, prompt: PanelPrompt) -> str:
        """Create narration text from dialogue lines."""

        if not prompt.dialogue:
            return ""
        return "\n".join(prompt.dialogue)

    def _write_metadata(self, chapter: Chapter, scenes, assets: List[PanelAsset]) -> Path:
        metadata_dir = self._config.output_dir / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        path = metadata_dir / f"chapter{chapter.index:02d}.json"
        payload = {
            "chapter": {
                "index": chapter.index,
                "title": chapter.title,
            },
            "scenes": [
                {
                    "scene_index": scene.scene_index,
                    "summary": scene.summary,
                    "beats": scene.beats,
                }
                for scene in scenes
            ],
            "panels": [
                {
                    "chapter_index": asset.prompt.chapter_index,
                    "scene_index": asset.prompt.scene_index,
                    "panel_index": asset.prompt.panel_index,
                    "description": asset.prompt.description,
                    "dialogue": asset.prompt.dialogue,
                    "style": asset.prompt.style,
                    "image_path": str(asset.image_path),
                    "audio_path": str(asset.audio_path) if asset.audio_path else None,
                    "narration": asset.narration_script,
                    "layout": (
                        {
                            "x": asset.layout.x,
                            "y": asset.layout.y,
                            "width": asset.layout.width,
                            "height": asset.layout.height,
                        }
                        if asset.layout
                        else None
                    ),
                    "review": (
                        {
                            "status": asset.review.status,
                            "issues": asset.review.issues,
                        }
                        if asset.review
                        else None
                    ),
                }
                for asset in assets
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
