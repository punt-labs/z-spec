"""The stub tools install_probcli_runner puts on a run's PATH.

Each is the text of a ``#!/bin/sh`` script. ``curl`` records every argv
through ``stub_log.StubLog`` and then refuses, serves a fixture, or dies
mid-transfer, as ``CURL_MODE`` and ``FETCH`` in its environment say; the
others stand in for a tool that fails, or for ``uname`` reporting the OS a
scenario's archive is for.
"""

from __future__ import annotations

from typing import Final

from tests.stub_log import StubLog

# CURL_MODE=modern: a curl >= 7.71 that accepts --retry-all-errors.
# CURL_MODE=old: a real pre-7.71 curl -- ANY invocation carrying
#   --retry-all-errors dies with exit 2 before doing anything, exactly as
#   curl 7.68 does; a bare --version still succeeds.
# FETCH=refuse: every download fails with curl's own "couldn't connect" (7).
# FETCH=serve: the download copies $FIXTURE to the -o path.
# FETCH=partial: the transfer dies mid-way (18), leaving partial bytes at -o.
CURL: Final[str] = (
    "#!/bin/sh\n"
    + StubLog.append_line("curl")
    + """for arg in "$@"; do
  if [ "$CURL_MODE" = old ] && [ "$arg" = "--retry-all-errors" ]; then
    echo "curl: option --retry-all-errors: is unknown" >&2
    echo "curl: try 'curl --help' for more information" >&2
    exit 2
  fi
done
for arg in "$@"; do
  if [ "$arg" = "--version" ]; then
    echo "curl 7.68.0 (x86_64-pc-linux-gnu) libcurl/7.68.0 (stub)"
    exit 0
  fi
done
out=""
while [ $# -gt 0 ]; do
  if [ "$1" = "-o" ]; then out="$2"; shift; fi
  shift
done
if [ "$FETCH" = serve ]; then
  cp "$FIXTURE" "$out"
  exit 0
fi
if [ "$FETCH" = partial ]; then
  printf 'partial archive bytes' > "$out"
  echo "curl: (18) transfer closed with outstanding read data remaining" >&2
  exit 18
fi
echo "curl: (7) Failed to connect to stub host" >&2
exit 7
"""
)


def broken_hasher(name: str) -> str:
    """A hash tool that fails as an unreadable file would, printing nothing."""
    return f'#!/bin/sh\necho "{name}: simulated read error" >&2\nexit 1\n'


def refusing(name: str) -> str:
    """A ``name`` that logs its call, then fails as a denied operation would.

    Its message names every argument, so a test can match the reason
    install_probcli reports against what the tool said.
    """
    return (
        "#!/bin/sh\n"
        + StubLog.append_line(name)
        + f'echo "{name}: $*: Operation not permitted" >&2\nexit 1\n'
    )


def uname(system: str) -> str:
    """A ``uname`` whose ``-s`` prints ``system``; any other use exits 2."""
    return f'#!/bin/sh\n[ "$1" = -s ] || exit 2\necho {system}\n'
