"""Wrapper for the fuzz type-checker."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from punt_zspec.types import FuzzError, FuzzResult

# Error pattern: "file", line N, col N: message
_ERROR_RE = re.compile(r'"[^"]*",\s*line\s+(\d+),\s*col\s+(\d+):\s*(.*)')


def resolve_fuzz() -> Path | None:
    """Find the fuzz binary. Check $FUZZ, then PATH."""
    env = os.environ.get("FUZZ")
    if env:
        p = Path(env)
        if p.is_file():
            return p
    found = shutil.which("fuzz")
    if found:
        return Path(found)
    return None


def run_fuzz(tex_path: Path, binary: Path) -> FuzzResult:
    """Run fuzz -t on a Z specification and return structured result."""
    result = subprocess.run(
        [str(binary), "-t", str(tex_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )

    raw = result.stdout + result.stderr

    if result.returncode == 0:
        return FuzzResult(ok=True, raw_output=raw)

    errors: list[FuzzError] = []
    for m in _ERROR_RE.finditer(raw):
        errors.append(
            FuzzError(
                line=int(m.group(1)),
                column=int(m.group(2)),
                message=m.group(3).strip(),
            )
        )

    # If no structured errors found, create one from raw output
    if not errors and raw.strip():
        errors.append(FuzzError(line=0, column=0, message=raw.strip()[:200]))

    return FuzzResult(ok=False, errors=errors, raw_output=raw)
