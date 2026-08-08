"""Contracts the shipped command prompts must satisfy.

`commands/*.md` is the largest surface this project ships and, until now, the
only untested one: `make check` gated the Python and the Z corpus, while
`check-dev-commands` verified that each `-dev` twin *matched* its prod source.
Two identical copies of a wrong protocol satisfy that gate perfectly — it tests
synchronisation, not correctness.

A prompt is executed by a model, so most of its content cannot be asserted
deterministically. What can be asserted is *internal consistency*: a prompt that
both specifies a wire protocol and embeds a reference implementation of it must
not contradict itself. That is the class of defect these tests cover, and it is
the class that produced the oracle verdict-envelope bug.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

import pytest

COMMANDS = Path(__file__).resolve().parents[2] / "commands"
DOCS_PRD = Path(__file__).resolve().parents[2] / "docs" / "prd"

_FENCE = re.compile(r"^```(\w+)\n(.*?)^```", re.MULTILINE | re.DOTALL)
_JSON_COMMENT = re.compile(r"^\s*//.*$", re.MULTILINE)
# Schema blocks use <angle-bracket> placeholders where a concrete example would
# carry a literal. Substituting a string keeps the block parseable, so a
# template and a worked example can be checked by the same assertions — the
# structural keys under test are literals in both. Quoted placeholders are
# replaced first; substituting the bare form inside its own quotes would
# otherwise produce `""?""`.
_QUOTED_PLACEHOLDER = re.compile(r'"<[^<>]*>"')
_BARE_PLACEHOLDER = re.compile(r"<[^<>\s][^<>]*>")


def _blocks(path: Path, lang: str) -> list[str]:
    """Return the bodies of every ```<lang> fenced block in ``path``."""
    return [body for tag, body in _FENCE.findall(path.read_text()) if tag == lang]


def _json_objects(body: str) -> list[dict[str, object]]:
    """Parse a ```json block into the objects it declares.

    Two shapes appear in the prompts and both are legitimate: a single
    pretty-printed document (audit, partition) and an NDJSON transcript with one
    object per line (the oracle wire protocol). Try the whole block first, then
    fall back to line-by-line. `//` comments annotate the examples throughout and
    are stripped, since JSON does not permit them.
    """
    text = _JSON_COMMENT.sub("", body)
    text = _QUOTED_PLACEHOLDER.sub('"?"', text)
    text = _BARE_PLACEHOLDER.sub('"?"', text).strip()
    if not text:
        return []

    try:
        document: object = json.loads(text)
    except json.JSONDecodeError:
        pass
    else:
        return (
            [cast("dict[str, object]", document)] if isinstance(document, dict) else []
        )

    objects: list[dict[str, object]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parsed: object = json.loads(stripped)
        if isinstance(parsed, dict):
            objects.append(cast("dict[str, object]", parsed))
    return objects


def _oracle_outputs(objects: list[dict[str, object]]) -> list[dict[str, object]]:
    """Oracle→harness lines, i.e. everything that is not a harness→oracle command."""
    return [o for o in objects if "op" not in o]


# --- every prompt's JSON examples must actually be JSON ----------------------


@pytest.mark.parametrize("path", sorted(COMMANDS.glob("*.md")), ids=lambda p: p.name)
def test_json_examples_parse(path: Path) -> None:
    """A malformed example teaches the model a malformed format."""
    for body in _blocks(path, "json"):
        _json_objects(body)


# --- the oracle protocol must distinguish a rejection from a no-op success ---


def _oracle_protocol_sources() -> list[Path]:
    return [
        COMMANDS / "oracle.md",
        COMMANDS / "oracle-dev.md",
        DOCS_PRD / "z-oracle.md",
    ]


@pytest.mark.parametrize("path", _oracle_protocol_sources(), ids=lambda p: p.name)
def test_oracle_output_carries_a_verdict(path: Path) -> None:
    """Every oracle→harness example must say whether the operation was accepted.

    Without a verdict the wire is ambiguous: an operation rejected for violating
    its precondition and an operation that succeeded while changing nothing emit
    byte-identical lines. A property-based driver comparing traces then cannot
    assert the one property the oracle exists to establish — that the
    implementation rejects exactly what the specification rejects.
    """
    outputs = [
        obj
        for body in _blocks(path, "json")
        for obj in _oracle_outputs(_json_objects(body))
    ]
    assert outputs, f"{path.name} defines no oracle output examples"
    for obj in outputs:
        assert "ok" in obj, f"{path.name}: oracle output {obj} carries no verdict"
        assert "state" in obj, f"{path.name}: oracle output {obj} has no state envelope"


@pytest.mark.parametrize("path", _oracle_protocol_sources(), ids=lambda p: p.name)
def test_oracle_rejection_example_names_the_failed_precondition(path: Path) -> None:
    """A driver that only learns *that* a step was rejected cannot report why."""
    rejections = [
        obj
        for body in _blocks(path, "json")
        for obj in _oracle_outputs(_json_objects(body))
        if obj.get("ok") is False
    ]
    assert rejections, f"{path.name} shows no rejected-operation example"
    for obj in rejections:
        assert obj.get("reason"), f"{path.name}: rejection {obj} gives no reason"
