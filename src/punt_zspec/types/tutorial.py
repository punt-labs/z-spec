"""Tutorial browser types: lessons and their enclosing collection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Lesson:
    """A single lesson in a tutorial collection."""

    title: str
    spec_path: str  # relative to manifest directory
    annotation: str  # didactic markdown
    highlights: list[str]  # section/schema names to default-open
    order: int  # 0-based index


@dataclass(frozen=True)
class Collection:
    """A tutorial collection parsed from a manifest.toml."""

    title: str
    description: str
    lessons: list[Lesson]
    base_path: Path  # directory containing the manifest
