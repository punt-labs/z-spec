"""Generate and verify the ``*-dev.md`` command twins.

Each prod command (``commands/<c>.md``, excluding ``*-dev.md``) has a dev twin
(``commands/<c>-dev.md``) that is identical except it lives in the ``z-spec-dev``
plugin namespace: MCP tool references gain the ``-dev`` plugin suffix and every
``/z-spec:<cmd>`` self-reference becomes ``/z-spec-dev:<cmd>-dev``.

Run as ``python tools/gen_dev_commands.py <commands-dir> [--check]``:
``--write`` (default) rewrites the twins; ``--check`` exits 1 if any committed
twin differs from what the current prod source would produce (drift).

The dev plugin name carries a hyphen (``z-spec`` -> ``z-spec-dev``), matching the
``hooks/hooks.json`` PostToolUse matcher ``mcp__(plugin_z-spec(-dev)?_)?zspec__.*``
and the working ``biff-dev`` reference. An underscore would break that matcher.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DEV_SUFFIX = "-dev"
PROD_MCP_PREFIX = "mcp__plugin_z-spec_zspec__"
DEV_MCP_PREFIX = "mcp__plugin_z-spec-dev_zspec__"

# A z-spec slash command: /z-spec:<name> where <name> is lowercase words joined
# by single hyphens (b-animate, code2model, check). The trailing (?![\w-]) stops
# the match before an already-hyphenated tail so it cannot re-consume output.
SELF_REF = re.compile(r"/z-spec:([a-z0-9]+(?:-[a-z0-9]+)*)(?![\w-])")


def _to_dev(text: str) -> str:
    """Return prod command text rewritten into the dev namespace."""
    text = text.replace(PROD_MCP_PREFIX, DEV_MCP_PREFIX)
    return SELF_REF.sub(r"/z-spec-dev:\1-dev", text)


def _prod_commands(commands_dir: Path) -> list[Path]:
    """Return the prod command files, sorted, excluding the dev twins."""
    return sorted(
        p for p in commands_dir.glob("*.md") if not p.stem.endswith(DEV_SUFFIX)
    )


def _dev_path(prod: Path) -> Path:
    """Return the dev-twin path for a prod command file."""
    return prod.with_name(f"{prod.stem}{DEV_SUFFIX}.md")


def _write(commands_dir: Path) -> int:
    """Generate every dev twin. Return 0."""
    for prod in _prod_commands(commands_dir):
        dev = _dev_path(prod)
        dev.write_text(_to_dev(prod.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"wrote {dev.name}")
    return 0


def _check(commands_dir: Path) -> int:
    """Return 1 if any committed twin is missing or stale, else 0."""
    drift: list[str] = []
    for prod in _prod_commands(commands_dir):
        dev = _dev_path(prod)
        want = _to_dev(prod.read_text(encoding="utf-8"))
        if not dev.exists():
            drift.append(f"{dev.name}: missing (run `make gen-dev-commands`)")
        elif dev.read_text(encoding="utf-8") != want:
            drift.append(f"{dev.name}: stale (run `make gen-dev-commands`)")
    if drift:
        for line in drift:
            print(f"gen-dev-commands: {line}", file=sys.stderr)
        return 1
    print(f"gen-dev-commands: {len(_prod_commands(commands_dir))} twins in sync")
    return 0


def main(argv: list[str]) -> int:
    """Dispatch to write or check. Return the process exit code."""
    args = [a for a in argv if a != "--write"]
    check = "--check" in args
    positional = [a for a in args if a != "--check"]
    if len(positional) != 1:
        print(
            "usage: gen_dev_commands.py <commands-dir> [--check]",
            file=sys.stderr,
        )
        return 2
    commands_dir = Path(positional[0])
    if not commands_dir.is_dir():
        print(
            f"gen-dev-commands: {commands_dir}: not a directory",
            file=sys.stderr,
        )
        return 2
    return _check(commands_dir) if check else _write(commands_dir)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
