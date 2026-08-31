"""Generate and verify the ``*-dev.md`` command twins.

Each prod command (``plugin/commands/<c>.md``, excluding ``*-dev.md``) has a dev
twin (``plugin/commands/<c>-dev.md``) that is identical except it lives in the
``z-spec-dev`` plugin namespace: MCP tool references gain the ``-dev`` plugin
suffix and every ``/z-spec:<cmd>`` self-reference becomes
``/z-spec-dev:<cmd>-dev``.

Run as ``python tools/gen_dev_commands.py <commands-dir> [--check]``:
``--write`` (default) rewrites the twins; ``--check`` exits 1 if any committed
twin differs from what the current prod source would produce (drift).

The dev plugin name carries a hyphen (``z-spec`` -> ``z-spec-dev``), matching the
``plugin/hooks/hooks.json`` PostToolUse matcher
``mcp__(plugin_z-spec(-dev)?_)?zspec__.*``
and the working ``biff-dev`` reference. An underscore would break that matcher.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DEV_SUFFIX = "-dev"
DEV_PLUGIN_NAME = "z-spec-dev"
PROD_PLUGIN_NAME = "z-spec"
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


def _orphan_twins(commands_dir: Path) -> list[Path]:
    """Return dev twins whose prod source no longer exists (stale after a
    prod command is renamed or deleted)."""
    prod_stems = {p.stem for p in _prod_commands(commands_dir)}
    return sorted(
        twin
        for twin in commands_dir.glob(f"*{DEV_SUFFIX}.md")
        if twin.stem[: -len(DEV_SUFFIX)] not in prod_stems
    )


def _write(commands_dir: Path) -> int:
    """Generate every dev twin. Return 0."""
    for prod in _prod_commands(commands_dir):
        dev = _dev_path(prod)
        dev.write_text(_to_dev(prod.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"wrote {dev.name}")
    for orphan in _orphan_twins(commands_dir):
        orphan.unlink()
        print(f"removed orphan {orphan.name}")
    return 0


def _plugin_name(commands_dir: Path) -> str:
    """Return the plugin name from the manifest beside the commands dir."""
    manifest = commands_dir.parent / ".claude-plugin" / "plugin.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    name = data["name"]
    if not isinstance(name, str):
        raise TypeError(f"{manifest}: plugin name is not a string: {name!r}")
    return name


def _check_prod(commands_dir: Path) -> int:
    """Return 1 if any dev twin survives in a prod-swapped tree, else 0.

    The release swap renames the plugin to prod and deletes every twin;
    a leftover ``*-dev.md`` there is real drift, and demanding the twins
    back (the dev-tree check) would fail every release PR.
    """
    leftovers = sorted(commands_dir.glob(f"*{DEV_SUFFIX}.md"))
    if leftovers:
        for twin in leftovers:
            print(
                f"gen-dev-commands: {twin.name}: present in a prod-swapped "
                "tree (the release swap must delete every dev twin)",
                file=sys.stderr,
            )
        return 1
    print(
        f"gen-dev-commands: prod tree, {len(_prod_commands(commands_dir))} "
        "commands, no dev twins (correct)"
    )
    return 0


def _check(commands_dir: Path) -> int:
    """Gate the tree: 0 healthy, 1 twin drift, 2 unreadable/unknown state."""
    try:
        name = _plugin_name(commands_dir)
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        # This tool is a gate: a manifest it cannot read is a failure to
        # report cleanly (exit 2), never a traceback that CI renders as a
        # generic crash.
        print(
            f"gen-dev-commands: cannot read the plugin manifest beside "
            f"{commands_dir}: {exc}",
            file=sys.stderr,
        )
        return 2
    if name == PROD_PLUGIN_NAME:
        return _check_prod(commands_dir)
    if name != DEV_PLUGIN_NAME:
        print(
            f"gen-dev-commands: unknown plugin name {name!r} -- expected "
            f"{DEV_PLUGIN_NAME!r} (dev tree) or {PROD_PLUGIN_NAME!r} "
            "(release-swapped tree)",
            file=sys.stderr,
        )
        return 2
    drift: list[str] = []
    for prod in _prod_commands(commands_dir):
        dev = _dev_path(prod)
        want = _to_dev(prod.read_text(encoding="utf-8"))
        if not dev.exists():
            drift.append(f"{dev.name}: missing (run `make gen-dev-commands`)")
        elif dev.read_text(encoding="utf-8") != want:
            drift.append(f"{dev.name}: stale (run `make gen-dev-commands`)")
    for orphan in _orphan_twins(commands_dir):
        drift.append(
            f"{orphan.name}: orphaned, no prod source (run `make gen-dev-commands`)"
        )
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
            "usage: gen_dev_commands.py <commands-dir> [--write | --check]",
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
