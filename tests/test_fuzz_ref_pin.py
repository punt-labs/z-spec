"""The pinned fuzz commit must agree across every copy that carries it.

FUZZ_REF is duplicated verbatim in install.sh, setup.md, setup-dev.md,
code2model.md, and code2model-dev.md because each runs its own
``git checkout`` or its own ``curl`` against a specific Spivoxity/fuzz
commit. A comment beside every copy asks the next editor to bump the
others in lockstep — that is an instruction, not a gate. This test is
the gate `make check-dev-commands` models for the ``-dev`` twins: it
fails the moment any one copy drifts from the rest.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
_FUZZ_REF_PATTERN: Final[re.Pattern[str]] = re.compile(r'FUZZ_REF="([0-9a-f]+)"')

_PINNED_FILES: Final[tuple[Path, ...]] = (
    _REPO_ROOT / "install.sh",
    _REPO_ROOT / "plugin" / "commands" / "setup.md",
    _REPO_ROOT / "plugin" / "commands" / "setup-dev.md",
    _REPO_ROOT / "plugin" / "commands" / "code2model.md",
    _REPO_ROOT / "plugin" / "commands" / "code2model-dev.md",
)


def _fuzz_ref(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = _FUZZ_REF_PATTERN.search(text)
    assert match, f'{path}: no FUZZ_REF="..." assignment found'
    return match.group(1)


def test_fuzz_ref_is_identical_across_every_pinned_file() -> None:
    refs = {
        str(path.relative_to(_REPO_ROOT)): _fuzz_ref(path) for path in _PINNED_FILES
    }
    distinct = set(refs.values())
    assert len(distinct) == 1, (
        "FUZZ_REF has drifted between the pinned copies -- bump every one "
        f"to the same commit: {refs}"
    )
