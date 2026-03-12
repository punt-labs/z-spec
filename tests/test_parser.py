"""Tests for punt_zspec.parser."""

from __future__ import annotations

from pathlib import Path

from punt_zspec.parser import (
    latex_to_unicode,
    normalize_z_body,
    parse_spec,
    render_schema_box,
)
from punt_zspec.types import BlockKind, ZBlock


def test_latex_to_unicode_basic() -> None:
    assert latex_to_unicode(r"\nat") == "ℕ"
    assert latex_to_unicode(r"\num") == "ℤ"
    assert latex_to_unicode(r"\in") == "∈"
    assert latex_to_unicode(r"\emptyset") == "∅"


def test_latex_to_unicode_no_partial_match() -> None:
    # \natural should NOT match \nat + ural
    result = latex_to_unicode(r"\natural")
    assert result == r"\natural"


def test_latex_to_unicode_combined() -> None:
    result = latex_to_unicode(r"x : \nat \cross \nat")
    assert result == "x : ℕ × ℕ"


def test_latex_to_unicode_prime() -> None:
    assert latex_to_unicode("x'") == "x′"
    assert latex_to_unicode("state'") == "state′"


def test_normalize_z_body_strips_comments() -> None:
    body = "x : \\nat\n% this is a comment\ny : \\num"
    result = normalize_z_body(body)
    assert "comment" not in result
    assert "x : ℕ" in result
    assert "y : ℤ" in result


def test_normalize_z_body_replaces_linebreaks() -> None:
    body = r"x : \nat \\ y : \num"
    result = normalize_z_body(body)
    lines = result.split("\n")
    assert len(lines) == 2


def test_normalize_z_body_replaces_quad() -> None:
    body = r"\quad~x : \nat"
    result = normalize_z_body(body)
    assert result.startswith("  x")


def test_render_schema_box_with_predicates() -> None:
    block = ZBlock(
        kind=BlockKind.schema,
        name="State",
        declarations=r"x : \nat",
        predicates=r"x \leq 10",
        section="State",
        line_number=1,
    )
    box = render_schema_box(block)
    assert "┌─ State" in box
    assert "│ x : ℕ" in box
    assert "├" in box
    assert "│ x ≤ 10" in box
    assert "└" in box


def test_render_schema_box_without_predicates() -> None:
    block = ZBlock(
        kind=BlockKind.zed,
        name="",
        declarations=r"Color ::= red | green | blue",
        predicates="",
        section="Types",
        line_number=1,
    )
    box = render_schema_box(block)
    assert "┌" in box
    assert "├" not in box  # no predicates → no mid-rule
    assert "│ Color ::= red | green | blue" in box
    assert "└" in box


def test_parse_spec_extracts_blocks(tmp_path: Path) -> None:
    tex = r"""
\documentclass{article}
\usepackage{fuzz}
\begin{document}
\title{Test Spec}

\section{Types}

\begin{zed}
  Color ::= red | green | blue
\end{zed}

\section{State}

\begin{schema}{MyState}
  x : \nat
  \where
  x \leq 10
\end{schema}

\section{Constants}

\begin{axdef}
  maxVal : \nat
  \where
  maxVal = 100
\end{axdef}

\end{document}
"""
    spec_file = tmp_path / "test.tex"
    spec_file.write_text(tex)

    spec = parse_spec(spec_file)
    assert spec.title == "Test Spec"
    assert "Types" in spec.sections
    assert "State" in spec.sections
    assert "Constants" in spec.sections

    assert len(spec.blocks) == 3

    # zed block
    zed = spec.blocks[0]
    assert zed.kind == BlockKind.zed
    assert "Color" in zed.declarations
    assert zed.section == "Types"

    # schema block
    schema = spec.blocks[1]
    assert schema.kind == BlockKind.schema
    assert schema.name == "MyState"
    assert r"\nat" in schema.declarations
    assert r"\leq" in schema.predicates
    assert schema.section == "State"

    # axdef block
    axdef = spec.blocks[2]
    assert axdef.kind == BlockKind.axdef
    assert "maxVal" in axdef.declarations
    assert "100" in axdef.predicates
    assert axdef.section == "Constants"


def test_parse_spec_blocks_by_section(tmp_path: Path) -> None:
    tex = r"""
\documentclass{article}
\usepackage{fuzz}
\begin{document}
\title{Group Test}

\section{Types}
\begin{zed}
  A ::= a1 | a2
\end{zed}
\begin{zed}
  B ::= b1 | b2
\end{zed}

\section{State}
\begin{schema}{S}
  x : \nat
  \where
  x = 0
\end{schema}

\end{document}
"""
    spec_file = tmp_path / "group.tex"
    spec_file.write_text(tex)

    spec = parse_spec(spec_file)
    by_section = spec.blocks_by_section()
    assert len(by_section["Types"]) == 2
    assert len(by_section["State"]) == 1


def test_parse_real_spec() -> None:
    """Parse the actual claude-code.tex example if available."""
    path = Path("examples/claude-code.tex")
    if not path.exists():
        return  # skip in CI where examples aren't present

    spec = parse_spec(path)
    assert spec.title == "Claude Code: A Z Specification"
    assert len(spec.blocks) > 10
    assert any(b.kind == BlockKind.schema for b in spec.blocks)
    assert any(b.kind == BlockKind.zed for b in spec.blocks)
