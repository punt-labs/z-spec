"""Tests for punt_zspec.commands.registry."""

from __future__ import annotations

from collections import Counter

from punt_zspec.commands.registry import CAPABILITIES


def test_capabilities_is_non_empty() -> None:
    assert CAPABILITIES


def test_canonical_names_are_unique() -> None:
    names = [cap.name for cap in CAPABILITIES]
    assert len(names) == len(set(names))


def test_cli_verbs_are_unique() -> None:
    verbs = [cap.cli_verb for cap in CAPABILITIES]
    assert len(verbs) == len(set(verbs))


def test_only_the_enablement_verbs_share_an_mcp_tool() -> None:
    # §2.14: enable and disable are two CLI verbs but one MCP tool taking an
    # action argument. Every other capability owns its tool name outright.
    counts = Counter(cap.mcp_tool for cap in CAPABILITIES)

    assert {tool for tool, n in counts.items() if n > 1} == {"enablement"}
    assert {c.name for c in CAPABILITIES if c.mcp_tool == "enablement"} == {
        "enable",
        "disable",
    }


def test_every_command_is_a_class() -> None:
    assert all(isinstance(cap.command, type) for cap in CAPABILITIES)
