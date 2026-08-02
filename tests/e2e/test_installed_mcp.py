"""Drive the installed MCP server over stdio.

The MCP surface is the one clients actually connect to, and it is the surface
where packaging faults surface as a hung "Loading…" rather than an error: the
server starts, the tool answers, and the data file it needed was never in the
wheel. Nothing in-process can see that. This spawns ``z-spec mcp``, completes
the JSON-RPC handshake, and asserts the tool list matches the registry.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import IO, Any, final

import pytest

from punt_zspec.commands.registry import CAPABILITIES

pytestmark = pytest.mark.e2e

_PROTOCOL_VERSION = "2024-11-05"
_TIMEOUT = 60.0


@final
class StdioClient:
    """A minimal newline-delimited JSON-RPC client for an MCP stdio server."""

    _next_id: int
    _proc: subprocess.Popen[str]

    __slots__ = ("_next_id", "_proc")

    def __new__(cls, proc: subprocess.Popen[str]) -> StdioClient:
        self = super().__new__(cls)
        self._proc = proc
        self._next_id = 0
        return self

    @property
    def _stdin(self) -> IO[str]:
        stdin = self._proc.stdin
        assert stdin is not None
        return stdin

    @property
    def _stdout(self) -> IO[str]:
        stdout = self._proc.stdout
        assert stdout is not None
        return stdout

    def notify(self, method: str) -> None:
        """Send a notification — a request with no id and no reply."""
        self._send({"jsonrpc": "2.0", "method": method})

    def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send ``method`` and return the matching response's ``result``."""
        self._next_id += 1
        request_id = self._next_id
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params if params is not None else {},
        }
        self._send(payload)
        return self._await(request_id)

    def _send(self, payload: dict[str, Any]) -> None:
        self._stdin.write(json.dumps(payload) + "\n")
        self._stdin.flush()

    def _await(self, request_id: int) -> Any:
        """Read lines until the response carrying ``request_id`` arrives."""
        for line in self._stdout:
            text = line.strip()
            if not text:
                continue
            message = json.loads(text)
            if message.get("id") != request_id:
                continue  # a notification or an unrelated response
            if "error" in message:
                raise AssertionError(f"server returned an error: {message['error']}")
            return message["result"]
        raise AssertionError(f"server closed stdout before answering id={request_id}")


def _spawn() -> subprocess.Popen[str]:
    binary = shutil.which("z-spec")
    if binary is None:
        pytest.skip("z-spec is not installed — run `make install` first")
    return subprocess.Popen(
        [binary, "mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )


def test_installed_server_exposes_every_registry_tool() -> None:
    proc = _spawn()
    try:
        client = StdioClient(proc)
        client.request(
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "z-spec-e2e", "version": "0"},
            },
        )
        client.notify("notifications/initialized")
        result = client.request("tools/list")

        names = {tool["name"] for tool in result["tools"]}
        missing = [c.mcp_tool for c in CAPABILITIES if c.mcp_tool not in names]
        assert not missing, f"tools absent from the installed server: {missing}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
