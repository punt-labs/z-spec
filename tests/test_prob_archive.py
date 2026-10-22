"""The ProB archive fixtures read the same under every tar and unzip.

The specs job runs on Linux (GNU tar) and macOS (bsdtar, libarchive), and
both carry Info-ZIP's unzip. A damaged fixture only proves a check works if
the host's own tool rejects it at the step the check relies on, so these
tests run the host's tar and unzip against each fixture: on the macOS leg
they are bsdtar's verdicts, on Linux GNU tar's.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path
from typing import Final

import pytest

from tests.install_sh_source import InstallSh
from tests.prob_archive import ProbArchive

_VERSION: Final[str] = InstallSh().prob_version()


def _tool(name: str) -> str:
    found = shutil.which(name)
    if found is None:
        pytest.fail(f"the host has no {name}, which these fixtures are read with")
    return found


def _reads(tmp_path: Path, archive: ProbArchive, *argv: str) -> bool:
    path = archive.write(tmp_path)
    run = subprocess.run(
        [_tool(argv[0]), *argv[1:], str(path)],
        capture_output=True,
        check=False,
        timeout=60,
    )
    return run.returncode == 0


def test_intact_tarball_lists(tmp_path: Path) -> None:
    good = ProbArchive.with_probcli("Linux", _VERSION)
    assert _reads(tmp_path, good, "tar", "-tzf")


def test_corrupt_tarball_does_not_list(tmp_path: Path) -> None:
    corrupt = ProbArchive.with_probcli("Linux", _VERSION).damaged("corrupt")
    assert not _reads(tmp_path, corrupt, "tar", "-tzf")


def test_intact_zip_lists_and_tests(tmp_path: Path) -> None:
    good = ProbArchive.with_probcli("Darwin", _VERSION)
    assert _reads(tmp_path, good, "unzip", "-Z1")
    assert _reads(tmp_path, good, "unzip", "-tq")


def test_corrupt_zip_lists_but_fails_its_crc_test(tmp_path: Path) -> None:
    # The listing reads, so only the CRC test can stop it before extraction.
    corrupt = ProbArchive.with_probcli("Darwin", _VERSION).damaged("corrupt")
    assert _reads(tmp_path, corrupt, "unzip", "-Z1")
    assert not _reads(tmp_path, corrupt, "unzip", "-tq")


@pytest.mark.parametrize("system", ["Linux", "Darwin"])
def test_corrupt_archive_hashes_differently(system: str) -> None:
    good = ProbArchive.with_probcli(system, _VERSION)
    assert good.damaged("corrupt").sha256() != good.sha256()


# The fixtures must not depend on the clock: a pin hashed from one build has
# to verify the next. The timestamps are checked where they live, in the
# headers, since two builds in the same second would agree by accident.
def test_tar_fixture_carries_no_timestamp() -> None:
    data = ProbArchive.with_probcli("Linux", _VERSION).data()
    assert data[:2] == b"\x1f\x8b"
    assert data[4:8] == b"\0\0\0\0", "gzip MTIME must be zero for a stable hash"
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        assert [m.mtime for m in tf.getmembers()] == [0]


def test_zip_fixture_carries_a_fixed_timestamp() -> None:
    data = ProbArchive.with_probcli("Darwin", _VERSION, "ProB/x").data()
    # Local file header: signature, then mod time (bytes 10-11) and mod
    # date (12-13); 1980-01-01 00:00:00 is time 0, date 0x0021.
    assert data[:4] == b"PK\x03\x04"
    assert data[10:14] == b"\x00\x00\x21\x00"
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert {i.date_time for i in zf.infolist()} == {(1980, 1, 1, 0, 0, 0)}
