"""Register and prune z-spec's bare ``@``-import line in a host ``CLAUDE.md``.

punt-kit ``standards/tool-enable-disable.md`` §2.1: the user's ``CLAUDE.md`` is
user-owned prose. The only mutation a tool may make is to add or remove one
``@``-import line pointing at a file the tool owns entirely — no marker block,
no managed section, no merge. §2.4 fixes the exact line, the match rules, and
the write contract; this module owns that single line and nothing else.

Claude Code resolves ``@``-imports only at top level, so a line inside a fenced
or indented code block is inert and must be ignored by both the presence scan
and the removal; :class:`~punt_zspec.markdown_fence.CodeBlockMap` classifies
the lines. A fence that never closes runs to the end of the file, so an import
appended below it would never load: ``register`` refuses instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

from punt_zspec.atomic_file import AtomicFile
from punt_zspec.markdown_fence import CodeBlockMap, UnclosedFenceError

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["ClaudeMdImport", "MarkdownLines"]


@final
class MarkdownLines:
    """The physical lines of a markdown document, classified by nesting.

    Lines keep their terminators, so a document can be rebuilt byte-for-byte
    after a line is dropped.
    """

    _blocks: CodeBlockMap
    _lines: tuple[str, ...]
    __slots__ = ("_blocks", "_lines")

    def __new__(cls, text: str) -> Self:
        self = super().__new__(cls)
        self._lines = tuple(text.splitlines(keepends=True))
        self._blocks = CodeBlockMap(self._lines)
        return self

    def contains(self, target: str) -> bool:
        """Return whether *target* appears as a top-level line."""
        return any(self._matches(line, target) for line in self._top_level_lines())

    def without(self, target: str) -> str:
        """Return the document with every top-level *target* line removed.

        Removes *every* match, collapsing an accidental duplicate to zero, and
        leaves an inert copy inside a code block untouched.
        """
        return "".join(
            line
            for line, top in zip(self._lines, self._blocks.top_level, strict=True)
            if not (top and self._matches(line, target))
        )

    def with_appended(self, target: str) -> str:
        """Return the document with *target* appended as one bare final line.

        Ensures a separating newline first, so the import is never glued to the
        user's last line, and uses the document's own EOL convention for both.
        Raises :class:`UnclosedFenceError` when the document ends inside a
        fence that never closes, where the appended line would be inert.
        """
        self.check_appendable()
        text = "".join(self._lines)
        eol = self.eol()
        if text and not text.endswith(("\n", "\r")):
            text += eol
        return f"{text}{target}{eol}"

    def check_appendable(self) -> None:
        """Raise :class:`UnclosedFenceError` if a line appended here would be code."""
        if self._blocks.open_at_eof:
            msg = "CLAUDE.md ends inside an unclosed code fence; close it first"
            raise UnclosedFenceError(msg)

    def eol(self) -> str:
        """Return the document's EOL convention, defaulting to ``\\n``."""
        for line in self._lines:
            if line.endswith("\r\n"):
                return "\r\n"
            if line.endswith("\n"):
                return "\n"
            if line.endswith("\r"):
                return "\r"
        return "\n"

    def _top_level_lines(self) -> tuple[str, ...]:
        return tuple(
            line
            for line, top in zip(self._lines, self._blocks.top_level, strict=True)
            if top
        )

    @staticmethod
    def _matches(line: str, target: str) -> bool:
        """Match a physical line against *target*, net of its terminator."""
        return line.rstrip("\r\n") == target


@final
class ClaudeMdImport:
    """Owns one bare ``@``-import line inside a host ``CLAUDE.md``.

    Every read-modify-write runs under :meth:`AtomicFile.locked`, and each
    write lands atomically, so a read never observes a torn file and two
    parallel ``enable`` runs cannot lose each other's update.
    """

    _host: AtomicFile
    _line: str
    __slots__ = ("_host", "_line")

    def __new__(cls, host: Path, import_line: str) -> Self:
        cls._validate(import_line)
        self = super().__new__(cls)
        self._host = AtomicFile(host)
        self._line = import_line
        return self

    @property
    def line(self) -> str:
        """Return the canonical import line this instance owns."""
        return self._line

    def is_registered(self) -> bool:
        """Return whether the import line is present at top level."""
        return MarkdownLines(self._host.read()).contains(self._line)

    def register(self) -> bool:
        """Append the import line if absent. Return whether the file changed.

        Idempotent: a line already present (net of its terminator, top level
        only) is a no-op, so re-running ``enable`` never duplicates it. Raises
        :class:`UnclosedFenceError` rather than append an import that would sit
        inside a fence that never closes.
        """
        with self._host.locked():
            doc = MarkdownLines(self._host.read())
            if doc.contains(self._line):
                return False
            self._host.write(doc.with_appended(self._line))
            return True

    def check_registrable(self) -> None:
        """Raise :class:`UnclosedFenceError` if :meth:`register` would refuse.

        Lets ``enable`` refuse before it writes any settings rule; ``register``
        repeats the check under the lock.
        """
        doc = MarkdownLines(self._host.read())
        if not doc.contains(self._line):
            doc.check_appendable()

    def prune(self) -> bool:
        """Remove every top-level occurrence. Return whether the file changed."""
        with self._host.locked():
            text = self._host.read()
            pruned = MarkdownLines(text).without(self._line)
            if pruned == text:
                return False
            self._host.write(pruned)
            return True

    @staticmethod
    def _validate(import_line: str) -> None:
        """Raise ``ValueError`` unless *line* is a lone top-level ``@`` line.

        Validated at the construction boundary (PY-EH-1): the line is spliced
        into the host file verbatim, so a padded, multi-line, or non-``@`` value
        would inject a duplicate, a blank line, or inert markdown.
        """
        if not import_line or import_line.isspace():
            msg = "import line must be non-empty"
            raise ValueError(msg)
        if "\n" in import_line or "\r" in import_line:
            msg = f"import line must be a single line: {import_line!r}"
            raise ValueError(msg)
        if import_line != import_line.strip():
            msg = f"import line must not be padded: {import_line!r}"
            raise ValueError(msg)
        if not import_line.startswith("@"):
            msg = f"import line must begin with '@': {import_line!r}"
            raise ValueError(msg)
