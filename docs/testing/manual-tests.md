# Acceptance Flight

The canonical user acceptance test for z-spec. Tier 5 of
[`TESTING.md`](../../TESTING.md). It runs **before the PR opens**, against the
**installed** artifact, by a human looking at the output.

## Hard rules

1. **Write the expected outcome before running each step.** Compare after.
   Every difference is a bug — including the ones you would rationalize away.
2. **Test the installed artifact.** `make uat` builds the wheel and installs the
   CLI. The running MCP server still holds the old code until you reconnect it;
   a reinstall does not restart it. A stale server proves nothing.
3. **For any lux surface, look at the window.** Introspection tools give
   Hub-side truth; the window gives what the human sees. They diverge — a scene
   can hold hundreds of elements and render an empty pane.

## Pre-flight

```bash
make check        # must be green first — UAT does not substitute for it
make uat          # build + uv tool install --force dist/*.whl
z-spec --version  # confirm the version you just built
```

Then reconnect the `z-spec` MCP server in the session (or restart the client) so
the MCP tools, the lux menu registration, and the slash commands run the new
code. Confirm with `mcp__plugin_z-spec_zspec__doctor` — it should answer from
the new build.

Run the rows applicable to the change. A change to a shared path (the command
registry, the display, the lux session) runs the whole flight.

## Flight

### Environment

| # | Action | Context | Expected |
|---|--------|---------|----------|
| E1 | `z-spec doctor` | fuzz + probcli installed | both reported present with versions/paths; exit 0 |
| E2 | `z-spec doctor` | `PROBCLI` pointing nowhere | a clear "not found" line naming what to install — not a traceback; non-zero exit |

### Type-checking and model-checking

| # | Action | Context | Expected |
|---|--------|---------|----------|
| T1 | `z-spec check examples/<spec>.tex` | a clean spec | "type-checked" success, exit 0 |
| T2 | `z-spec check examples/<spec>-bad.tex` | a deliberately broken spec | fuzz's error, line-numbered and readable; non-zero exit, no traceback |
| T3 | `z-spec check /nonexistent.tex` | missing file | a typed "file not found" message; no traceback |
| T4 | `z-spec test examples/<spec>.tex` | probcli present | model-check summary (states, transitions) and a saved report path |
| T5 | `z-spec report <saved report>` | report on disk | the same report renders back |
| T6 | same as T1/T4 via the MCP tools (`check`, `test`, `model_check`, `animate`) | reconnected server | identical outcomes to the CLI — the surfaces share one `Command`; any divergence is a parity defect |

### Display and browse (lux)

| # | Action | Context | Expected |
|---|--------|---------|----------|
| D1 | `z-spec show examples/<spec>.tex` | luxd running | the spec renders with its title and body visible in the pane — not an empty frame |
| D2 | `z-spec pick .` / **Z-Spec Browser** menu entry | a real repo with specs | only the repo's **real** specs (in this repo: `examples/`, `plugin/tutorials/`); each labelled with a readable name, not a truncated path; selecting one shows its content |
| D3 | `z-spec pick .` | repo containing scratch dirs (`.tmp/`, `.venv/`, `.git/`, `.pytest_cache/`, pytest temp trees) | scratch and test junk **excluded** — no `.tmp/pytest-of-…/*.tex` in the picker |
| D4 | `z-spec pick <empty dir>` | directory with no specs | a clear "no Z specs found" message — **not** a stranded "Loading…" placeholder |
| D5 | `z-spec show <absolute path outside cwd>` | path outside the project | renders, or a typed failure — never an uncaught crash |
| D6 | **Z-Spec Tutorial** menu entry | installed plugin (`ZSPEC_PLUGIN_ROOT` set) | the intro lessons render with their titles |
| D7 | **Z-Spec Tutorial** menu entry | standalone CLI, no plugin root | either the packaged lessons render or a clean "unavailable" — never a stuck spinner |
| D8 | menu registration | second repo open at the same time | both repos' entries present, grouped, no collision; identity name is ASCII |
| D9 | click `Clients ▸ <repo> ▸ Z-Spec Tutorial`, then `… ▸ Z-Spec Browser` | luxd running, z-spec enabled | each raised frame's **title bar reads exactly the clicked label** — byte-identical, no repo suffix; only a title bar shows this, no in-process test can |

For every D row, capture **both**:

- Hub-side: `list_menus`, `list_scenes`, `inspect_scene`, `list_recent_events`,
  `list_errors`.
- Human-side: the window itself — and a `screenshot` when the row is about
  layout or labels.

### Reports written by agents

| # | Action | Context | Expected |
|---|--------|---------|----------|
| R1 | `save_partition_report` with a valid payload | MCP | report persists; `get_report` reads it back unchanged |
| R2 | `save_audit_report` with a malformed payload | MCP | a validation error naming the offending field; nothing half-written on disk |

## Post-flight

- Record in the PR description which rows ran and what each produced. "Ran the
  flight" without the rows is not evidence.
- Any row that failed is fixed in this PR, then the row is re-run — not filed as
  a follow-up bead.
- Only after the flight passes: local review agents, then open the PR.
