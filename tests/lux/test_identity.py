"""Tests for ZSpecLuxIdentity — what one z-spec server declares itself to luxd as."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from punt_lux.connection_identity import connection_for

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


def test_the_name_is_the_connection_token_carrying_this_process_pid() -> None:
    # The name is hashed into the connection id with kind, repo, and agent. The
    # pid is what keeps two sessions on one repository off a single connection,
    # where the second would take the listener slot and clear the first's
    # callbacks. It is this process's own — a pid naming another would lie.
    identity = ZSpecLuxIdentity(_PROJECT).client_identity

    assert identity.name == f"z-spec #{os.getpid()}"


def test_two_sessions_on_one_repo_own_distinct_connections(
    monkeypatch: MonkeyPatch,
) -> None:
    """Same repository, two server processes, two connections — not one.

    luxd hashes (kind, name, repo, agent) into the connection id, and a second
    arrival on one connection takes the listener slot and clears the callbacks
    the first registered. The pid in the name is what stops that.
    """
    monkeypatch.setattr(os, "getpid", lambda: 111)
    first = ZSpecLuxIdentity(_PROJECT).client_identity
    monkeypatch.setattr(os, "getpid", lambda: 222)
    second = ZSpecLuxIdentity(_PROJECT).client_identity

    assert connection_for(first.model_dump()) != connection_for(second.model_dump())
    # ...and they still read identically in the menu; luxd numbers the collision.
    assert first.menu_label == second.menu_label == "my-repo"


def test_the_declared_lease_is_the_applet_convention() -> None:
    """60s: the length written for a client that lives and dies with a session.

    The listen leg renews every 15s, so four beats may be lost before the entries
    go — long enough to ride out a luxd restart, short enough that a killed
    session's entries do not linger. The 30s this replaces was inherited from
    voxd, a machine-wide daemon with a different lifetime.
    """
    identity = ZSpecLuxIdentity(_PROJECT).client_identity

    assert identity.lease_ttl == 60.0


def test_the_same_identity_object_backs_every_leg() -> None:
    # Both legs must hand luxd one identity: luxd links a REST menu registration
    # to the listen leg through the connection both derive from it.
    identity = ZSpecLuxIdentity(_PROJECT)

    assert identity.client_identity is identity.client_identity


def test_for_session_declares_this_pid(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

    identity = ZSpecLuxIdentity.for_session().client_identity

    assert identity.name == f"z-spec #{os.getpid()}"


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
