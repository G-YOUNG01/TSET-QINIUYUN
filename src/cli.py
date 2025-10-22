"""Command line entry point for the novel-to-comic pipeline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .chapter_loader import load_chapters
from .config import ImageConfig, LLMConfig, PipelineConfig, TTSConfig
from .pipeline import ComicPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate comic assets from novel chapters.")
    parser.add_argument("chapters", type=Path, help="Folder containing chapter text files.")
    parser.add_argument("output", type=Path, help="Folder for generated assets.")
    parser.add_argument("--config", type=Path, help="Optional JSON config overriding defaults.")
    parser.add_argument("--with-tts", action="store_true", help="Enable TTS narration synthesis.")
    parser.add_argument("--database", type=Path, help="Optional SQLite database path for logging results.")
    parser.add_argument("--enable-quality", action="store_true", help="Enable LLM-driven quality review.")
    return parser.parse_args()


def load_pipeline_config(args: argparse.Namespace) -> PipelineConfig:
    defaults = PipelineConfig(
        output_dir=args.output,
        llm=LLMConfig(model="gpt-4o-mini"),
        image=ImageConfig(model="stability-core"),
        tts=None,
        database_path=args.database,
        enable_quality=args.enable_quality,
    )
    if args.with_tts:
        defaults.tts = TTSConfig(voice="default", model="standard")
    if args.config:
        data = json.loads(args.config.read_text(encoding="utf-8"))
        if "llm" in data:
            defaults.llm = LLMConfig(**data["llm"])
        if "image" in data:
            defaults.image = ImageConfig(**data["image"])
        if "tts" in data:
            defaults.tts = TTSConfig(**data["tts"])
        defaults.output_dir = Path(data.get("output_dir", defaults.output_dir))
        if "database_path" in data:
            defaults.database_path = Path(data["database_path"])
        if "enable_quality" in data:
            defaults.enable_quality = bool(data["enable_quality"])
    if args.database:
        defaults.database_path = args.database
    if args.enable_quality:
        defaults.enable_quality = True
    return defaults


def main() -> None:
    args = parse_args()
    chapters = load_chapters(args.chapters)
    config = load_pipeline_config(args)
    pipeline = ComicPipeline(config)
    pipeline.run(chapters)


if __name__ == "__main__":
    main()
