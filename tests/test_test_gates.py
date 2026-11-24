"""Exercise local test selection and enforcement of quarantine metadata."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

from tools.test_changed import select_tests
from tools.test_quarantine import pytest_collection_modifyitems, quarantine_is_valid

_ROOT = Path(__file__).resolve().parents[1]


def test_precommit_tests_the_index_not_the_working_tree(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    (tmp_path / "tests").mkdir()
    probe = tmp_path / "tests/test_probe.py"
    probe.write_text("def test_probe():\n    assert False, 'index-only failure'\n")
    subprocess.run(["git", "add", "tests/test_probe.py"], cwd=tmp_path, check=True)
    probe.write_text("def test_probe():\n    assert True\n")

    result = subprocess.run(
        [sys.executable, str(_ROOT / "tools/test_changed.py")],
        cwd=tmp_path,
        env={**os.environ, "PYTEST_ADDOPTS": f"--basetemp={tmp_path / 'child'}"},
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 1, result.stderr
    assert "AssertionError: index-only failure" in result.stdout
    assert probe.read_text() == "def test_probe():\n    assert True\n"


def test_changed_module_and_test_select_relevant_paths(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    matching = tests / "test_fuzz.py"
    matching.write_text("from punt_zspec.fuzz import resolve_fuzz\n")
    unrelated = tests / "test_prob.py"
    unrelated.write_text("from punt_zspec.prob import resolve_probcli\n")
    staged = {Path("src/punt_zspec/fuzz.py"), unrelated.relative_to(tmp_path)}

    assert select_tests(tmp_path, staged) == sorted(
        path.relative_to(tmp_path) for path in (matching, unrelated)
    )


@pytest.mark.parametrize(
    "path", ["tests/conftest.py", "src/punt_zspec/unmapped.py", "uv.lock"]
)
def test_shared_or_unmapped_changes_select_default_suite(
    tmp_path: Path, path: str
) -> None:
    assert select_tests(tmp_path, {Path(path)}) is None


def test_docs_only_changes_do_not_select_python_tests(tmp_path: Path) -> None:
    assert select_tests(tmp_path, {Path("TESTING.md")}) == []


def test_indirect_source_consumers_select_default_suite(tmp_path: Path) -> None:
    source = tmp_path / "src/punt_zspec"
    source.mkdir(parents=True)
    (source / "command.py").write_text("from .prob import run_model_check\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_prob.py").write_text("from punt_zspec.prob import run_model_check\n")

    assert select_tests(tmp_path, {Path("src/punt_zspec/prob.py")}) is None


@pytest.mark.parametrize(
    ("issue", "owner", "reason", "expires", "valid"),
    [
        ("PL-12", "tester", "intermittent timeout", "2026-11-24", True),
        ("PL-12", "tester", "intermittent timeout", "2026-12-08", True),
        ("#12", "tester", "intermittent timeout", "2026-11-25", False),
        ("PL-12", " ", "intermittent timeout", "2026-11-25", False),
        ("PL-12", "tester", "", "2026-11-25", False),
        ("PL-12", "tester", "intermittent timeout", "2026-11-23", False),
        ("PL-12", "tester", "intermittent timeout", "2026-12-09", False),
        ("PL-12", "tester", "intermittent timeout", "2026-11-31", False),
    ],
)
def test_quarantine_requires_an_owned_and_near_term_deadline(
    issue: str, owner: str, reason: str, expires: str, valid: bool
) -> None:
    mark = pytest.mark.quarantine(
        issue=issue, owner=owner, reason=reason, expires=expires
    ).mark
    assert quarantine_is_valid(mark, date(2026, 11, 24)) is valid


def test_collection_rejects_invalid_quarantine() -> None:
    item = Mock(spec=pytest.Item, nodeid="tests/test_example.py::test_flaky")
    item.iter_markers.return_value = [pytest.mark.quarantine().mark]

    with pytest.raises(pytest.UsageError, match="test_flaky: quarantine requires"):
        pytest_collection_modifyitems([item])
