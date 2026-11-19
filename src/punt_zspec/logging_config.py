"""Configure z-spec diagnostics for its process entry points.

Library modules only declare ``logging.getLogger(__name__)``; the CLI and the
MCP server call :func:`configure_logging` once at startup, which routes every
record to the private, redacted, rotated file the shared ``punt-observe``
package owns at ``~/.punt-labs/z-spec/logs/z-spec.log``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from punt_observe.logging import (
    LoggingSetupError,
    configure_logging as _configure_logging,
)

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["TOOL", "LoggingSetupError", "Role", "configure_logging"]

TOOL = "z-spec"

type Role = Literal["cli", "mcp"]


def configure_logging(role: Role, *, stderr_level: str = "WARNING") -> Path:
    """Configure a private durable sink and optional terminal diagnostics.

    stderr only carries records at ``stderr_level`` or above; stdout is never
    a log sink, so the MCP stdio transport stays clean.

    Args:
        role: The entry point configuring the process.
        stderr_level: The lowest level echoed to stderr.

    Returns:
        The path of the active log file.

    Raises:
        LoggingSetupError: The private log directory or file cannot be secured.
    """
    return _configure_logging(TOOL, role, stderr_level=stderr_level)
