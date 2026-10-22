"""Readers for install.sh's ProB pins, shared by the install and workflow tests.

install.sh and .github/workflows/test.yml each carry the ProB version, the
per-OS SHA-256 pins, and the curl flag set. The tests that gate their parity
read install.sh through this one module, so both sides of every parity
assertion come from the same parser.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Final

INSTALL_SH: Final[Path] = Path(__file__).resolve().parent.parent / "install.sh"
_PROB_VERSION: Final[re.Pattern[str]] = re.compile(r"^PROB_VERSION=(\S+)$", re.M)
_PIN: Final[re.Pattern[str]] = re.compile(
    r'^(PROB_SHA256_(?:LINUX|MACOS))="([^"]*)"$', re.M
)
_SET_FLAGS: Final[re.Pattern[str]] = re.compile(
    r"^\s*set -- (-fL(?:[^\n]*\\\n)*[^\n]*)$", re.M
)


def prob_version() -> str:
    """Return install.sh's top-level PROB_VERSION value."""
    found = [m.group(1) for m in _PROB_VERSION.finditer(INSTALL_SH.read_text("utf-8"))]
    assert len(found) == 1, f"install.sh: expected one PROB_VERSION=, got {found}"
    return found[0]


def pins() -> dict[str, str]:
    """Return install.sh's PROB_SHA256_LINUX / PROB_SHA256_MACOS values."""
    found = [
        (m.group(1), m.group(2)) for m in _PIN.finditer(INSTALL_SH.read_text("utf-8"))
    ]
    names = sorted(name for name, _ in found)
    assert names == ["PROB_SHA256_LINUX", "PROB_SHA256_MACOS"], (
        f"install.sh must assign PROB_SHA256_LINUX and PROB_SHA256_MACOS once "
        f"each, found {names}"
    )
    return dict(found)


def install_probcli_source() -> str:
    """Return install.sh from PROB_VERSION= through install_probcli's ``)``."""
    lines = INSTALL_SH.read_text(encoding="utf-8").splitlines()
    numbered = list(enumerate(lines))
    start = next((i for i, ln in numbered if ln.startswith("PROB_VERSION=")), None)
    assert start is not None, "install.sh: no line starting with 'PROB_VERSION='"
    opener = next((i for i, ln in numbered if ln == "install_probcli() ("), None)
    assert opener is not None, "install.sh: no line 'install_probcli() ('"
    assert opener > start, "install.sh: install_probcli() precedes PROB_VERSION="
    end = next((i for i in range(opener, len(lines)) if lines[i] == ")"), None)
    assert end is not None, "install.sh: install_probcli() has no closing ')' line"
    source = "\n".join(lines[start : end + 1]) + "\n"
    assert "resolve_probcli_path() {" in source, (
        "install.sh: resolve_probcli_path() is no longer between PROB_VERSION= and "
        "install_probcli(), so the sliced function would call an undefined helper"
    )
    return source


def fetch_flags() -> list[str]:
    """Return the fixed curl flags install_probcli builds with ``set --``."""
    match = _SET_FLAGS.search(install_probcli_source())
    assert match, "install_probcli has no `set -- -fL ...` curl flag list"
    return shlex.split(match.group(1).replace("\\\n", " "))
