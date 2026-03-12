"""Tests for punt_zspec.fuzz."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from punt_zspec.fuzz import resolve_fuzz, run_fuzz


def test_resolve_fuzz_from_env(tmp_path: Path) -> None:
    binary = tmp_path / "fuzz"
    binary.write_text("#!/bin/sh\n")
    with patch.dict("os.environ", {"FUZZ": str(binary)}):
        result = resolve_fuzz()
    assert result == binary


def test_resolve_fuzz_from_path() -> None:
    with patch("shutil.which", return_value="/usr/local/bin/fuzz"):
        result = resolve_fuzz()
    assert result == Path("/usr/local/bin/fuzz")


def test_resolve_fuzz_not_found() -> None:
    with (
        patch.dict("os.environ", {}, clear=True),
        patch("shutil.which", return_value=None),
    ):
        result = resolve_fuzz()
    assert result is None


def test_run_fuzz_success(tmp_path: Path) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    binary = Path("/usr/local/bin/fuzz")

    mock_result = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="0 type errors\n", stderr=""
    )
    with patch("subprocess.run", return_value=mock_result):
        result = run_fuzz(tex, binary)

    assert result.ok is True
    assert len(result.errors) == 0


def test_run_fuzz_type_error(tmp_path: Path) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    binary = Path("/usr/local/bin/fuzz")

    mock_result = subprocess.CompletedProcess(
        args=[],
        returncode=1,
        stdout="",
        stderr='"spec.tex", line 42, col 5: Type mismatch: expected NAT, got INT\n',
    )
    with patch("subprocess.run", return_value=mock_result):
        result = run_fuzz(tex, binary)

    assert result.ok is False
    assert len(result.errors) == 1
    assert result.errors[0].line == 42
    assert result.errors[0].column == 5
    assert "Type mismatch" in result.errors[0].message


def test_run_fuzz_multiple_errors(tmp_path: Path) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    binary = Path("/usr/local/bin/fuzz")

    mock_result = subprocess.CompletedProcess(
        args=[],
        returncode=1,
        stdout="",
        stderr=(
            '"spec.tex", line 10, col 3: Undeclared variable x\n'
            '"spec.tex", line 20, col 7: Type mismatch\n'
        ),
    )
    with patch("subprocess.run", return_value=mock_result):
        result = run_fuzz(tex, binary)

    assert result.ok is False
    assert len(result.errors) == 2


def test_run_fuzz_unstructured_error(tmp_path: Path) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    binary = Path("/usr/local/bin/fuzz")

    mock_result = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="", stderr="Segmentation fault\n"
    )
    with patch("subprocess.run", return_value=mock_result):
        result = run_fuzz(tex, binary)

    assert result.ok is False
    assert len(result.errors) == 1
    assert "Segmentation fault" in result.errors[0].message
