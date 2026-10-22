"""install_fuzz removes its scratch clone, whatever TMPDIR is.

The clone lives in a ``mktemp -d`` directory under $TMPDIR, removed by an
EXIT trap. install_fuzz cds into that directory to build, so a relative
TMPDIR would leave the trap's ``rm -rf`` naming a path relative to the
clone itself -- nothing -- and the clone would stay. The whole script is run
with fuzz's build tools stubbed (``install_sh_runner``) and a fuzz whose
probe fails, so the build runs to its end and then fails. A TMPDIR that
is a symlink (macOS's /var is one, to /private/var) must resolve to the
real directory, so the clone's path cannot depend on how TMPDIR was
spelled -- nor on CDPATH, which would make the cd that resolves it print
the directory into the captured path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.install_sh_runner import WholeInstall


@pytest.mark.parametrize(
    "tmpdir",
    ["rel-tmp", None, "link-tmp"],
    ids=["relative", "absolute", "symlink"],
)
def test_the_scratch_clone_is_removed_after_a_failed_build(
    tmp_path: Path, tmpdir: str | None
) -> None:
    if tmpdir == "link-tmp":
        (tmp_path / "real-tmp").mkdir()
        (tmp_path / "link-tmp").symlink_to(tmp_path / "real-tmp")
    home = str(tmp_path / "home")
    install = WholeInstall(
        home, args=("--fuzz-only",), fuzz="exit 1", build=True, tmpdir=tmpdir
    )
    run = install.run(tmp_path)

    scratch = tmp_path / (tmpdir or "tmp")
    clones = [call for call in run.calls("git") if call[:1] == ["clone"]]
    assert run.result.returncode == 1
    assert len(clones) == 1, run.calls("git")
    assert Path(clones[0][-1]).is_absolute(), clones[0]
    # pwd -P: the physical directory, whatever symlink TMPDIR went through.
    assert Path(clones[0][-1]).parent == scratch.resolve()
    assert run.calls("make") == [[], ["install"]], "the build never ran"
    assert list(scratch.iterdir()) == [], "the scratch clone was left behind"


def test_a_cdpath_entry_does_not_double_the_scratch_path(tmp_path: Path) -> None:
    # With "." on CDPATH, a cd to the relative scratch path finds it through
    # that entry and prints it; captured, the path would be two lines.
    install = WholeInstall(
        str(tmp_path / "home"),
        args=("--fuzz-only",),
        fuzz="exit 1",
        build=True,
        tmpdir="rel-tmp",
        env=(("CDPATH", ".:/nonexistent"),),
    )
    run = install.run(tmp_path)

    scratch = tmp_path / "rel-tmp"
    clones = [call for call in run.calls("git") if call[:1] == ["clone"]]
    assert run.result.returncode == 1
    assert len(clones) == 1, run.calls("git")
    dest = clones[0][-1]
    assert "\n" not in dest, f"the scratch path is more than one line: {dest!r}"
    assert Path(dest).is_absolute(), dest
    assert Path(dest).parent == scratch.resolve()
    assert list(scratch.iterdir()) == [], "the scratch dir was left behind"
