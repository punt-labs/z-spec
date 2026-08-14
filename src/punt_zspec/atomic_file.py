"""Serialized, atomic, byte-preserving mutation of a shared host file.

punt-kit ``standards/tool-enable-disable.md`` §2.4 mandates one write contract
for every host file a tool shares with other tools and invocations — the repo
``CLAUDE.md`` import line and the ``.claude/settings.json`` entries alike:
exclusive sibling lock, atomic rename, no newline translation, symlink
resolved, mode preserved.

The correctness is ported (copy, not shared runtime) from the canonical
``ClaudeMdImport`` in ``punt-labs/biff``, which §2.4 names as the reference
implementation.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Self, final

if TYPE_CHECKING:
    from collections.abc import Generator

__all__ = ["AtomicFile"]

_NEW_FILE_MODE = 0o644


@final
class AtomicFile:
    """One host file, read and replaced under an exclusive sibling lock.

    The lock file is the sibling ``.<name>.punt-import.lock``. That name is
    mandated and tool-agnostic: every punt CLI mutating the same host file must
    take the identical lock, or a per-tool lock serializes a tool only against
    itself and leaves the cross-tool lost update in place. Locking the target
    itself is forbidden — the atomic rename replaces its inode, so the lock
    would travel with the dead file (§2.4).
    """

    _path: Path
    _lock_path: Path
    __slots__ = ("_lock_path", "_path")

    def __new__(cls, path: Path) -> Self:
        self = super().__new__(cls)
        # Resolved once because the lock name derives from it: a symlinked
        # CLAUDE.md is one real file under two names, and a name-keyed lock
        # hands two tools reaching that one file two different locks.
        self._path = path.resolve()
        self._lock_path = self._path.parent / f".{self._path.name}.punt-import.lock"
        return self

    @property
    def path(self) -> Path:
        """Return the real host file this instance mutates, symlinks resolved."""
        return self._path

    @contextmanager
    def locked(self) -> Generator[None]:
        """Hold the exclusive sibling lock for a whole read-modify-write.

        Atomic rename prevents a torn file; it does not prevent a lost update —
        two parallel ``enable`` runs would each read the old bytes and the
        second would clobber the first. This serializes them.
        """
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock_path.open("w", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def read(self) -> str:
        """Return the file verbatim, or ``""`` when it does not exist.

        ``newline=""`` disables universal-newline translation so a read/write
        round trip keeps LF, CRLF, and lone-CR endings byte-identical.
        ``errors="surrogateescape"`` keeps a host that is not valid UTF-8
        readable: invalid bytes decode to lone surrogates and :meth:`write`
        restores them, so such a file neither crashes the read nor is corrupted
        on write-back.
        """
        if not self._path.is_file():
            return ""
        return self._path.read_text(
            encoding="utf-8", newline="", errors="surrogateescape"
        )

    def write(self, text: str) -> None:
        """Replace the file's contents with *text* atomically.

        Writes a temp file in the target's own directory, ``fsync``s it, then
        renames it over the target — an interrupted write leaves the original
        untouched. The target was resolved at construction, so the rename
        updates the real file and leaves a symlink pointing at it intact; an
        existing file's mode is preserved.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        mode = (
            stat.S_IMODE(self._path.stat().st_mode)
            if self._path.is_file()
            else _NEW_FILE_MODE
        )
        tmp = self._staged(text)
        try:
            # os.replace preserves the temp's 0600 mkstemp mode, so stamp the
            # intended mode before the rename or an existing 0644 file drops.
            tmp.chmod(mode)
            tmp.replace(self._path)
        except BaseException:
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)
            raise

    def _staged(self, text: str) -> Path:
        """Write *text* to a fsynced temp file beside the target and return it."""
        fd, name = tempfile.mkstemp(
            dir=self._path.parent, prefix=f".{self._path.name}.", suffix=".tmp"
        )
        tmp = Path(name)
        try:
            # surrogateescape mirrors read(): a lone surrogate produced by
            # decoding an invalid host byte is written back as that exact byte.
            handle = os.fdopen(
                fd, "w", encoding="utf-8", newline="", errors="surrogateescape"
            )
        except BaseException:
            os.close(fd)
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)
            raise
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        return tmp
