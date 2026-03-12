"""LaTeX Z specification parser → SpecModel."""

from __future__ import annotations

import re
from pathlib import Path

from punt_zspec.types import BlockKind, SpecModel, ZBlock

# ---------------------------------------------------------------------------
# LaTeX → Unicode translation table (BMP-safe)
# ---------------------------------------------------------------------------

LATEX_TO_UNICODE: dict[str, str] = {
    r"\nat": "ℕ",
    r"\num": "ℤ",
    r"\real": "ℝ",
    r"\power": "ℙ",
    r"\finset": "F",
    r"\seq": "seq",
    r"\cross": "×",
    r"\fun": "→",
    r"\pfun": "⇸",
    r"\bij": "⤖",
    r"\pinj": "⤔",
    r"\surj": "↠",
    r"\rel": "↔",
    r"\in": "∈",
    r"\notin": "∉",
    r"\subseteq": "⊆",
    r"\subset": "⊂",
    r"\cup": "∪",
    r"\cap": "∩",
    r"\setminus": "∖",
    r"\emptyset": "∅",
    r"\langle": "⟨",
    r"\rangle": "⟩",
    r"\forall": "∀",
    r"\exists": "∃",
    r"\land": "∧",
    r"\lor": "∨",
    r"\lnot": "¬",
    r"\implies": "⇒",
    r"\iff": "⇔",
    r"\Delta": "Δ",
    r"\Xi": "Ξ",
    r"\dom": "dom",
    r"\ran": "ran",
    r"\dres": "◁",
    r"\rres": "▷",
    r"\ndres": "⩤",
    r"\nrres": "⩥",
    r"\oplus": "⊕",
    r"\mapsto": "↦",
    r"\neq": "≠",
    r"\leq": "≤",
    r"\geq": "≥",
    r"\#": "#",
    r"\theta": "θ",
    r"\upto": "‥",
    r"\cat": "⁀",
    r"\semi": "⨟",
    r"\pipe": "≫",
    r"\project": "↾",
}

# Build regex: sort by length (longest first) to avoid partial matches.
# Each command is followed by a word boundary or non-alpha to avoid matching
# prefixes (e.g., \natural should not match \nat + ural).
_SORTED_COMMANDS = sorted(LATEX_TO_UNICODE.keys(), key=len, reverse=True)
_LATEX_PATTERN = re.compile(
    "|".join(re.escape(cmd) + r"(?![a-zA-Z])" for cmd in _SORTED_COMMANDS)
)


def latex_to_unicode(text: str) -> str:
    """Convert LaTeX Z commands to Unicode symbols."""
    result = _LATEX_PATTERN.sub(lambda m: LATEX_TO_UNICODE[m.group(0)], text)
    # Prime suffix: var' -> var-prime (but not inside LaTeX commands)
    result = re.sub(r"([a-zA-Z])'+", lambda m: m.group(0).replace("'", "′"), result)
    return result


def normalize_z_body(text: str) -> str:
    """Normalize layout tokens in Z block body text."""
    # Remove % comment lines
    lines = [line for line in text.split("\n") if not line.strip().startswith("%")]
    text = "\n".join(lines)
    # Replace \\ and \\[<len>] with newlines
    text = re.sub(r"\\\\(\[[^\]]*\])?", "\n", text)
    # Replace \quad~ and \quad with 2-space indent
    text = text.replace(r"\quad~", "  ").replace(r"\quad", "  ")
    # Convert LaTeX commands to Unicode
    text = latex_to_unicode(text)
    # Clean up whitespace: rstrip lines (preserve leading indent), drop blanks
    lines = [line.rstrip() for line in text.split("\n")]
    lines = [line for line in lines if line.strip()]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Schema box rendering
# ---------------------------------------------------------------------------

_BOX_WIDTH = 60
_NAME_EXTRA = 5  # extra dashes for name line (proportional font compensation)


def render_schema_box(block: ZBlock) -> str:
    """Render a Z block as a Unicode open-right box."""
    decl = normalize_z_body(block.declarations)
    pred = normalize_z_body(block.predicates)

    if block.name:
        top = f"┌─ {block.name} " + "─" * (_BOX_WIDTH + _NAME_EXTRA)
    else:
        top = "┌" + "─" * (_BOX_WIDTH + _NAME_EXTRA + 3)

    lines = [top]
    for line in decl.split("\n"):
        if line:
            lines.append(f"│ {line}")

    if pred:
        lines.append("├" + "─" * _BOX_WIDTH)
        for line in pred.split("\n"):
            if line:
                lines.append(f"│ {line}")

    lines.append("└" + "─" * _BOX_WIDTH)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Spec parser
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(r"\\section\{([^}]+)\}")
_TITLE_RE = re.compile(r"\\title\{([^}]+)\}")

# Block patterns — capture the begin tag line number
_BLOCK_PATTERNS: list[tuple[BlockKind, re.Pattern[str]]] = [
    (
        BlockKind.schema,
        re.compile(
            r"\\begin\{schema\}\{([^}]+)\}(.*?)\\end\{schema\}",
            re.DOTALL,
        ),
    ),
    (
        BlockKind.zed,
        re.compile(r"\\begin\{zed\}(.*?)\\end\{zed\}", re.DOTALL),
    ),
    (
        BlockKind.axdef,
        re.compile(r"\\begin\{axdef\}(.*?)\\end\{axdef\}", re.DOTALL),
    ),
    (
        BlockKind.gendef,
        re.compile(
            r"\\begin\{gendef\}(?:\[([^\]]*)\])?(.*?)\\end\{gendef\}",
            re.DOTALL,
        ),
    ),
]


def _line_number_at(text: str, pos: int) -> int:
    """Return 1-based line number for a character position."""
    return text[:pos].count("\n") + 1


def _split_where(body: str) -> tuple[str, str]:
    r"""Split a Z block body at \where into (declarations, predicates)."""
    # Find \where not inside a comment
    parts = re.split(r"\\where\b", body, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return body.strip(), ""


def _current_section(
    text: str, pos: int, section_positions: list[tuple[int, str]]
) -> str:
    """Find which section a position falls in."""
    current = ""
    for sec_pos, sec_name in section_positions:
        if sec_pos <= pos:
            current = sec_name
        else:
            break
    return current


def parse_spec(path: Path) -> SpecModel:
    """Parse a .tex Z specification into a SpecModel."""
    text = path.read_text(encoding="utf-8")

    # Extract title
    title_match = _TITLE_RE.search(text)
    title = title_match.group(1) if title_match else path.stem

    # Extract sections with positions
    section_positions: list[tuple[int, str]] = []
    sections: list[str] = []
    for m in _SECTION_RE.finditer(text):
        name = m.group(1)
        section_positions.append((m.start(), name))
        sections.append(name)

    # Extract blocks
    blocks: list[ZBlock] = []

    for kind, pattern in _BLOCK_PATTERNS:
        for m in pattern.finditer(text):
            line_num = _line_number_at(text, m.start())
            section = _current_section(text, m.start(), section_positions)

            if kind == BlockKind.schema:
                name = m.group(1)
                body = m.group(2)
                decls, preds = _split_where(body)
            elif kind == BlockKind.gendef:
                # gendef may have optional type params in []
                name = m.group(1) or ""
                body = m.group(2)
                decls, preds = _split_where(body)
            elif kind == BlockKind.zed:
                name = ""
                body = m.group(1)
                decls = body.strip()
                preds = ""
            else:  # axdef
                name = ""
                body = m.group(1)
                decls, preds = _split_where(body)

            blocks.append(
                ZBlock(
                    kind=kind,
                    name=name,
                    declarations=decls,
                    predicates=preds,
                    section=section,
                    line_number=line_num,
                )
            )

    # Sort blocks by line number
    blocks.sort(key=lambda b: b.line_number)

    return SpecModel(
        title=title,
        sections=sections,
        blocks=blocks,
        source_path=str(path),
    )
