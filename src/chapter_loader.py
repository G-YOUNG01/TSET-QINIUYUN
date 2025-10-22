"""Utilities to load chapter text from disk."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from .models import Chapter


def load_chapters(folder: Path) -> List[Chapter]:
    """Load chapters from text files sorted by filename."""

    if not folder.exists():
        raise FileNotFoundError(f"Chapter folder not found: {folder}")

    files: Iterable[Path] = sorted(p for p in folder.iterdir() if p.suffix.lower() in {".txt", ".md"})
    chapters: List[Chapter] = []
    for index, path in enumerate(files, start=1):
        text = path.read_text(encoding="utf-8")
        chapters.append(
            Chapter(
                index=index,
                title=path.stem,
                text=text.strip(),
            )
        )
    if not chapters:
        raise ValueError(f"No chapter files found in {folder}")
    return chapters
