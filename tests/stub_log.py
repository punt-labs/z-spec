"""Stub tool call logs: one self-delimiting record per call, read back exactly.

A stub script logs each call with ONE printf: its argument count, then
every argument, each field NUL-terminated (``printf '%s\\0' "$#" "$@"``).
The count makes a record self-delimiting, so a call with no arguments, an
empty argument, or an argument holding a space or a newline reads back as
exactly the argv the stub was given; and since a call is one write, a
truncated record is detectable rather than silently merged into the next.
Both the install.sh runner and the workflow-step runner log through here,
so the two read their stubs the same way.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final, Self, final

import pytest

_COUNT: Final[re.Pattern[str]] = re.compile(r"[0-9]+")


@final
class StubLog:
    """The directory stubs log to, one file per tool, read as argv lists."""

    __slots__ = ("_directory",)
    _directory: Path

    def __new__(cls, directory: Path) -> Self:
        self = super().__new__(cls)
        self._directory = directory
        return self

    @staticmethod
    def append_line(name: str) -> str:
        """Return the shell line a stub runs to log its own call as ``name``.

        The log directory comes from the stub's ``$LOGS`` at run time.
        """
        return f'printf \'%s\\0\' "$#" "$@" >> "$LOGS/{name}"\n'

    def calls(self, tool: str) -> list[list[str]]:
        """Return every logged argv of ``tool``, in call order.

        A record that is cut short -- a missing terminator, a count with too
        few arguments after it, a count that is not a number -- fails the
        test rather than being read as some other argv.
        """
        log = self._directory / tool
        if not log.exists():
            return []
        # Bytes, not read_text: universal-newline decoding would turn an
        # argument's "\r" into "\n".
        fields = log.read_bytes().decode("utf-8").split("\0")
        if fields.pop() != "":
            pytest.fail(f"{tool} log ends in a partial record: {log}")
        calls: list[list[str]] = []
        i = 0
        while i < len(fields):
            if not _COUNT.fullmatch(fields[i]):
                pytest.fail(f"{tool} log record {len(calls) + 1}: count {fields[i]!r}")
            end = i + 1 + int(fields[i])
            if end > len(fields):
                pytest.fail(f"{tool} log ends in a partial record: {fields[i:]!r}")
            calls.append(fields[i + 1 : end])
            i = end
        return calls
