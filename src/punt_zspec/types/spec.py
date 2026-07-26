"""Parsed Z specification model: blocks and their enclosing sections."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class BlockKind(StrEnum):
    """Kind of Z notation block."""

    schema = "schema"
    zed = "zed"
    axdef = "axdef"
    gendef = "gendef"


@dataclass(frozen=True)
class ZBlock:
    """A single Z notation block extracted from a .tex file."""

    kind: BlockKind
    name: str  # schema name, or "" for zed/axdef/gendef
    declarations: str  # text before \where (or entire body for zed)
    predicates: str  # text after \where (empty if no \where)
    section: str  # enclosing \section{} title
    line_number: int  # 1-based line number in source


@dataclass(frozen=True)
class SpecModel:
    """Parsed Z specification."""

    title: str
    sections: list[str]
    blocks: list[ZBlock]
    source_path: str

    def blocks_by_section(self) -> dict[str, list[ZBlock]]:
        """Group blocks by their enclosing section."""
        result: dict[str, list[ZBlock]] = {}
        for block in self.blocks:
            result.setdefault(block.section, []).append(block)
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "sections": self.sections,
            "blocks": [
                {
                    "kind": b.kind.value,
                    "name": b.name,
                    "declarations": b.declarations,
                    "predicates": b.predicates,
                    "section": b.section,
                    "line_number": b.line_number,
                }
                for b in self.blocks
            ],
            "source_path": self.source_path,
        }
