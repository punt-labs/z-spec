"""Stub tool call logs: one self-delimiting record per call, read back exactly.

A stub script logs each call with ONE printf: its argument count, then
every argument, each field NUL-terminated (``printf '%s\\0' "$#" "$@"``).
The count makes a record self-delimiting, so a call with no arguments, an
empty argument, or an argument holding a space or a newline reads back as
exactly the argv the stub was given; and since a call is one write, a
truncated record is detectable rather than silently merged into the next.
Both the install.sh runner and the workflow-step runner log through here,
so the two read their stubs the same way.

Neither side can fail quietly: a stub that cannot write its record exits
125 with a message instead of running on unlogged, and reading a log
directory that does not exist fails the test, so "never called" is never
concluded from a log that could not have been written.
"""

from __future__ import annotations

import re
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Final, Self, final

import pytest

_COUNT: Final[re.Pattern[str]] = re.compile(r"[0-9]+")
# The first-argument patterns of an extracting call -- ``tar -x...``,
# ``unzip -q`` and ``unzip -oq``, the forms install.sh and the workflow use.
# The failing-extractor stub's shell ``case`` and ``is_extraction`` are both
# built from this one tuple, so the two cannot classify a call differently.
_EXTRACTING: Final[tuple[str, ...]] = ("-x*", "-q", "-oq")
# The first argument of a zip listing call: ``unzip -Z1``.
_LISTING: Final[str] = "-Z1"


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

        The log directory comes from the stub's ``$LOGS`` at run time. A
        record that cannot be written stops the stub with exit 125, so the
        call fails loudly instead of running on with nothing logged.
        """
        return (
            f'printf \'%s\\0\' "$#" "$@" >> "$LOGS/{name}" || {{ '
            f'echo "{name} stub: could not write its call log $LOGS/{name}" >&2; '
            "exit 125; }\n"
        )

    @staticmethod
    def is_extraction(argv: list[str]) -> bool:
        """Whether a logged tar/unzip call extracts, as the stub classifies it.

        A call with no arguments is not an extraction: its ``$1`` is empty,
        which no pattern matches.
        """
        return bool(argv) and any(fnmatchcase(argv[0], p) for p in _EXTRACTING)

    @classmethod
    def wrapper(
        cls,
        name: str,
        real: str,
        *,
        extraction_fails: bool = False,
        listing_fails: bool = False,
    ) -> str:
        """Return a stub that logs its call as ``name``, then runs ``real``.

        With ``extraction_fails``, an extracting call (``is_extraction``)
        fails as an unwritable destination would, whatever the uid; listing
        and testing calls (``-tzf``, ``-tq``, ``-Z1``) still run ``real``, so
        a good archive gets as far as its extraction. With ``listing_fails``,
        ``unzip -Z1`` fails while ``-tq`` still runs ``real``, so a good zip
        passes its integrity test and only its listing fails.
        """
        branches: list[str] = []
        if extraction_fails:
            branches.append(
                f"  {'|'.join(_EXTRACTING)}) "
                f'echo "{name}: simulated extraction failure" >&2; exit 1 ;;\n'
            )
        if listing_fails:
            branches.append(
                f'  {_LISTING}) echo "{name}: simulated listing failure" >&2; '
                "exit 1 ;;\n"
            )
        script = "#!/bin/sh\n" + cls.append_line(name)
        if branches:
            script += 'case "$1" in\n' + "".join(branches) + "esac\n"
        return script + f"exec '{real}' \"$@\"\n"

    def calls(self, tool: str) -> list[list[str]]:
        """Return every logged argv of ``tool``, in call order.

        A record that is cut short -- a missing terminator, a count with too
        few arguments after it, a count that is not a number -- fails the
        test rather than being read as some other argv. So does a log
        directory that does not exist: no stub could have logged there.
        """
        if not self._directory.is_dir():
            pytest.fail(f"stub log directory {self._directory} does not exist")
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
