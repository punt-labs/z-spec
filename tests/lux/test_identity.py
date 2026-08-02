"""Tests for ZSpecLuxIdentity — pure app-identity and two-axis label construction."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from punt_zspec.lux.identity import ZSpecLuxIdentity

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_app_name_carries_repo_and_pid() -> None:
    identity = ZSpecLuxIdentity("my-repo", 4242)

    assert identity.app_name == "z-spec / my-repo / #4242"


def test_app_name_is_ascii_but_labels_keep_the_middle_dot() -> None:
    # The identity name is the X-Lux-Client-Name header luxd hashes into the
    # ConnectionId; a non-ASCII separator encodes to different bytes on the WS and
    # REST transports, so luxd links no listen leg and refuses the register. The
    # labels ride register_callback's JSON body (UTF-8), so they keep the "·".
    identity = ZSpecLuxIdentity("my-repo", 4242)

    assert identity.app_name.isascii()
    assert not identity.tutorial_label.isascii()
    assert not identity.browse_label.isascii()


def test_labels_carry_both_tool_and_session_axes() -> None:
    identity = ZSpecLuxIdentity("my-repo", 4242)

    # Tool axis (Tutorial vs Browse) AND session axis (repo + pid) — both are
    # mandatory so two sessions never click the wrong repo's specs.
    assert identity.tutorial_label == "z-spec Tutorial · my-repo · #4242"
    assert identity.browse_label == "z-spec Browse · my-repo · #4242"
    assert identity.tutorial_label != identity.browse_label


def test_client_identity_is_a_30s_app_lease() -> None:
    identity = ZSpecLuxIdentity("my-repo", 4242)

    client_identity = identity.client_identity

    assert client_identity.kind == "app"
    assert client_identity.name == "z-spec / my-repo / #4242"
    assert client_identity.lease_ttl == 30.0


def test_for_session_uses_this_pid_and_the_z_spec_repo() -> None:
    identity = ZSpecLuxIdentity.for_session()

    assert identity.app_name.startswith("z-spec / ")
    assert identity.app_name.endswith(f"#{os.getpid()}")


def test_for_session_resolves_the_enclosing_git_repo(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "src" / "pkg"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    identity = ZSpecLuxIdentity.for_session()

    # Walks up from the cwd to the nearest .git and names the session for it.
    assert identity.app_name == f"z-spec / {tmp_path.name} / #{os.getpid()}"
