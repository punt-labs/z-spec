# RESUME — z-spec interactive lux menu (feat/lux-normal-path-client)

Handoff for the next agent. Read this fully before touching anything.

## The task (real scope — hold to it)

Upgrade z-spec's lux client to the new punt-lux Hub API (0.22.x:
`LuxRestClient` / `LuxHubClient`) **and register two right-click menu entries**
(Tutorial + Browse) so a click renders in luxd. That is the whole job. It is
**not** a redesign of the spec picker. When in doubt, reuse the display path that
already works (`build_browser_scene` / the `browse` + `show_z_spec` render path);
do not invent new discovery/labelling/layout.

## Branch / PR state

- **Work on ONE branch: `feat/lux-normal-path-client`** (PR **#82**, OPEN). Do not
  create new branches or PRs. Fold everything into this one. (A separate design
  PR #81 was already merged — ignore it; the two-PR split was a mistake, see
  memory `feedback-no-two-pr-ceremony`.)
- HEAD is `2dbd5ea`. **The working tree is DIRTY with my uncommitted changes
  (see below), and `make check` has NOT been re-run/passed since those edits.**

## What actually works (verified live against a real luxd)

The API upgrade + menu registration is done and confirmed: both entries register
first-try, identity name is ASCII (`z-spec / <repo> / #<pid>`), menu labels keep
`·`, cross-repo gives 4 entries/2 groups with no collision, lease sweep works.
Keep this.

## What is BROKEN (found by the operator running it — the part I failed to do)

1. **Browse picker is unusable.** `PickerCommand._discover` `rglob`s the ENTIRE
   cwd and surfaces scratch/test junk (`.tmp/pytest-of-…/*.tex`, `.tmp/probe/*`,
   etc.) as "specs"; tabs are labelled with truncated raw paths; the content pane
   renders empty (838 elements, nothing visible). Screenshot confirmed.
2. **Tutorial is stuck on "Loading…".** The tutorial manifest didn't resolve in
   an installed context (the `__file__`-relative path only works in a dev
   checkout). edt added a `ZSPEC_PLUGIN_ROOT` resolution in `2dbd5ea` — **but it
   has NOT been verified by actually running the Tutorial and seeing lessons
   render.**
3. **Empty content pane** in Browse — root cause unconfirmed (maybe the junk
   specs were empty stubs; maybe a real render bug). Must be diagnosed by
   RUNNING it and inspecting the scene.

Note: the running server the operator tested was an **old build** (identity name
still had `·`, pre-fixes). You MUST rebuild+reinstall+restart to test current
code — a reinstall alone does not restart a running MCP server.

## My uncommitted changes (review, keep or redo — NOT verified by running)

- `src/punt_zspec/browser.py` — `build_spec_picker`: dropped the `root` param,
  label is now `tex_path.stem` (readable, can't crash).
- `src/punt_zspec/commands/picker.py` — `PickerSceneBuilder` Protocol dropped
  `root`; `PickerCommand.run` calls `self._build(specs)`; `_discover` now skips
  hidden dirs via a new `_is_hidden(tex, directory)` (excludes `.tmp/`, `.venv/`,
  `.git/`, `.pytest_cache/`).
- `tests/commands/test_picker.py`, `tests/test_browser.py` — updated to the new
  signature; `test_spec_picker_labels_tabs_by_filename_stem` asserts stem labels.
- Process docs (the build→install→run→verify loop that was skipped):
  `docs/WORKFLOW.md` (three-loop process), `TESTING.md` (five-tier pyramid,
  UAT before the PR), `docs/testing/manual-tests.md` (the acceptance flight),
  and the rewritten `CLAUDE.md`. **Read them.** `make uat` is the entry point.

`git diff` to see them. `make check` last passed at `2dbd5ea`; since my edits I
fixed the 3 mypy/test errors it flagged but did **not** re-run it — assume it is
unverified.

## What to do (in order)

1. `git diff` the uncommitted changes; keep what's right, redo what isn't.
2. `make check` green (unpiped, read the whole thing).
3. **RUN IT — the step that was skipped:** `make build && uv tool install --force
   dist/*.whl`, restart the z-spec MCP server, then actually exercise it:
   - Click **Browse** in this repo (or run `z-spec pick .`); `inspect_scene` the
     `z-spec-picker` scene AND look at the window. Expected: only the real
     `examples/`/`tutorials/` specs, readable stem labels, spec content visible.
   - Click **Tutorial** (in an installed/plugin context with `ZSPEC_PLUGIN_ROOT`);
     expected: the 10 intro lessons render with titles — NOT a stuck spinner.
   - Empty dir → clean "no specs" message, not a stranded placeholder.
4. Compare actual vs expected; fix until Browse and Tutorial **work on screen.**
5. Only then: one commit, push to PR #82. No new branches/PRs, no review loop
   until it works.

## Key files

- `src/punt_zspec/lux/` — the menu client (works): `session.py` (lifespan +
  `_default_tutorial_manifest`), `clients.py`, `menu.py`, `subscription.py`,
  `identity.py`.
- `src/punt_zspec/commands/picker.py` — `PickerCommand` + discovery (the broken
  part; my fix uncommitted).
- `src/punt_zspec/browser.py` — `build_spec_picker` (label) and
  `build_browser_scene` (**the working reference** for rendering specs with
  titles + content; the picker should look like this).
- The `pick` MCP tool (`server.py`), `z-spec pick` CLI verb (`__main__.py`), and
  the Browse menu callback (`subscription.py`) all run `PickerCommand` — fixing
  the command fixes all three.

## Gotchas

- Identity NAME must be ASCII; display richness goes in menu LABELS (memory
  `reference-lux-identity-ascii`; luxd branch decode bug, fixed in lux PR #303).
- Do NOT verify punt-lux APIs against the `../lux` repo venv — branch build,
  stale `0.22.1` version string. `raise_frame` is 0.23-only.
- Tutorial packaging: `ZSPEC_PLUGIN_ROOT` covers the installed plugin; a
  standalone `pip`/wheel install needs `importlib.resources` packaging — bead
  `z-spec-9v6`.

## Beads

`z-spec-2xt` (this feature), `z-spec-i6s` (menu entries), `z-spec-9v6` (wheel
tutorial packaging), `z-spec-90k` (collapse `_raise_scene` to `raise_frame` when
punt-lux 0.23 ships).

## The lesson (do not repeat)

The feature was declared "verified" from unit tests + Hub introspection and taken
to PR without ever being run by a human. That is why Browse (junk specs, path
labels, empty pane) and Tutorial (stuck spinner) were broken on delivery. For any
CLI/MCP/interactive-lux change, the verification of record is RUNNING IT in the
real app and looking at the result. `make check` is necessary, never sufficient.
