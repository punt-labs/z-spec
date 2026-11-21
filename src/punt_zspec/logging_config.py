"""Configure z-spec diagnostics for its process entry points.

Library modules only declare ``logging.getLogger(__name__)``; each entry
point calls :meth:`DiagnosticLog.configure` at startup, which routes
every record to the private, redacted, rotated file the shared
``punt-observe`` package owns at ``~/.punt-labs/z-spec/logs/z-spec.log``.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import TYPE_CHECKING, Literal, final

from punt_observe.logging import LoggingSetupError, configure_logging

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "POST_TOOL_USE_COMMAND",
    "TOOL",
    "DiagnosticLog",
    "HookOutcome",
    "LoggingSetupError",
    "Role",
]

TOOL = "z-spec"

type Role = Literal["cli", "hook", "mcp"]

POST_TOOL_USE_COMMAND = "_log-post-tool-use"
logger = logging.getLogger(__name__)


class HookOutcome(StrEnum):
    """Allowlisted PostToolUse formatting outcomes, never tool responses."""

    formatted = "formatted"
    fallback = "fallback"
    failed = "failed"


@final
class DiagnosticLog:
    """The one place a z-spec process configures its diagnostics."""

    __slots__ = ()

    @staticmethod
    def role(subcommand: str | None) -> Role:
        """Resolve the logging role from the invoked CLI subcommand."""
        if subcommand == POST_TOOL_USE_COMMAND:
            return "hook"
        return "mcp" if subcommand == "mcp" else "cli"

    @staticmethod
    def post_tool_use(outcome: HookOutcome) -> None:
        """Record the result of formatting a PostToolUse result."""
        logger.info("Completed PostToolUse formatting via hook: outcome=%s", outcome)

    @staticmethod
    def configure(role: Role, *, stderr_level: str = "WARNING") -> Path:
        """Configure a private durable sink and optional terminal diagnostics.

        stderr only carries records at ``stderr_level`` or above; stdout is
        never a log sink, so the MCP stdio transport stays clean.

        Args:
            role: The entry point configuring the process.
            stderr_level: The lowest level echoed to stderr.

        Returns:
            The path of the active log file.

        Raises:
            LoggingSetupError: The home directory cannot be found, or the
                private log directory or file cannot be secured.
        """
        try:
            return configure_logging(TOOL, role, stderr_level=stderr_level)
        except RuntimeError as exc:  # Path.home(): no HOME and no passwd entry
            msg = "cannot locate the home directory"
            raise LoggingSetupError(msg) from exc
