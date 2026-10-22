"""Each runner reads a stub's call log back as exactly the argv it was given.

Every "was this tool called, and how" assertion in the install.sh and
workflow-step tests rests on this: a parser that merged two calls, or split
one argument at a space, would let a wrong argv pass as a right one. So a
real stub -- the shell line ``StubLog.append_line`` writes, run by ``sh`` --
is called with awkward arguments, and each runner's ``calls()`` must return
them unchanged.
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


def _stub_calls(root: Path, argvs: list[list[str]]) -> None:
    """Run a logging stub named ``tool`` once per argv, as a tool would be."""
    sh = shutil.which("sh")
    if sh is None:
        pytest.fail("the host has no sh, which every stub runs under")
    stub = root / "bin" / "tool"
    stub.parent.mkdir(parents=True)
    (root / "logs").mkdir()
    stub.write_text(f"#!{sh}\n" + StubLog.append_line("tool"), encoding="utf-8")
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
    assert reader(tmp_path)("tool") == []


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
