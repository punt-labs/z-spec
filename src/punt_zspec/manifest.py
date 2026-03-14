"""Parse tutorial collection manifests (manifest.toml)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from punt_zspec.types import Collection, Lesson


def parse_manifest(path: Path) -> Collection:
    """Parse a manifest.toml into a Collection.

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If required fields are missing or lessons list is empty.
    """
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    base_path = path.parent

    collection = data.get("collection", {})
    title = collection.get("title")
    if not title:
        msg = "manifest missing collection.title"
        raise ValueError(msg)
    description = collection.get("description", "")

    raw_lessons = data.get("lessons", [])
    if not raw_lessons:
        msg = "manifest must contain at least one [[lessons]] entry"
        raise ValueError(msg)

    lessons: list[Lesson] = []
    for i, entry in enumerate(raw_lessons):
        lesson_title = entry.get("title")
        if not lesson_title:
            msg = f"lesson {i} missing title"
            raise ValueError(msg)
        spec = entry.get("spec")
        if not spec:
            msg = f"lesson {i} ({lesson_title}) missing spec"
            raise ValueError(msg)
        lessons.append(
            Lesson(
                title=lesson_title,
                spec_path=spec,
                annotation=entry.get("annotation", ""),
                highlights=entry.get("highlights", []),
                order=i,
            )
        )

    return Collection(
        title=title,
        description=description,
        lessons=lessons,
        base_path=base_path,
    )
