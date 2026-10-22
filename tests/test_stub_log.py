"""Each runner reads a stub's call log back as exactly the argv it was given.

Every "was this tool called, and how" assertion in the install.sh and
workflow-step tests rests on this: a parser that merged two calls, or split
one argument at a space, would let a wrong argv pass as a right one. So a
real stub -- the shell line ``StubLog.append_line`` writes, run by ``sh`` --
is called with awkward arguments, and each runner's ``calls()`` must return
them unchanged. Neither end may fail quietly: a stub that cannot log stops,
and a log directory that does not exist is an error, not "never called".
The failing-extractor stub and the runners' ``extractions()`` must agree on
which calls extract.
"""

from __future__ import annotations

import shutil
import stat
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Final

import pytest

from tests.install_probcli_runner import Run
from tests.stub_log import StubLog
from tests.workflow_step_runner import StepRun

type Reader = Callable[[Path], Callable[[str], list[list[str]]]]

_DONE: Final[subprocess.CompletedProcess[str]] = subprocess.CompletedProcess([], 0)
# Each runner's calls(), reading the log directory <root>/logs.
_READERS: Final[dict[str, Reader]] = {
    "install_probcli_runner": lambda root: Run(_DONE, root, root / "logs", "").calls,
    "workflow_step_runner": lambda root: StepRun(_DONE, root).calls,
}
_AWKWARD: Final[list[list[str]]] = [
    [],
    [""],
    ["two words"],
    ["\nleading newline", "", "last"],
    ["-o", "out file", "carriage\rreturn", "tab\there"],
]


def _sh() -> str:
    sh = shutil.which("sh")
    if sh is None:
        pytest.fail("the host has no sh, which every stub runs under")
    return sh


def _stub_calls(root: Path, argvs: list[list[str]]) -> None:
    """Run a logging stub named ``tool`` once per argv, as a tool would be."""
    stub = root / "bin" / "tool"
    stub.parent.mkdir(parents=True)
    (root / "logs").mkdir()
    stub.write_text(f"#!{_sh()}\n" + StubLog.append_line("tool"), encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    for argv in argvs:
        subprocess.run([str(stub), *argv], env={"LOGS": str(root / "logs")}, check=True)


@pytest.mark.parametrize("reader", _READERS.values(), ids=_READERS.keys())
def test_awkward_arguments_read_back_exactly(tmp_path: Path, reader: Reader) -> None:
    _stub_calls(tmp_path, _AWKWARD)
    assert reader(tmp_path)("tool") == _AWKWARD


@pytest.mark.parametrize("reader", _READERS.values(), ids=_READERS.keys())
def test_a_call_with_no_arguments_is_an_empty_argv(
    tmp_path: Path, reader: Reader
) -> None:
    _stub_calls(tmp_path, [[], []])
    assert reader(tmp_path)("tool") == [[], []]


@pytest.mark.parametrize("reader", _READERS.values(), ids=_READERS.keys())
def test_a_tool_never_called_has_no_calls(tmp_path: Path, reader: Reader) -> None:
    (tmp_path / "logs").mkdir()
    assert reader(tmp_path)("tool") == []


@pytest.mark.parametrize("reader", _READERS.values(), ids=_READERS.keys())
def test_a_missing_log_directory_fails_loudly(tmp_path: Path, reader: Reader) -> None:
    # No stub could have logged here, so "never called" would be vacuous.
    with pytest.raises(pytest.fail.Exception, match="does not exist"):
        reader(tmp_path)("tool")


def test_a_stub_that_cannot_log_stops_with_125(tmp_path: Path) -> None:
    stub = tmp_path / "tool"
    stub.write_text(f"#!{_sh()}\n" + StubLog.append_line("tool") + "exit 0\n")
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    missing = tmp_path / "no-such-dir"
    run = subprocess.run(
        [str(stub), "a"],
        env={"LOGS": str(missing)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 125
    assert f"tool stub: could not write its call log {missing}/tool\n" in run.stderr


@pytest.mark.parametrize("reader", _READERS.values(), ids=_READERS.keys())
@pytest.mark.parametrize(
    "log",
    [b"2\0a\0", b"1\0a", b"0\0x", b"x\0a\0", b"1\0a\0\0"],
    ids=[
        "count-exceeds-arguments",
        "unterminated",
        "unterminated-after-a-record",
        "no-count",
        "stray-field",
    ],
)
def test_a_partial_record_fails_loudly(
    tmp_path: Path, reader: Reader, log: bytes
) -> None:
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "tool").write_bytes(log)
    with pytest.raises(pytest.fail.Exception, match="tool log"):
        reader(tmp_path)("tool")


# First arguments the failing-extractor stub must fail, and must let through.
_EXTRACTING: Final[list[list[str]]] = [["-xzf", "a"], ["-x"], ["-q", "a"], ["-oq"]]
_NOT_EXTRACTING: Final[list[list[str]]] = [
    [],
    [""],
    ["-tzf", "a"],
    ["-tq", "a"],
    ["-Z1", "a"],
    ["-qo"],
    ["x"],
    ["--x"],
]


def _argv_id(argv: list[str]) -> str:
    return " ".join(repr(arg) for arg in argv) or "no-arguments"


def _run_wrapper(tmp_path: Path, argv: list[str], *, listing: bool) -> int:
    """Run a failing-extractor (or failing-listing) wrapper around ``true``."""
    real = shutil.which("true")
    if real is None:
        pytest.fail("the host has no true")
    stub = tmp_path / "wrapped"
    text = StubLog.wrapper(
        "wrapped", real, extraction_fails=not listing, listing_fails=listing
    )
    stub.write_text(text, encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    (tmp_path / "logs").mkdir(exist_ok=True)
    env = {"LOGS": str(tmp_path / "logs"), "PATH": "/usr/bin:/bin"}
    return subprocess.run([str(stub), *argv], env=env, check=False).returncode


@pytest.mark.parametrize("argv", _EXTRACTING + _NOT_EXTRACTING, ids=_argv_id)
def test_the_stub_and_extractions_classify_a_call_alike(
    tmp_path: Path, argv: list[str]
) -> None:
    extracts = argv in _EXTRACTING
    assert StubLog.is_extraction(argv) == extracts
    assert _run_wrapper(tmp_path, argv, listing=False) == (1 if extracts else 0)


@pytest.mark.parametrize(
    ("argv", "status"),
    [(["-Z1", "a"], 1), (["-tq", "a"], 0), (["-q", "a"], 0), ([], 0)],
    ids=["listing", "integrity-test", "extraction", "no-arguments"],
)
def test_a_failing_listing_stub_fails_only_the_listing(
    tmp_path: Path, argv: list[str], status: int
) -> None:
    assert _run_wrapper(tmp_path, argv, listing=True) == status
