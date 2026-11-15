"""Classify a Markdown document's physical lines as top-level or code.

Claude Code resolves ``@``-imports only at top level, so a line inside a fenced
or indented code block is inert. Fenced blocks are balanced pairs
(:meth:`Fence.closes`), and an **unterminated opener runs to the end of the
file**, as in Claude Code's Markdown lexer (punt-kit
``standards/tool-enable-disable.md`` §2.4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self, final

__all__ = ["CodeBlockMap", "Fence", "UnclosedFenceError"]

_MARKERS = "`~"
_MIN_RUN = 3
_INDENT = 4


class UnclosedFenceError(OSError):
    """A document ends inside a code fence, so a line appended to it is inert.

    An ``OSError`` like ``SettingsRefusedError``: the user's repo refusing the
    write, rendered by the same enablement failure path.
    """


@final
@dataclass(frozen=True, slots=True)
class Fence:
    """A fence delimiter: a run of *run* copies of *marker* (a backtick or tilde).

    *bare* is set when nothing but whitespace follows the run.
    """

    marker: str
    run: int
    bare: bool

    @classmethod
    def parse(cls, line: str) -> Fence | None:
        """Return the fence *line* delimits, or ``None`` when it is not a delimiter.

        ``None`` (PY-TS-14) means "not a delimiter" — the documented contract,
        not a failure. A delimiter is a run of three or more of one marker after
        at most three leading spaces; an indented line is inert and never a
        delimiter, or it would flip the classification of every following line.
        A backtick fence's info string cannot hold a backtick (CommonMark), so a
        line such as ```` ```x``` ```` is an inline code span, not a fence.
        """
        bare = line.rstrip("\r\n")
        if CodeBlockMap.is_indented(bare):
            return None
        stripped = bare.lstrip(" ")
        if not stripped or stripped[0] not in _MARKERS:
            return None
        marker = stripped[0]
        run = len(stripped) - len(stripped.lstrip(marker))
        if run < _MIN_RUN or (marker == "`" and "`" in stripped[run:]):
            return None
        return cls(marker, run, bare=not stripped[run:].strip())

    def closes(self, opener: Fence) -> bool:
        """Return whether this delimiter closes a block *opener* started.

        Only a bare run of the same marker, at least as long as the opener's,
        closes it (CommonMark: an info string is valid on an opener only); a
        shorter, mismatched or info-tagged delimiter is content, and blocks
        never nest.
        """
        return self.bare and self.marker == opener.marker and self.run >= opener.run


@final
class CodeBlockMap:
    """Which physical lines of a document sit outside every code block.

    The content and closing delimiter of a fenced block are code; the opener is
    not. Every line below an opener that never closes is code, and
    :attr:`open_at_eof` is set; a line above it is unaffected. An indented line
    (a tab or four or more leading spaces) is always code.
    """

    __slots__ = ("_open_at_eof", "_top_level")

    _open_at_eof: bool
    _top_level: tuple[bool, ...]

    def __new__(cls, lines: tuple[str, ...]) -> Self:
        self = super().__new__(cls)
        code: set[int] = set()
        opener: Fence | None = None  # None = no block open (PY-TS-14: a state)
        for i, line in enumerate(lines):
            fence = Fence.parse(line)
            if opener is not None:
                code.add(i)
                if fence is not None and fence.closes(opener):
                    opener = None
            elif fence is not None:
                opener = fence
        self._open_at_eof = opener is not None
        self._top_level = tuple(
            i not in code and not cls.is_indented(line) for i, line in enumerate(lines)
        )
        return self

    @property
    def open_at_eof(self) -> bool:
        """Return whether the document ends inside a fence that never closes."""
        return self._open_at_eof

    @property
    def top_level(self) -> tuple[bool, ...]:
        """Return one flag per physical line: ``True`` when it is top-level."""
        return self._top_level

    @staticmethod
    def is_indented(line: str) -> bool:
        """Return whether *line* is an indented-code line (tab or 4+ spaces)."""
        return line.startswith("\t") or len(line) - len(line.lstrip(" ")) >= _INDENT
