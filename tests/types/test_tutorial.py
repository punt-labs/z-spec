"""Tests for punt_zspec.types.tutorial."""

from __future__ import annotations

from pathlib import Path

from punt_zspec.types import Collection, Lesson


def _lesson(title: str, order: int) -> Lesson:
    return Lesson(
        title=title,
        spec_path=f"{title}.tex",
        annotation="",
        highlights=[],
        order=order,
    )


def test_collection_base_path_is_a_path() -> None:
    collection = Collection(
        title="T", description="d", lessons=[], base_path=Path("/tmp/z")
    )
    assert isinstance(collection.base_path, Path)


def test_lessons_preserve_declared_order() -> None:
    lessons = [_lesson("a", 0), _lesson("b", 1), _lesson("c", 2)]
    collection = Collection(
        title="T", description="d", lessons=lessons, base_path=Path(".")
    )
    assert [lesson.order for lesson in collection.lessons] == [0, 1, 2]
