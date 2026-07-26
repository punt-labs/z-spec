"""Parity guard: every capability is exposed on both the CLI and MCP surfaces."""

from __future__ import annotations

import click
import pytest
from typer.main import get_command

from punt_zspec.__main__ import app
from punt_zspec.commands.registry import CAPABILITIES, Capability
from punt_zspec.server import mcp

# The CLI carries one verb with no capability: the server launcher.
_CLI_ONLY: frozenset[str] = frozenset({"mcp"})


def _cli_verbs() -> set[str]:
    group = get_command(app)
    assert isinstance(group, click.Group)  # a multi-command app is a click.Group
    return set(group.commands.keys())


def _mcp_tools() -> set[str]:
    return {t.name for t in mcp._tool_manager.list_tools()}  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize("cap", CAPABILITIES, ids=lambda c: c.name)
def test_capability_has_both_surfaces(cap: Capability) -> None:
    assert cap.cli_verb in _cli_verbs(), f"{cap.name}: no CLI verb {cap.cli_verb!r}"
    assert cap.mcp_tool in _mcp_tools(), f"{cap.name}: no MCP tool {cap.mcp_tool!r}"


def test_no_orphan_cli_verbs() -> None:
    registered = {c.cli_verb for c in CAPABILITIES} | _CLI_ONLY
    assert _cli_verbs() == registered


def test_no_orphan_mcp_tools() -> None:
    assert _mcp_tools() == {c.mcp_tool for c in CAPABILITIES}


def test_commands_are_final() -> None:
    for cap in CAPABILITIES:
        assert getattr(cap.command, "__final__", False), f"{cap.name} not @final"
