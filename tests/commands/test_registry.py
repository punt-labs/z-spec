"""Tests for punt_zspec.commands.registry."""

from __future__ import annotations

from punt_zspec.commands.registry import CAPABILITIES


def test_capabilities_is_non_empty() -> None:
    assert CAPABILITIES


def test_canonical_names_are_unique() -> None:
    names = [cap.name for cap in CAPABILITIES]
    assert len(names) == len(set(names))


def test_cli_verbs_are_unique() -> None:
    verbs = [cap.cli_verb for cap in CAPABILITIES]
    assert len(verbs) == len(set(verbs))


def test_mcp_tool_names_are_unique() -> None:
    tools = [cap.mcp_tool for cap in CAPABILITIES]
    assert len(tools) == len(set(tools))


def test_every_command_is_a_class() -> None:
    assert all(isinstance(cap.command, type) for cap in CAPABILITIES)
