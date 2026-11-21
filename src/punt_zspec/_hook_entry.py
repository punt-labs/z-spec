"""Record PostToolUse formatting diagnostics without loading the CLI."""

from __future__ import annotations

import logging
import signal
import sys
from enum import StrEnum

from punt_zspec.logging_config import DiagnosticLog, LoggingSetupError

logger = logging.getLogger(__name__)


class _Outcome(StrEnum):
    """Record formatter state without logging the tool name or response."""

    formatted = "formatted"
    fallback = "fallback"
    failed = "failed"


def main() -> int:
    """Log one allowlisted formatter outcome, returning a process exit code."""
    args = sys.argv[1:]
    if len(args) != 1:
        return 2
    try:
        outcome = _Outcome(args[0])
    except ValueError:
        return 2
    signal.alarm(1)
    try:
        DiagnosticLog.configure("hook")
        logger.info("Completed PostToolUse formatting via hook: outcome=%s", outcome)
    except LoggingSetupError:
        return 1
    finally:
        signal.alarm(0)
    return 0
