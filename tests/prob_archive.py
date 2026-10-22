"""ProB-shaped archive fixtures, served to the shipped install shell.

The install.sh and workflow tests run the shipped shell against a
``ProbArchive``: built byte-for-byte the same on every build, so a pin taken
from one build matches the next, and damaged on request the way a broken or
hostile host might serve it.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import tarfile
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, Literal, Self, final

type Damage = Literal["none", "not-an-archive", "corrupt"]
_ARCHIVE_NAMES: Final[dict[str, str]] = {
    "Darwin": "ProB.macos.zip",
    "Linux": "ProB.linux64.tar.gz",
}


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
    mode: int = 0o755  # every member's permission bits

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
    def running(cls, system: str, body: str) -> Self:
        """Build an archive whose ProB/probcli runs ``body`` under /bin/sh."""
        return cls(system, (("ProB/probcli", f"#!/bin/sh\n{body}\n".encode()),))

    @classmethod
    def without_probcli(cls, system: str) -> Self:
        """Build a well-formed archive whose only member is ProB/README."""
        return cls(system, (("ProB/README", b"no probcli in this archive\n"),))

    def damaged(self, damage: Damage) -> ProbArchive:
        """Return this archive served with ``damage``."""
        return replace(self, damage=damage)

    def not_executable(self) -> ProbArchive:
        """Return this archive with no exec bit on any member (mode 0644)."""
        return replace(self, mode=0o644)

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
                    zinfo.external_attr = self.mode << 16
                    zf.writestr(zinfo, payload)
            return buffer.getvalue()
        with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as tf:
            for name, payload in self.members:
                tinfo = tarfile.TarInfo(name)
                tinfo.size, tinfo.mode, tinfo.mtime = len(payload), self.mode, 0
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
