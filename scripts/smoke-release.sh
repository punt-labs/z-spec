#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: bash scripts/smoke-release.sh candidate VERSION WHEEL | published VERSION" >&2
  exit 2
}

version=${2:-}
[[ "$version" =~ ^[0-9][0-9A-Za-z.+!-]*$ ]] || usage
case "${1:-}:$#" in
  candidate:3)
    channel="candidate wheel"
    package=$(realpath -- "$3")
    [[ -f "$package" && "$package" == *.whl ]] || usage
    ;;
  published:2)
    channel="production PyPI"
    package="punt-z-spec==$version"
    ;;
  *) usage ;;
esac

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
fuzz=$(command -v fuzz) || {
  echo "fuzz is required; run ./install.sh --fuzz-only and add it to PATH." >&2
  exit 1
}
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
printf 'Testing punt-z-spec %s from %s\n' "$version" "$channel"

uv_bin=$(command -v uv)
clean=(env -i "PATH=$PATH" "HOME=$HOME")
cd "$work"
"${clean[@]}" "$uv_bin" --no-config venv --python 3.13 venv
python="$work/venv/bin/python"
install=("${clean[@]}" "$uv_bin" --no-config pip install --python "$python"
  --default-index https://pypi.org/simple/ --only-binary punt-z-spec)
if [[ "$1" == published ]]; then
  for attempt in 1 2 3; do
    if "${install[@]}" --refresh-package punt-z-spec "$package"; then
      break
    fi
    [[ "$attempt" != 3 ]] || exit 1
    sleep 10
  done
else
  "${install[@]}" "$package"
fi

mkdir -p "$work/home" "$work/repo/.punt-labs/z-spec"
cd "$work/repo"
isolated=(env -i "PATH=$work/venv/bin:/usr/bin:/bin" "HOME=$work/home"
  "GIT_CONFIG_NOSYSTEM=1" "PUNT_TELEMETRY=off" "LUX_SOCKET=$work/no-lux.sock"
  "FUZZ=$fuzz")
"${isolated[@]}" git init --quiet
touch .punt-labs/z-spec/enabled
spec=animation-hints-good.tex
cp "$root/examples/$spec" .
zspec="$work/venv/bin/z-spec"

actual=$("${isolated[@]}" "$zspec" --version)
if [[ "$actual" != "z-spec $version" ]]; then
  printf 'Expected z-spec %s, got %s\n' "$version" "$actual" >&2
  exit 1
fi
output=$("${isolated[@]}" "$zspec" check "$spec")
if [[ "$output" != "fuzz: $spec OK" ]]; then
  printf 'Unexpected CLI check result: %s\n' "$output" >&2
  exit 1
fi
test -s "${spec%.tex}.fuzz.json"
rm -- "${spec%.tex}.fuzz.json"
printf 'PASS: punt-z-spec %s from %s (CLI check)\n' "$version" "$channel"

"${isolated[@]}" "$python" -I - "$zspec" "$spec" <<'PY'
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent


async def main() -> None:
    binary, spec = sys.argv[1:]
    server = StdioServerParameters(command=binary, args=["mcp"], env=dict(os.environ))
    async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("check", {"file": spec})
        content = result.content
        if result.isError or len(content) != 1 or not isinstance(content[0], TextContent):
            raise SystemExit(f"Unexpected MCP response: {result}")
        payload = json.loads(content[0].text)
        if payload.get("ok") is not True or payload.get("errors") != []:
            raise SystemExit(f"MCP check did not type-check {spec}: {payload}")
        report = json.loads(Path(spec).with_suffix(".fuzz.json").read_text(encoding="utf-8"))
        if report != payload:
            raise SystemExit(f"MCP report differs from the check result: {report}")


asyncio.run(asyncio.wait_for(main(), timeout=30))
PY
printf 'PASS: punt-z-spec %s from %s (MCP stdio check)\n' "$version" "$channel"
