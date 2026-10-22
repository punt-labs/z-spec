"""install.sh's ProB values and the ProB archive fixtures, shared by two tests.

install.sh and .github/workflows/test.yml each carry the ProB version, the
per-OS SHA-256 pins, and the curl flag set. The tests that gate their parity
read install.sh through ``InstallSh``, so both sides of every parity
assertion come from the same parser, and compare curl flags as
``CurlFlags`` -- flag -> value pairs, so a value swapped between two flags is
a difference, not an equal bag of tokens. Both tests also run the shipped
shell against a ``ProbArchive``: a ProB-shaped archive built byte-for-byte
the same on every build, so a pin taken from one build matches the next.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import re
import shlex
import tarfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, Literal, Self, final

_INSTALL_SH: Final[Path] = Path(__file__).resolve().parent.parent / "install.sh"
_PROB_VERSION: Final[re.Pattern[str]] = re.compile(r"^PROB_VERSION=(\S+)$", re.M)
_PIN: Final[re.Pattern[str]] = re.compile(
    r'^(PROB_SHA256_(?:LINUX|MACOS))="([^"]*)"$', re.M
)
_SET_FLAGS: Final[re.Pattern[str]] = re.compile(
    r"^\s*set -- (-fL(?:[^\n]*\\\n)*[^\n]*)$", re.M
)
type Damage = Literal["none", "not-an-archive", "corrupt"]
_ARCHIVE_NAMES: Final[dict[str, str]] = {
    "Darwin": "ProB.macos.zip",
    "Linux": "ProB.linux64.tar.gz",
}


@final
@dataclass(frozen=True, slots=True)
class CurlFlags:
    """A curl option list as ordered flag -> value pairs (None: no value).

    A token is a flag's value when it follows the flag and does not itself
    start with ``-``; every value curl takes here (``=https``, ``20``) does
    not. A flag given twice is rejected rather than collapsed, so a duplicate
    can never hide behind the comparison.
    """

    pairs: tuple[tuple[str, str | None], ...]  # None: the flag takes no value

    @classmethod
    def parse(cls, tokens: list[str]) -> Self:
        pairs: list[tuple[str, str | None]] = []
        i = 0
        while i < len(tokens):
            flag = tokens[i]
            if not flag.startswith("-"):
                raise ValueError(f"curl option list: {flag!r} is not a flag")
            value = None
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                value = tokens[i + 1]
                i += 1
            pairs.append((flag, value))
            i += 1
        flags = [flag for flag, _ in pairs]
        if len(set(flags)) != len(flags):
            raise ValueError(f"curl option list repeats a flag: {flags}")
        return cls(tuple(pairs))

    def as_dict(self) -> dict[str, str | None]:
        return dict(self.pairs)

    def with_flag(self, flag: str) -> CurlFlags:
        """Return these flags plus a value-less ``flag`` appended."""
        return CurlFlags.parse([*self.tokens(), flag])

    def tokens(self) -> list[str]:
        return [t for flag, value in self.pairs for t in (flag, value) if t]


@final
class InstallSh:
    """install.sh's text, read for the ProB values the tests gate."""

    __slots__ = ("_text",)
    _text: str

    def __new__(cls, path: Path = _INSTALL_SH) -> Self:
        self = super().__new__(cls)
        self._text = path.read_text(encoding="utf-8")
        return self

    def prob_version(self) -> str:
        """Return the top-level PROB_VERSION value."""
        found = [m.group(1) for m in _PROB_VERSION.finditer(self._text)]
        if len(found) != 1:
            raise ValueError(f"install.sh: expected one PROB_VERSION=, got {found}")
        return found[0]

    def pins(self) -> dict[str, str]:
        """Return the PROB_SHA256_LINUX / PROB_SHA256_MACOS values."""
        found = [(m.group(1), m.group(2)) for m in _PIN.finditer(self._text)]
        names = sorted(name for name, _ in found)
        if names != ["PROB_SHA256_LINUX", "PROB_SHA256_MACOS"]:
            raise ValueError(
                f"install.sh must assign PROB_SHA256_LINUX and PROB_SHA256_MACOS "
                f"once each, found {names}"
            )
        return dict(found)

    def install_probcli_source(self) -> str:
        """Return the text from PROB_VERSION= through install_probcli's ``)``."""
        lines = self._text.splitlines()
        start = self._first(lines, 0, lambda ln: ln.startswith("PROB_VERSION="))
        opener = self._first(lines, 0, lambda ln: ln == "install_probcli() (")
        if opener < start:
            raise ValueError("install.sh: install_probcli() precedes PROB_VERSION=")
        end = self._first(lines, opener, lambda ln: ln == ")")
        source = "\n".join(lines[start : end + 1]) + "\n"
        if "resolve_probcli_path() {" not in source:
            raise ValueError(
                "install.sh: resolve_probcli_path() is no longer between "
                "PROB_VERSION= and install_probcli(), so the sliced function "
                "would call an undefined helper"
            )
        return source

    def fetch_flags(self) -> CurlFlags:
        """Return the fixed curl flags install_probcli builds with ``set --``."""
        match = _SET_FLAGS.search(self.install_probcli_source())
        if match is None:
            raise ValueError("install_probcli has no `set -- -fL ...` curl flag list")
        return CurlFlags.parse(shlex.split(match.group(1).replace("\\\n", " ")))

    @staticmethod
    def _first(lines: list[str], start: int, matches: Callable[[str], bool]) -> int:
        for i in range(start, len(lines)):
            if matches(lines[i]):
                return i
        raise ValueError(f"install.sh: no matching line at or after line {start + 1}")


@final
@dataclass(frozen=True, slots=True)
class ProbArchive:
    """A ProB-shaped archive for one OS, built deterministically.

    The tar.gz is written with a zero gzip header mtime and zero member
    mtimes, and the zip with zipfile's fixed 1980 timestamp, so two builds
    are byte-identical: a pin hashed from one build verifies the next.

    ``damage`` serves what a broken or hostile host might, still under the
    archive's own name and pinnable by its own hash: ``"not-an-archive"`` is
    an HTML error page, and ``"corrupt"`` is the archive damaged where every
    implementation of the reading tool notices. The zip has one byte of its
    first member's payload flipped: its listing still reads, and only a CRC
    test or an extraction notices -- Info-ZIP's unzip on Linux and macOS
    alike. The tar.gz is cut to half its length, so the gzip stream ends
    early and listing it fails under GNU tar ("unexpected end of file") and
    bsdtar/libarchive, macOS's tar ("truncated gzip input"). A flipped gzip
    CRC trailer is not used: libarchive does not check it, so bsdtar lists
    such an archive cleanly.
    """

    system: str  # "Linux" (tar.gz) or "Darwin" (zip), as `uname -s` prints
    members: tuple[tuple[str, bytes], ...]
    damage: Damage = "none"

    @classmethod
    def with_probcli(cls, system: str, version: str, *extra: str) -> Self:
        """Build an archive whose ProB/probcli prints ``version``.

        Each ``extra`` member name is added with placeholder content -- e.g.
        ``"../escaped"`` for an archive that tries to write outside its dest.
        """
        script = f"#!/bin/sh\necho 'ProB command line, version {version}'\n"
        members = [("ProB/probcli", script.encode())]
        members += [(name, b"planted by the archive\n") for name in extra]
        return cls(system, tuple(members))

    @classmethod
    def without_probcli(cls, system: str) -> Self:
        """Build a well-formed archive whose only member is ProB/README."""
        return cls(system, (("ProB/README", b"no probcli in this archive\n"),))

    def damaged(self, damage: Damage) -> ProbArchive:
        """Return this archive served with ``damage``."""
        return replace(self, damage=damage)

    @property
    def name(self) -> str:
        return _ARCHIVE_NAMES[self.system]

    def data(self) -> bytes:
        match self.damage:
            case "not-an-archive":
                return b"<html><body><h1>503 Service Unavailable</h1></body></html>\n"
            case "corrupt":
                return self._corrupted(self._intact())
            case "none":
                return self._intact()

    def sha256(self) -> str:
        return hashlib.sha256(self.data()).hexdigest()

    def write(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / self.name
        path.write_bytes(self.data())
        return path

    def _intact(self) -> bytes:
        buffer = io.BytesIO()
        if self.system == "Darwin":
            with zipfile.ZipFile(buffer, "w") as zf:
                for name, payload in self.members:
                    zinfo = zipfile.ZipInfo(name)
                    zinfo.external_attr = 0o755 << 16
                    zf.writestr(zinfo, payload)
            return buffer.getvalue()
        with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as tf:
            for name, payload in self.members:
                tinfo = tarfile.TarInfo(name)
                tinfo.size, tinfo.mode, tinfo.mtime = len(payload), 0o755, 0
                tf.addfile(tinfo, io.BytesIO(payload))
        return gzip.compress(buffer.getvalue(), mtime=0)

    def _corrupted(self, data: bytes) -> bytes:
        if self.system != "Darwin":
            return data[: len(data) // 2]
        # Stored (uncompressed) members: the payload is in the zip as is.
        payload = self.members[0][1]
        if data.count(payload) != 1:
            raise ValueError("zip payload is not uniquely locatable to damage")
        at = data.index(payload)
        return data[:at] + bytes([data[at] ^ 0xFF]) + data[at + 1 :]
