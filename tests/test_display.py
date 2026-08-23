"""Tests for LuxDisplay — publishes scenes to the lux Hub over REST, no real lux."""

from __future__ import annotations

from typing import Any

import pytest
from punt_lux import HubUnavailableError
from punt_lux.domain.ids import ConnectionId
from punt_lux.operations import OpError, RenderRequest, SceneShown, Scope
from punt_lux.protocol import TextElement

from punt_zspec.commands.show import DisplayError
from punt_zspec.display import LuxDisplay

_SCOPE = Scope(connection_id=ConnectionId("test-scope"))


def _client_stub(renderer: Any) -> Any:
    class _Client:
        sync = renderer
        scope = _SCOPE

    return _Client()


def _recording_connector(requests: list[tuple[RenderRequest, Scope]]) -> Any:
    class _Renderer:
        def render(
            self, request: RenderRequest, *, scope: Scope
        ) -> SceneShown | OpError:
            requests.append((request, scope))
            return SceneShown(scene_id=request.scene_id)

    stub = _client_stub(_Renderer())

    def connect() -> Any:
        return stub

    return connect


def _op_error_connector(reason: str) -> Any:
    class _Renderer:
        def render(
            self, request: RenderRequest, *, scope: Scope
        ) -> SceneShown | OpError:
            return OpError(code="display_unavailable", reason=reason)

    stub = _client_stub(_Renderer())

    def connect() -> Any:
        return stub

    return connect


def _raising_connector(exc: Exception) -> Any:
    def connect() -> Any:
        raise exc

    return connect


def _scene() -> TextElement:
    return TextElement(id="t", content="hello")


def test_show_publishes_scene_to_hub() -> None:
    requests: list[tuple[RenderRequest, Scope]] = []
    display = LuxDisplay(connect=_recording_connector(requests))

    display.show(_scene(), frame_id="z-spec", frame_title="Z-Spec: s.tex")

    assert len(requests) == 1
    req, scope = requests[0]
    assert req.scene_id == "z-spec"
    assert len(req.elements) == 1
    assert req.elements[0]["kind"] == "text"
    assert req.title == "Z-Spec: s.tex"
    assert req.frame is not None
    assert req.frame.frame_id == "z-spec"
    assert req.frame.frame_title == "Z-Spec: s.tex"
    # The Hub scopes writes; LuxDisplay must pass client.scope through with the
    # RenderRequest, not drop it — a bare render at 0.29 raises at the Protocol.
    assert scope is _SCOPE


def test_show_raises_display_error_when_hub_unavailable() -> None:
    display = LuxDisplay(connect=_raising_connector(HubUnavailableError("luxd down")))

    with pytest.raises(DisplayError, match="luxd down"):
        display.show(_scene(), frame_id="z-spec", frame_title="t")


def test_show_raises_display_error_on_transport_error() -> None:
    # A transport failure mid-render (ConnectionError is an OSError subclass)
    # is a "could not reach the Hub" condition and must become DisplayError so
    # the MCP tools return {ok:false} rather than crashing.
    display = LuxDisplay(connect=_raising_connector(ConnectionError("reset")))

    with pytest.raises(DisplayError, match="reset"):
        display.show(_scene(), frame_id="z-spec", frame_title="t")


def test_show_does_not_mask_a_malformed_request() -> None:
    # A non-I/O error (e.g. a validation error from a request we built wrong)
    # is our bug — it must propagate, not be masked as DisplayError.
    display = LuxDisplay(connect=_raising_connector(ValueError("bad request")))

    with pytest.raises(ValueError, match="bad request"):
        display.show(_scene(), frame_id="z-spec", frame_title="t")


def test_show_raises_display_error_on_hub_rejection() -> None:
    display = LuxDisplay(connect=_op_error_connector("bad scene"))

    with pytest.raises(DisplayError, match="bad scene"):
        display.show(_scene(), frame_id="z-spec", frame_title="t")
