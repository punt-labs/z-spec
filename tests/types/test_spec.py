"""Tests for punt_zspec.types.spec."""

from __future__ import annotations

from punt_zspec.types import BlockKind, SpecModel, ZBlock


def _block(name: str, section: str) -> ZBlock:
    return ZBlock(
        kind=BlockKind.schema,
        name=name,
        declarations="",
        predicates="",
        section=section,
        line_number=1,
    )


def test_blocks_by_section_groups_across_two_sections() -> None:
    a1, a2, b1 = _block("A1", "State"), _block("A2", "State"), _block("B1", "Ops")
    model = SpecModel(
        title="T",
        sections=["State", "Ops"],
        blocks=[a1, a2, b1],
        source_path="s.tex",
    )
    assert model.blocks_by_section() == {"State": [a1, a2], "Ops": [b1]}


def test_blocks_by_section_empty_returns_empty_dict() -> None:
    model = SpecModel(title="T", sections=[], blocks=[], source_path="s.tex")
    assert model.blocks_by_section() == {}


def test_to_dict_serializes_block_kind_to_value() -> None:
    model = SpecModel(
        title="T", sections=["S"], blocks=[_block("A", "S")], source_path="s.tex"
    )
    assert model.to_dict()["blocks"][0]["kind"] == "schema"
