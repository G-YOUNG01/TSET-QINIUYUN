"""SQLite-backed storage for generation metadata."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import ChapterBundle


class RecordStore:
    """Persist chapter and panel metadata for later retrieval."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chapters (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    metadata_path TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS panels (
                    chapter_id INTEGER NOT NULL,
                    panel_index INTEGER NOT NULL,
                    scene_index INTEGER NOT NULL,
                    image_path TEXT NOT NULL,
                    audio_path TEXT,
                    narration TEXT,
                    layout TEXT,
                    review_status TEXT,
                    review_issues TEXT,
                    UNIQUE(chapter_id, panel_index)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def log_chapter(self, bundle: ChapterBundle) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO chapters(id, title, metadata_path) VALUES (?, ?, ?)",
                (bundle.chapter.index, bundle.chapter.title, str(bundle.metadata_path)),
            )
            for asset in bundle.panels:
                layout = None
                if asset.layout:
                    layout = json.dumps(
                        {
                            "x": asset.layout.x,
                            "y": asset.layout.y,
                            "width": asset.layout.width,
                            "height": asset.layout.height,
                        }
                    )
                review_status = asset.review.status if asset.review else None
                review_issues = json.dumps(asset.review.issues) if asset.review else None
                connection.execute(
                    """
                    INSERT OR REPLACE INTO panels(
                        chapter_id,
                        panel_index,
                        scene_index,
                        image_path,
                        audio_path,
                        narration,
                        layout,
                        review_status,
                        review_issues
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        bundle.chapter.index,
                        asset.prompt.panel_index,
                        asset.prompt.scene_index,
                        str(asset.image_path),
                        str(asset.audio_path) if asset.audio_path else None,
                        asset.narration_script,
                        layout,
                        review_status,
                        review_issues,
                    ),
                )
            connection.commit()

    # Future: add incremental logging helpers when pipeline streams panel completion.
