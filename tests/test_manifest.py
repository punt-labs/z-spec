"""Tests for punt_zspec.manifest."""

from __future__ import annotations

from pathlib import Path

import pytest

from punt_zspec.manifest import parse_manifest


def _write_manifest(tmp_path: Path, content: str) -> Path:
    manifest = tmp_path / "manifest.toml"
    manifest.write_text(content, encoding="utf-8")
    return manifest


def test_parse_valid_manifest(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        """\
[collection]
title = "Intro to Z"
description = "A progressive tour"

[[lessons]]
title = "Basic Types"
spec = "01-basic.tex"
annotation = "Z starts with **basic types**."
highlights = ["Basic Types"]

[[lessons]]
title = "State"
spec = "02-state.tex"
annotation = "A state schema holds data."
highlights = ["State"]
""",
    )

    coll = parse_manifest(manifest)
    assert coll.title == "Intro to Z"
    assert coll.description == "A progressive tour"
    assert len(coll.lessons) == 2
    assert coll.base_path == tmp_path

    lesson0 = coll.lessons[0]
    assert lesson0.title == "Basic Types"
    assert lesson0.spec_path == "01-basic.tex"
    assert lesson0.annotation == "Z starts with **basic types**."
    assert lesson0.highlights == ["Basic Types"]
    assert lesson0.order == 0

    lesson1 = coll.lessons[1]
    assert lesson1.order == 1
    assert lesson1.highlights == ["State"]


def test_parse_missing_title(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        """\
[collection]
description = "No title"

[[lessons]]
title = "Lesson 1"
spec = "01.tex"
""",
    )
    with pytest.raises(ValueError, match=r"collection\.title"):
        parse_manifest(manifest)


def test_parse_empty_lessons(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        """\
[collection]
title = "Empty"
""",
    )
    with pytest.raises(ValueError, match="at least one"):
        parse_manifest(manifest)


def test_parse_lesson_missing_spec(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        """\
[collection]
title = "Test"

[[lessons]]
title = "No Spec"
""",
    )
    with pytest.raises(ValueError, match="missing spec"):
        parse_manifest(manifest)


def test_parse_lesson_missing_title(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        """\
[collection]
title = "Test"

[[lessons]]
spec = "01.tex"
""",
    )
    with pytest.raises(ValueError, match="missing title"):
        parse_manifest(manifest)


def test_parse_optional_fields_default(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        """\
[collection]
title = "Minimal"

[[lessons]]
title = "Lesson 1"
spec = "01.tex"
""",
    )
    coll = parse_manifest(manifest)
    assert coll.description == ""
    assert coll.lessons[0].annotation == ""
    assert coll.lessons[0].highlights == []


def test_parse_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        parse_manifest(tmp_path / "nonexistent.toml")
