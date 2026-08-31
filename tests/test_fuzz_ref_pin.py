"""The pinned fuzz commit must agree across every copy that carries it.

FUZZ_REF is duplicated verbatim in install.sh and in the plugin commands
that clone or curl a specific Spivoxity/fuzz commit, because each runs its
own ``git checkout`` or ``curl``. A comment beside every copy asks the next
editor to bump the others in lockstep — that is an instruction, not a gate.
This test is the gate: it fails the moment any one copy drifts.

The pin sites are discovered, not hard-listed: the working tree carries
generated ``-dev`` twins of the plugin commands, and a release tree does
not (the prod swap deletes them), so a fixed file list is wrong in one
tree or the other. Discovery scans install.sh plus every
``plugin/commands/*.md`` and gates whatever actually carries a pin, while
a required-minimum set keeps the discovery itself honest — an empty scan
can never pass vacuously.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
# Full 40-hex only: a truncated SHA that happened to agree across files
# would satisfy an any-length pattern while weakening the pin.
_FULL_SHA: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{40}")
_LOOSE_PATTERN: Final[re.Pattern[str]] = re.compile(r'FUZZ_REF="([^"]*)"')

# Files that must carry a pin in every tree, dev or release-swapped.
_REQUIRED: Final[frozenset[str]] = frozenset(
    {"install.sh", "plugin/commands/setup.md", "plugin/commands/code2model.md"}
)


def _pin_sites() -> dict[str, list[str]]:
    candidates = [_REPO_ROOT / "install.sh"]
    candidates.extend(sorted((_REPO_ROOT / "plugin" / "commands").glob("*.md")))
    sites: dict[str, list[str]] = {}
    for path in candidates:
        text = path.read_text(encoding="utf-8")
        loose = _LOOSE_PATTERN.findall(text)
        if loose:
            sites[str(path.relative_to(_REPO_ROOT))] = loose
    return sites


def test_fuzz_ref_is_identical_across_every_pinned_file() -> None:
    sites = _pin_sites()

    missing = _REQUIRED - sites.keys()
    assert not missing, f"expected FUZZ_REF pins in {sorted(missing)} -- none found"

    for name, values in sites.items():
        assert len(values) == 1, (
            f"{name}: {len(values)} FUZZ_REF assignments -- exactly one per file, "
            "or the gate can read the wrong one and miss real drift"
        )
        assert _FULL_SHA.fullmatch(values[0]), (
            f"{name}: FUZZ_REF is not a full 40-hex commit SHA: {values[0]!r}"
        )

    refs = {name: values[0] for name, values in sites.items()}
    assert len(set(refs.values())) == 1, (
        "FUZZ_REF has drifted between the pinned copies -- bump every one "
        f"to the same commit: {refs}"
    )
