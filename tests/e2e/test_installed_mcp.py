"""Drive the installed MCP server over stdio.

The MCP surface is the one clients actually connect to, and it is the surface
where packaging faults surface as a hung "Loading…" rather than an error: the
server starts, the tool answers, and the data file it needed was never in the
wheel. Nothing in-process can see that. This spawns ``z-spec mcp``, completes
the JSON-RPC handshake, and asserts the tool list matches the registry.
"""

from __future__ import annotations

import json
import queue
import shutil
import subprocess
import threading
import time
from typing import IO, Any, NoReturn, Self, final

import pytest

from punt_zspec.commands.registry import CAPABILITIES

pytestmark = pytest.mark.e2e

_PROTOCOL_VERSION = "2024-11-05"
_TIMEOUT = 60.0
# How long one request waits for its reply. A server that starts but never
# answers — an import that hangs, a lifespan that deadlocks — must fail this
# test in seconds with a diagnostic, not stall the job until Actions kills it.
_REQUEST_TIMEOUT = 30.0


@final
class _PipeReader:
    """Drain one of the child's pipes on a daemon thread.

    Both pipes need a reader, for different reasons. stdout is the JSON-RPC
    stream, and reading it through a queue is what gives :meth:`next_line` a
    deadline that a blocking ``readline`` cannot have. stderr is the server's
    log: unread, a chatty server fills the pipe buffer and blocks on its own
    logging. Every line drained is kept, so a failure can quote what the
    server said before it stopped answering.
    """

    _pipe: IO[str]
    _lines: queue.Queue[str | None]
    _seen: list[str]
    __slots__ = ("_lines", "_pipe", "_seen")

    def __new__(cls, pipe: IO[str]) -> Self:
        self = super().__new__(cls)
        self._pipe = pipe
        self._lines = queue.Queue()
        self._seen = []
        threading.Thread(target=self._drain, daemon=True).start()
        return self

    def next_line(self, timeout: float) -> str | None:
        """Return the next line, or ``None`` once the pipe closes.

        ``None`` is the documented end-of-stream value — a distinct outcome
        from ``TimeoutError``, which says the pipe is still open and silent.
        """
        try:
            return self._lines.get(timeout=timeout)
        except queue.Empty:
            msg = f"no output for {timeout:.1f}s"
            raise TimeoutError(msg) from None

    def text(self) -> str:
        """Return every line drained so far — the child's own diagnostics."""
        return "".join(self._seen)

    def _drain(self) -> None:
        for line in self._pipe:
            self._seen.append(line)
            self._lines.put(line)
        self._lines.put(None)


@final
class StdioClient:
    """A minimal newline-delimited JSON-RPC client for an MCP stdio server."""

    _next_id: int
    _proc: subprocess.Popen[str]
    _out: _PipeReader
    _err: _PipeReader

    __slots__ = ("_err", "_next_id", "_out", "_proc")

    def __new__(cls, proc: subprocess.Popen[str]) -> Self:
        stdout, stderr = proc.stdout, proc.stderr
        assert stdout is not None
        assert stderr is not None
        self = super().__new__(cls)
        self._proc = proc
        self._next_id = 0
        self._out = _PipeReader(stdout)
        self._err = _PipeReader(stderr)
        return self

    @property
    def _stdin(self) -> IO[str]:
        stdin = self._proc.stdin
        assert stdin is not None
        return stdin

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
        """Read lines until the response carrying ``request_id`` arrives.

        Bounded by ``_REQUEST_TIMEOUT`` in total, not per line, so a server
        that dribbles notifications forever fails as surely as a silent one.
        """
        deadline = time.monotonic() + _REQUEST_TIMEOUT
        while (remaining := deadline - time.monotonic()) > 0:
            try:
                line = self._out.next_line(remaining)
            except TimeoutError:
                break
            if line is None:
                self._fail(f"server closed stdout before answering id={request_id}")
            text = line.strip()
            if not text:
                continue
            message = json.loads(text)
            if message.get("id") != request_id:
                continue  # a notification or an unrelated response
            if "error" in message:
                self._fail(f"server returned an error: {message['error']}")
            return message["result"]
        self._fail(f"no reply to id={request_id} within {_REQUEST_TIMEOUT:.0f}s")

    def _fail(self, reason: str) -> NoReturn:
        """Raise with the server's stderr attached — the only diagnostic there is."""
        raise AssertionError(f"{reason}\n--- server stderr ---\n{self._err.text()}")


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
