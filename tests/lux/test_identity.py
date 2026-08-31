"""Tests for ZSpecLuxIdentity — what one z-spec server declares itself to luxd as."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from punt_lux.connection_identity import connection_for
from punt_lux.domain.hub import applet_name_format

from punt_zspec.lux.identity import ZSpecLuxIdentity

if TYPE_CHECKING:
    from pytest import MonkeyPatch

_PROJECT = Path("/work/my-repo")


def test_the_identity_is_an_applet_declaring_the_project_as_its_repo() -> None:
    identity = ZSpecLuxIdentity(_PROJECT).client_identity

    assert identity.kind == "applet"
    assert identity.repo == "/work/my-repo"


def test_luxd_labels_the_client_from_the_repo_not_the_declared_name() -> None:
    # menu_label is `_repo_name or name`, so declaring a repo is what makes the
    # Clients submenu read "my-repo" instead of the connection token in the name.
    identity = ZSpecLuxIdentity(_PROJECT).client_identity

    assert identity.menu_label == "my-repo"


def test_the_name_is_the_four_part_shape_the_domain_helper_writes() -> None:
    # ClientIdentity's applet validator rejects any name not matching
    # ``lux · <repo> · #<pid> · <program>`` (DES-067). Delegating to
    # applet_name_format.format_name keeps the writer aligned with the reader —
    # a format change upstream fails here as a signature mismatch, not silently.
    identity = ZSpecLuxIdentity(_PROJECT).client_identity

    expected = applet_name_format.format_name(
        repo_name="my-repo", session_pid=os.getppid(), program="z-spec"
    )
    assert identity.name == expected


def test_the_name_carries_the_session_pid_not_this_process_pid() -> None:
    """The pid in the name is the Claude session's — the server's parent.

    luxd groups Clients-menu entries by the session pid parsed from the applet
    name. Stamping the server's own pid puts z-spec in a submenu of one, apart
    from every other applet of the same session (vox-panel stamps the parent).
    In-process the two are distinguishable: getpid() is never getppid().
    """
    identity = ZSpecLuxIdentity(_PROJECT).client_identity

    stamped = applet_name_format.session_pid_from_name(identity.name)
    assert stamped == os.getppid()
    assert stamped != os.getpid()


def test_two_sessions_on_one_repo_own_distinct_connections(
    monkeypatch: MonkeyPatch,
) -> None:
    """Same repository, two Claude sessions, two connections — not one.

    luxd hashes (kind, name, repo, agent) into the connection id, and a second
    arrival on one connection takes the listener slot and clears the callbacks
    the first registered. Two sessions have two distinct session pids, so the
    session pid embedded in the name is what stops that.
    """
    monkeypatch.setattr(os, "getppid", lambda: 111)
    first = ZSpecLuxIdentity(_PROJECT).client_identity
    monkeypatch.setattr(os, "getppid", lambda: 222)
    second = ZSpecLuxIdentity(_PROJECT).client_identity

    assert connection_for(first.model_dump()) != connection_for(second.model_dump())
    # ...and they still read identically in the menu; luxd numbers the collision.
    assert first.menu_label == second.menu_label == "my-repo"


def test_no_lease_is_declared_so_the_applet_kind_length_applies() -> None:
    """Absent is luxd's "use my kind's length" — the documented default.

    An applet's length is already written for a client that lives and dies with a
    session. Declaring a number would copy a constant luxd owns and pin us to
    today's value of it.
    """
    identity = ZSpecLuxIdentity(_PROJECT).client_identity

    assert identity.lease_ttl is None


def test_the_same_identity_object_backs_every_leg() -> None:
    # Both legs must hand luxd one identity: luxd links a REST menu registration
    # to the listen leg through the connection both derive from it.
    identity = ZSpecLuxIdentity(_PROJECT)

    assert identity.client_identity is identity.client_identity


def test_for_session_declares_the_session_pid(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

    identity = ZSpecLuxIdentity.for_session().client_identity

    assert applet_name_format.session_pid_from_name(identity.name) == os.getppid()


def test_for_session_prefers_project_dir_env_over_cwd(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # The plugin-launched server's cwd is the plugin checkout; CLAUDE_PROJECT_DIR
    # names the user's project. Declaring cwd would label every session's submenu
    # "z-spec" instead of the repository the user has open.
    project = tmp_path / "user-project"
    project.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.chdir(tmp_path)

    identity = ZSpecLuxIdentity.for_session().client_identity

    assert identity.repo == str(project)
    assert identity.menu_label == "user-project"


def test_for_session_declares_the_cwd_where_no_project_dir_is_set(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The standalone CLI case: cwd is the user's project, and it is absolute.

    ``ClientIdentity`` rejects a relative or blank repo, so the fallback has to
    yield an absolute path or the whole session build raises.
    """
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)

    identity = ZSpecLuxIdentity.for_session().client_identity

    assert Path(identity.repo or "").is_absolute()
