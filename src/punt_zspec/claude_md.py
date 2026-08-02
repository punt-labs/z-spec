"""Register and prune z-spec's bare ``@``-import line in a host ``CLAUDE.md``.

punt-kit ``standards/tool-enable-disable.md`` §2.1: the user's ``CLAUDE.md`` is
user-owned prose. The only mutation a tool may make is to add or remove one
``@``-import line pointing at a file the tool owns entirely — no marker block,
no managed section, no merge. §2.4 fixes the exact line, the match rules, and
the write contract; this module owns that single line and nothing else.

Claude Code resolves ``@``-imports only at top level, so a line inside a fenced
or indented code block is inert and must be ignored by both the presence scan
and the removal. Fence semantics follow §2.4's balanced-pair definition — an
unterminated opener delimits nothing, or one stray fence in the user's prose
would flip the classification of the tool's own line and make ``enable``
duplicate it and ``disable`` unable to remove it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

from punt_zspec.atomic_file import AtomicFile

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["ClaudeMdImport", "MarkdownLines"]

_FENCE_CHARS = "`~"
_MIN_FENCE = 3
_INDENT_CODE = 4


@final
class MarkdownLines:
    """The physical lines of a markdown document, classified by nesting.

    Lines keep their terminators, so a document can be rebuilt byte-for-byte
    after a line is dropped.
    """

    _lines: tuple[str, ...]
    _top_level: tuple[bool, ...]
    __slots__ = ("_lines", "_top_level")

    def __new__(cls, text: str) -> Self:
        self = super().__new__(cls)
        self._lines = tuple(text.splitlines(keepends=True))
        self._top_level = cls._classify(self._lines)
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
            for line, top in zip(self._lines, self._top_level, strict=True)
            if not (top and self._matches(line, target))
        )

    def with_appended(self, target: str) -> str:
        """Return the document with *target* appended as one bare final line.

        Ensures a separating newline first, so the import is never glued to the
        user's last line, and uses the document's own EOL convention for both.
        """
        text = "".join(self._lines)
        eol = self.eol()
        if text and not text.endswith(("\n", "\r")):
            text += eol
        return f"{text}{target}{eol}"

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
            line for line, top in zip(self._lines, self._top_level, strict=True) if top
        )

    @staticmethod
    def _matches(line: str, target: str) -> bool:
        """Match a physical line against *target*, net of its terminator."""
        return line.rstrip("\r\n") == target

    @classmethod
    def _classify(cls, lines: tuple[str, ...]) -> tuple[bool, ...]:
        """Flag each line ``True`` when it is top level (not in a code block).

        Content and the closing delimiter of a matched fenced block are inside;
        the opening delimiter is not. An indented line — a tab or four or more
        leading spaces — is an indented-code line and never top level.
        """
        inside: set[int] = set()
        for open_idx, close_idx in cls._fenced_ranges(lines):
            inside.update(range(open_idx + 1, close_idx + 1))
        return tuple(
            i not in inside and not cls._indented(line) for i, line in enumerate(lines)
        )

    @classmethod
    def _fenced_ranges(cls, lines: tuple[str, ...]) -> list[tuple[int, int]]:
        """Return the ``(open, close)`` index pairs of matched fenced blocks.

        A block opened by a run of *N* of a marker closes only on a later
        same-marker delimiter of length ``>= N``; a mismatched marker or a
        shorter run is content, not a close. An unterminated opener is dropped,
        so a dangling fence never swallows the rest of the file.
        """
        ranges: list[tuple[int, int]] = []
        opened_at: int | None = None  # None = no block open (PY-TS-14: a state)
        marker, length = "", 0
        for i, line in enumerate(lines):
            fence = cls._parse_fence(line)
            if opened_at is None:
                if fence is not None:
                    opened_at, (marker, length) = i, fence
            elif fence is not None and fence[0] == marker and fence[1] >= length:
                ranges.append((opened_at, i))
                opened_at = None
        return ranges

    @staticmethod
    def _parse_fence(line: str) -> tuple[str, int] | None:
        """Return ``(marker, run length)`` when *line* is a fence delimiter.

        ``None`` (PY-TS-14) means "not a delimiter" — the documented contract,
        not a failure. An indented line is inert and never a delimiter, even
        when it opens with backticks: treating it as one would toggle the block
        state and flip the classification of every following line.
        """
        bare = line.rstrip("\r\n")
        stripped = bare.lstrip(" ")
        if bare.startswith("\t") or len(bare) - len(stripped) >= _INDENT_CODE:
            return None
        if not stripped or stripped[0] not in _FENCE_CHARS:
            return None
        marker = stripped[0]
        run = len(stripped) - len(stripped.lstrip(marker))
        return (marker, run) if run >= _MIN_FENCE else None

    @staticmethod
    def _indented(line: str) -> bool:
        return (
            line.startswith("\t") or len(line) - len(line.lstrip(" ")) >= _INDENT_CODE
        )


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
        only) is a no-op, so re-running ``enable`` never duplicates it.
        """
        with self._host.locked():
            doc = MarkdownLines(self._host.read())
            if doc.contains(self._line):
                return False
            self._host.write(doc.with_appended(self._line))
            return True

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
