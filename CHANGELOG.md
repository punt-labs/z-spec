# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.20.0] - 2026-08-29

### Added

- **Static gate against the manifest bug that broke plugin load in 0.18.0–0.19.0.** `tests/test_plugin_manifest.py` reads `plugin/.claude-plugin/plugin.json` and refuses any spelling of `hooks/hooks.json` in the `hooks` field whenever `plugin/hooks/hooks.json` exists on disk — the exact invariant Claude Code enforces at plugin load. Runs as part of `make check` in milliseconds, needs no `claude` CLI or subprocess. Verified positive (passes on the current fixed manifest) and negative (fails with a clear message when the bad `"hooks": "./hooks/hooks.json"` line is reintroduced). Closes the invisible-bug window that let #106 ship — if anyone re-adds the field, CI fails before the release ever runs.

### Fixed

- **`/z-spec:setup`'s probcli install pointed at a dead URL and failed silently.** `plugin/commands/setup.md` downloaded probcli from `prob.hhu.de/downloads/prob2-latest/...`, which 404s on every platform; `curl -L -o` with no `-f` saved the HTML error page to disk under the archive's name and exited 0, so the install reported success while installing nothing — `z-spec doctor` later reported `probcli: NOT FOUND` with nothing pointing back at the cause. Both platform blocks now point at `stups.hhu-hosting.de/downloads/prob/tcltk/releases`, every download uses `-f` to fail loudly on a bad response, and the archive is verified as the correct type before extraction. Pinned to probcli **1.15.1** rather than the newest 1.16.1 — ProB 1.16.0 changed its `-coverage` census output to a format `src/punt_zspec/coverage.py` cannot yet read (tracked as bead `z-spec-v0m`); pinning the newer release would have "fixed" the install while silently breaking every spec's coverage check.

## [0.19.1] - 2026-08-23

### Changed

- **README restructured to match the org [README standard](https://github.com/punt-labs/punt-kit/blob/main/standards/readme.md).** Added PyPI + Python badges and pointed the CI badge at `test.yml`, added a one-paragraph description before the "What is Z?" preamble, dropped in-prose punt-lux version numbers (`punt-lux 0.22.1+`, `punt-lux 0.21+`), and moved the contributor-facing content — the dev-vs-prod plugin swap, release flow, and project structure — out of `README.md` into `docs/development.md` so the README stays user-facing. Added a `## Documentation` index pointing at `docs/development.md`, `docs/WORKFLOW.md`, `TESTING.md`, `docs/design/`, and `CHANGELOG.md`. Every relative markdown link in `README.md` was converted to an absolute GitHub URL so it renders correctly when PyPI uses `README.md` as the package long description.

- **PR/FAQ updated to reflect the current product (v0.19.0, 21 commands, shipped on PyPI + marketplace).** Version citations moved off `v0.2.0` / `15 commands` on the Press Release dateline, the Competitors FAQ moat sizing, the Validation checklist item, the Technical/Timeline claim ("Z Spec is at v0.19.0 with 21 commands shipped, on PyPI as `punt-z-spec` and on the Punt Labs plugin marketplace"), and the Feasibility risk row. Feature Appendix reclassified: the Should Do lane is tagged inline as **Shipped** for the six items that have landed (`model2code`, `audit`, `prove`, `oracle`, `refine`, B-Method) and **Open** for Tutor mode (beads `z-spec-p4a`, `z-spec-yfv`); `elaborate` was added; the standalone CLI + MCP is now a shipped Should Do item; and the "Standalone operation outside Claude Code" Won't Do entry was struck because the CLI now runs standalone via `--no-plugin`. The Feasibility risk was bumped from Green/Low to Amber/Medium: performance on a single-user machine and the unmapped hardware-to-scale equation are called out, along with the observation that a hosted deployment has not been evaluated. The Revenue model FAQ was corrected — the sibling Punt Labs tools (Quarry, Biff, Vox, Lux) are not commercial products today. The scaling FAQ example was corrected to a 5-mode state machine and the "first tool to explore Z + LLMs" claim was softened. Working Backwards document version bumped to v2.1.

### Fixed

- **The plugin failed to load with a duplicate-hooks error: `plugin.json` redundantly declared `hooks`.** `plugin/.claude-plugin/plugin.json` carried `"hooks": "./hooks/hooks.json"`, but Claude Code auto-loads every plugin's `hooks/hooks.json` by convention with no manifest reference needed; the `hooks` field is for *additional* hook files only. Pointing it at the same file Claude Code already loaded made `claude plugin list` report `z-spec@punt-labs` as failed to load, taking every slash command and hook down with it. The `z-spec` CLI and its stdio MCP server were unaffected — neither goes through plugin load. Confirmed against every other punt-labs plugin (beadle, biff, ethos, lux, prfaq, quarry, vox): the five that ship a `hooks/hooks.json` all declare no `hooks` field in their manifest and load correctly; z-spec was the outlier. Closes #106.

### Removed

- **Stray `.biff` config at the repo root.** Legacy peering file from the earlier biff bootstrap; biff resolves its own config elsewhere and does not read the root file.

## [0.19.0] - 2026-08-23

### Changed

- **`punt-lux` pin advanced to `>=0.29,<0.30` and the render/menu paths migrated to `LuxClient.sync`.** The 0.28→0.29 release deleted `punt_lux/rest_client.py`; `LuxRestClient` is gone from every path, so the `from punt_lux.rest_client import LuxRestClient` import in `display.py` no longer resolves. `ZSpecLuxClients.rest()` now returns `LuxClient.for_identity(...).sync` — the same underlying transport typed as the `SyncOps` Protocol — and a new `ZSpecLuxClients.lux_client()` returns the `LuxClient` itself so `LuxDisplay` can pair `client.sync.render(request, scope=client.scope)` directly on the concrete client. `HubUnavailableError` imports standardize on `from punt_lux import HubUnavailableError` everywhere. Ports, commands, CLI verbs, and the `asyncio.to_thread` wraps in `click.py`, `menu.py`, and `subscription.py` are unchanged: the sync surface is preserved end to end.

- **The applet name shown in luxd's Details pane now carries a hex PID rather than decimal**, per the four-part `lux · <repo> · #<pid-hex> · <program>` shape `punt_lux.domain.hub.applet_name_format.format_name` enforces (`f"{prefix}{pid:x}"`, with the regex accepting hex only). z-spec cannot work around this without breaking the format's own regex. Anyone who used to run `ps -p <pid-from-Details-pane>` needs `printf '%d' 0x<pid>` first.

## [0.18.2] - 2026-08-20

### Changed

- **The shippable plugin surface moved to `plugin/`, so a marketplace install can fetch only the plugin.** The current `"source": "url"` marketplace entry clones the whole repository — `src/`, `tests/`, `tools/`, `docs/`, `research/`, the spec corpus, and this repo's own `.punt-labs/` and `.claude/` working state — to deliver 44 command prompts, one hooks registration, one hook script, and a manifest. `.claude-plugin/`, `commands/`, `hooks/`, `reference/`, `templates/`, and `tutorials/` now sit under a single `plugin/` directory, which lets the entry use Claude Code's `git-subdir` source (`"source": "git-subdir"`, `"path": "plugin"`) — a blobless partial clone plus `git sparse-checkout set --cone plugin`. Measured against this branch on GitHub: 89 files / 1.5 MB of working tree (2.2 MB including `.git`) versus 336 files / 4.1 MB (5.8 MB including `.git`) for an equivalent shallow full clone — `src/`, `tests/`, `tools/`, `docs/`, `examples/`, `research/`, `scripts/`, `.github/`, `.beads/`, `.claude/`, and `.punt-labs/` are all absent. Cone mode always materializes the files sitting in the *repo root*, so the 24 root files (780 KB, chiefly `uv.lock` at 232 KB and `prfaq.pdf` at 195 KB) still travel with an install; `plugin/` itself is 65 files and 752 KB. Shrinking that remainder means moving root documents into a subdirectory, which this change does not attempt. The reference library, the templates, and the tutorials are inside the surface because the plugin reads them at run time or names them in its prompts, and a directory left outside `plugin/` is simply absent from an install: the commands cite their reference documents as `reference/<name>.md`, a plugin-root-relative path that keeps resolving, and the lux Tutorial entry resolves `$ZSPEC_PLUGIN_ROOT/tutorials/intro/manifest.toml`. `examples/` deliberately stays at the root — it is the spec corpus `make check` gates, not plugin content. Nothing inside the surface needed rewriting, since `plugin.json`'s `hooks` path and `hooks.json`'s `${CLAUDE_PLUGIN_ROOT}/hooks/suppress-output.sh` are both plugin-root-relative and the whole surface moved together. One consequence for anyone working in this repo: a dev session loads `claude --plugin-dir plugin`, not `--plugin-dir .`, because `CLAUDE_PLUGIN_ROOT` has to name the same directory a real install checks out; the dev manifest's `uv run --directory ${CLAUDE_PLUGIN_ROOT} z-spec mcp` still finds this project because uv discovers a project by walking up from the directory it is given. No user-visible behavior change — existing installs are unaffected until the marketplace entry is repointed.

### Fixed

- **The lux Tutorial entry resolved a directory that no longer exists when the plugin env is absent.** `ZSpecLuxSession._default_tutorial_manifest` falls back to a src-layout path when `ZSPEC_PLUGIN_ROOT` is unset — the standalone-CLI case — and that path was `<repo>/tutorials`, which the move emptied. Its test asserted the resolved path by recomputing it the way the implementation does, so it would have passed either way; it now also asserts the manifest is a file that exists, which is the only form of the assertion that fails when the tutorials move again.

- **The shipped probcli guide pointed at two files no user has.** `plugin/reference/probcli-guide.md` cited `examples/animation-hints-good.tex` and `examples/animation-hints-bad.tex` as paths. That resolved while the whole repository was the plugin; from a `plugin/`-only install it names nothing, silently, in the one document a reader consults when animation misbehaves. They are now GitHub URLs — the corpus is gated by this repository's `make check` and deliberately does not ship, so a path was the wrong kind of citation even before the move. Verified from a real sparse checkout: every other path the surface cites — `reference/*.md`, `commands/model2code.md`, `templates/preamble.tex`, `tutorials/intro/manifest.toml` and all ten lesson files, `hooks/suppress-output.sh` — resolves inside `plugin/`.

- **`release-plugin.sh` could tag a prod release with the `-dev` command twins still in it.** The twins are collected by `while read … done < <(find "$COMMANDS_DIR" …)`, and a process substitution's exit status is invisible to `set -e`. With a wrong `COMMANDS_DIR` the `find` fails, the loop reads nothing, and the resulting empty list is indistinguishable from "this tree has no twins": the script printed `No -dev commands found — name and MCP swap only` and went on to commit. Demonstrated against a nonexistent path. The directory is a precondition and is now asserted before the `find`.

- **`restore-dev-plugin.sh` staged the commands directory whether or not it restored anything.** An unconditional `git add` succeeds either way, so a restore that recovered nothing still produced a commit that looked like a success. The `git add` now sits inside the branch that performs the checkout, which makes an empty index — and `git commit`'s refusal — the signal.

- **`restore-dev-plugin.sh` no-opped instead of refusing when aimed at a release-prep commit from a different layout.** It restored the `-dev` command twins only when `git ls-tree <commit>^ -- <commands dir>/` mentioned a `-dev.md` file, and treated an empty listing as "the parent had no twins". An empty listing means the parent tree has no such directory at all, in which case every path in the script silently does nothing; it now reports that and exits non-zero.

- **`plugin/hooks/suppress-output.sh` was linted by nothing, and `make lint` ran no shellcheck at all.** CI's `lint.yml` covered `scripts/*.sh` and `install.sh`; the Makefile covered neither, so a shell fault in the one script that ships to users was invisible locally and in CI. `make lint` and `lint.yml` now run the identical command over `scripts/*.sh install.sh plugin/hooks/*.sh`.

- **`make lint` could not pass in a checkout with a git worktree.** The `**/*.md` glob descended into `.worktrees/<branch>/.venv/`, reporting 200+ markdownlint errors in dependency READMEs — while CI, which has no worktree, stayed green. `.markdownlint-cli2.jsonc` now ignores `.worktrees/` and nested `.venv/` directories; the top-level `.venv/` entry only ever matched the root one.

## [0.18.1] - 2026-08-19

### Fixed

- **Installing the plugin no longer requires a GitHub SSH key.** z-spec ships through the Punt Labs marketplace, and `claude plugin install` clones the plugin repo *with submodules*. `.gitmodules` mounted the org identity registry `punt-labs/team` at `.punt-labs/ethos/` over the SSH URL `git@github.com:punt-labs/team.git`, so a user without a key got `fatal: clone of 'git@github.com:punt-labs/team.git' into submodule path ... failed` / `Failed to clone '.punt-labs/ethos' a second time, aborting`, and the install stopped there. `punt-labs/team` being a public repo does not help: SSH authentication fails before repo visibility is consulted. Rewriting the URL to HTTPS would have fixed the auth failure while still copying 1 MB of internal identity data onto every user's disk, so the submodule is removed instead — see Removed.

- Action pin comments now state the version actually pinned:
  `actions/checkout` was pinned to v7.0.1's SHA but labelled `# v4` in
  seven places. The SHA is the security control, but the comment is the
  only part a human reads — a wrong one hides a stale pin from every
  review, which is how `gh-action-pypi-publish` broke punt-kit's 0.12.0
  release. No SHA changed.

### Removed

- **The `.punt-labs/ethos` git submodule**, and with it the 247 files of the org identity registry — identities, personalities, writing styles, roles, teams — that every plugin install was copying onto the user's machine. The org-wide convention that each project mounts `punt-labs/team` there does not apply to a repo that is cloned onto strangers' machines, the same exception `punt-labs/claude-plugins` already carries. Identity resolves from the global `~/.punt-labs/ethos/` at runtime, and the repo-local pointer `.punt-labs/ethos.yaml` (`agent: claude`, `team: formal-methods`) is kept — 35 bytes of this project's own configuration, not the roster. The mount path is gitignored so a later `ethos` run cannot re-commit it.

- **Eighteen `.claude/agents/*.md` files for specialists who do no work here** — the Go, Swift, Kubernetes and product agents ethos deposits into every repo it touches. `.gitignore` has documented a per-agent allowlist since the agent files were added, naming z-spec's own team; the list of names it introduces was never actually present, because the canonical rollout owns that block and its blanket `!.claude/agents/` was what took effect. The rule the comment describes now exists, below the repo-specific marker where the rollout will not clobber it: `adb`, `adt`, `dna`, `edt`, `gvr`, `jms`, `jra`, `mdm`, `rmh` — the delegation table in `CLAUDE.md` exactly. The files stay on disk where ethos put them; they are only untracked.

### Added

- `OPENROUTER_API_KEY` wired up in `.envrc` (canonical envrc rollout).

## [0.18.0] - 2026-08-09

### Fixed

- **The spec model-check gate could not fail** --- `make test-z-*` decided pass or fail from probcli's exit status, and probcli exits 0 when it finds a counterexample: it prints `*** COUNTER EXAMPLE FOUND ***` and `Total Errors: 1`, then returns success. A specification with a real violation passed the gate while the violation scrolled past in the output. `z-spec model-check` was already correct here — the engine matched the counterexample text and set `ProbReport.ok` to false — so only the Makefile read the wrong channel. Verified by construction with a deadlocking specification that exits 0 under the old recipe and 1 under the new one.

- **Operation coverage was inferred rather than measured** --- `_build_coverage` never passed `-coverage` to probcli. It scanned animation output for operation names near the words "execute" or "fired" and set `times_fired` to 1 for anything it matched. On `oracle-protocol.tex` the applet rendered `Coverage: 3/3 ops` with counts 1, 1, 1 while probcli's own census reports 5 operations firing 6, 6, 3, 1 and 1 — wrong in the numerator, the denominator, and every count. On a specification with an operation that could never fire it rendered `Coverage: 0/4` while the report said the run was fine and the gate passed: three different answers about one run, none of them measured. The census is now parsed from probcli, and an operation that never fires fails the gate.

- **`ALL OPERATIONS COVERED` was used as a run verdict** --- probcli prints that banner mid-run and reports what it found afterwards, so a run that covered every operation and then deadlocked was classified as passed. The counterexample is now tested first and unconditionally, and the banner is gone from the marker table: it answers the coverage question, not "did this run find anything."

- **An incomplete exploration was reported as a clean pass** --- when `MAX_OPERATIONS` is too small probcli prints `No counter example found. However, not all transitions were computed !` and exits 0. The code contained a branch mapping that warning to a `warning` status, and it was unreachable: the "no counter example found" test always fired first, because probcli prints both strings on one line. So the file asserted it handled incompleteness while doing the opposite, and a reader auditing it saw the case covered. `tests/fixtures/probcli/specs/hidden-deadlock-bad.tex` demonstrates why this matters: it deadlocks, and at `MAX_OPERATIONS=3` probcli reports `deadlocked:0`, `UNCOVERED_OPERATIONS (0)`, "all open states visited" and exit 0 — every signal of a clean run. The verdicts are now separated by what truncation does to them: a counterexample is existential and survives, so it is tested first; the absence of one is universal and cannot be claimed, so incompleteness outranks it; coverage is monotone under exploration, so `UNCOVERED_OPERATIONS (0)` still passes.

- **A model check that outran its timeout raised instead of reporting** --- `_run_probcli` passed a timeout to `subprocess.run` with no `except subprocess.TimeoutExpired`, so a long-running specification produced a forty-line traceback out of `make check`. `TESTING.md` requires a wrapper to treat a tool that does not answer as normal operating input. Reproduced independently by two people within an hour, on a loaded machine and on an unloaded one, which is also why a green `make check` on one machine was not evidence of anything on another. The process cap is now its own constant rather than derived from probcli's `TIME_OUT`, which bounds a single internal computation: tying them meant every raise of the solve budget also lengthened how long a genuinely hung process was waited on.

- **Five specifications contained operations that no execution could reach** --- found by the repaired gate, in `claude-code.tex` and its four derivatives, from three unrelated causes. `EndSession` set `sessionPhase' = spEnded` while emptying `sessionId`, which the State invariant forbids, so the terminal phase was unreachable in all five. In the vox specification `EndSession` also disabled the facilities `FarewellSession` needs: it cleared `notifyMode`, which that operation's precondition names, and `speakMode`, which its prose requires — so the file said a farewell is spoken as the session shuts down over mathematics in which it could not fire, and then, after the first repair, over mathematics in which it fired silently. In the quarry specification `Init` pinned three capture flags and every operation framed them constant, so the document promised each capture layer could be independently disabled while making that unobservable; the configuration now enters as inputs on the `SessionStart` operations, where the hook that reads it runs. A `SessionOver` schema declares the intended halt, which the deadlock check needs in order to mean anything now that `spEnded` is reachable. Every specification in `examples/` now reaches `UNCOVERED_OPERATIONS (0)`.

- **The generated oracle could not distinguish a rejected operation from a no-op success** --- `/z-spec:oracle` emitted a bare state object per command, and the protocol also specified that an operation whose precondition fails "outputs the state unchanged". Those two rules collide. Given `Withdraw` requiring `amount \leq balance` and a balance of 20, `Withdraw 500` (rejected) and `Withdraw 0` (accepted, no change) produced byte-identical lines. A property-based driver comparing traces could not tell them apart, so it could not assert the one property the harness exists to establish — that the implementation accepts exactly what the specification accepts. An implementation permitting an illegal withdrawal produced the same observable trace as one that correctly refused, and its tests passed. Every oracle line now carries a verdict envelope, `{"state": {...}, "ok": true}`, with `ok: false` and a `reason` naming the violated predicate on rejection; the initial state emitted at startup is enveloped too. The reference Lean implementation, the Python/TypeScript/Swift/Kotlin driver templates, and their `execute_concrete_op` stubs all move with it — the drivers now compare the verdict *before* the state, because state alone hides the disagreement whenever the rejected operation would not have changed the state anyway. The envelope design is Eric Bowman's, from `ebowman/z-spec`; this repo's framing and startup semantics are retained, and the two halves are merged.

### Added

- **Prompt contract tests (`tests/commands/test_prompt_contracts.py`)** --- `commands/*.md` is 17,318 lines, the largest surface this project ships, and until now the only entirely untested one. `check-dev-commands` verified that each `-dev` twin *matched* its prod source, which two identical copies of a wrong protocol satisfy perfectly: it tests synchronisation, not correctness. A prompt is executed by a model, so most of its content cannot be asserted deterministically — but *internal consistency* can be. A prompt that both specifies a wire protocol and embeds a reference implementation of it must not contradict itself, and that is exactly the defect above. The suite parses the fenced blocks out of every command prompt, normalising `//` annotations and `<angle-bracket>` placeholders so schema templates and worked examples are checked alike, then asserts that every JSON example actually parses and that each oracle output carries its verdict and reason. 48 cases; the oracle contracts fail against the previous documents, which is how the fix was verified.

### Security

- **Nine open advisories closed across five transitive dependencies, including one critical** --- none of these are direct dependencies; all arrive through `mcp` and `punt-lux`, which is why four separate Dependabot pull requests each moved one leaf and none of them touched the critical. `fastmcp` 3.1.0 → 3.4.6 closes an SSRF and path-traversal hole in the OpenAPI provider (the critical; first patched in 3.2.0) and a missing consent verification in the OAuth proxy callback. `cryptography` 46.0.5 → 50.0.0 closes a Bleichenbacher oracle in PKCS#7 `EnvelopedData` decryption, a duplicate self-signed intermediate path issue, and a vulnerable OpenSSL bundled in the wheels. `pyjwt` 2.11.0 → 2.13.0 closes a public-key-JWK-accepted-as-HMAC-secret forgery and unknown `crit` header extensions being accepted. `python-multipart` 0.0.22 → 0.0.32 closes quadratic-time querystring parsing and unbounded multipart denial of service. `pydantic-settings` 2.13.1 → 2.15.0 rides along in the same resolution. Lockfile-only: no constraint in `pyproject.toml` changed, so this is a `uv.lock` bump verified by resolution rather than a version-range edit. The `fastmcp` jump spans three minor versions of the framework the MCP server is built on, so it was verified by tier 5 — `make uat` then the installed binary and the server driven over stdio — not by `make check` alone.

### Added

- **Per-repo enablement (`z-spec enable` / `z-spec disable`)** --- z-spec's MCP server registered two lux menu entries in its FastMCP lifespan with no enablement gate, and because the plugin loads in every Claude Code session regardless of repo while luxd is one shared daemon serving one window, twelve z-spec entries accumulated on the menu across six live sessions. z-spec now implements [`tool-enable-disable.md`](https://github.com/punt-labs/punt-kit/blob/main/standards/tool-enable-disable.md): `enable` deposits `.punt-labs/z-spec/CLAUDE.md`, writes the committed `.punt-labs/z-spec/enabled` marker, and adds the bare `@.punt-labs/z-spec/CLAUDE.md` import to the host `CLAUDE.md` exactly once; `disable` removes the import line and the marker and leaves the subtree dormant (§2.9 --- no vendored content is erased). Both verbs are reachable from the CLI and as `/z-spec:enable` / `/z-spec:disable`, both route through one `RepoEnablement.apply`, and both are registered in the command registry so the surface-parity test covers them. Host-file mutation takes the mandated exclusive sibling lock (§2.4) around both the read and the write, so there is no lost-update race. **The gate is the MCP server and only the MCP server** --- menu registration lives in the lifespan and the sole hook matches MCP tool calls, so both fall out of it; in an unmarked repo every MCP tool declines with a message naming the enable command, except `enablement` itself, because the door cannot be behind the lock it opens. The `z-spec` CLI is deliberately **not** gated: a shell invocation is deliberate by definition, so `check`/`test`/`animate` keep working anywhere. There is no `y`/`n` toggle and no auto-enable --- the marker exists because a human ran `enable` and committed it.

### Fixed

- **The spec picker surfaced scratch files and labelled tabs with truncated paths** --- `PickerCommand._discover` globbed every `.tex` under the working directory, so a repo containing a `.tmp/pytest-of-*/` tree offered its fixtures as Z specs beside the real ones, and each tab was labelled with a raw path clipped to fit. Discovery now skips dot-directories (`.tmp`, `.venv`, `.git`, `.pytest_cache`) and `build_spec_picker` labels each tab with the file's stem, which reads cleanly in a narrow strip and cannot raise the way a `relative_to(cwd)` label does for an absolute root the process was not launched from. Verified against a live luxd: 18 tabs, exactly the 8 specs in `examples/` and the 10 in `tutorials/intro/`, with none of the five scratch `.tex` files present.

- **CI actually runs the quality gates** --- until now `.github/workflows/` held only `docs.yml` (markdownlint), `release.yml`, and `biff-notify.yml`, so a green pull request attested to the markdown and nothing else: no tests, no type checks, no lint, no ratchets ran on any PR. New `lint.yml` runs ruff check/format, mypy, pyright, shellcheck, `make check-dev-commands`, and all three ratchets with merge-base scoping (`--base-ref <merge-base> --require-base`, with a `--allow-no-improvement` waiver for mechanical `release/*` version bumps and a post-merge `HEAD~1` tripwire on main). New `test.yml` runs three jobs: `unit` (pytest), `e2e` (builds and installs the wheel, then drives the installed artifact), and `specs` (builds `fuzz` from source, downloads `probcli`, and type-checks + model-checks every `examples/*.tex`). `uv.lock` is now tracked so CI can `uv sync --frozen` reproducibly.
- **Tier 5 end-to-end tests against the installed artifact** --- `tests/e2e/` drives the `z-spec` binary that `make install` put on `PATH`, not the working tree: the CLI as a subprocess (`--version`, every registry verb present in `--help`, a missing spec file failing without a traceback, `check` reaching the real `fuzz`, `doctor` running from an unrelated directory) and the MCP server over stdio (JSON-RPC `initialize` handshake plus `tools/list` asserted against the capability registry). These catch the packaging faults no in-process test can see — an entry point that does not resolve, a data file absent from the wheel, a `__file__`-relative path that only works in a checkout. Gated behind a new `e2e` pytest marker, deselected by default, run with `make test-e2e`.
- **`make install`, `make uat`, `make test-e2e`, `make metrics`, `make coverage`** --- there was previously no target that built and installed the wheel, so there was no supported way to run the artifact a user gets. `make install` builds, installs, and prints that a running MCP server still holds the old code until reconnected. `make report` is now full diagnostics per PY-BS-3 (OO, coupling, suppressions, both type checkers, formatting, lint, tests, fuzz); the previous probcli-report target is renamed `spec-reports`.
- **`docs/WORKFLOW.md`, `TESTING.md`, `docs/testing/manual-tests.md`** --- the three-loop development process (backlog → PR → mission) with pseudocode and entry/exit Z schemas at each level, adapted from lux and vox; a five-tier testing pyramid whose top tier is user acceptance testing against the installed artifact **before the PR opens**; and the canonical acceptance flight of action × context × expected outcome. `CLAUDE.md` is rewritten on the lux/vox template with these `@`-imported, plus an architecture and module map, the OO ratchet policy, and the delegation table. Written because a feature was declared verified from unit tests and Hub introspection, taken to PR, and only then found unusable when a human ran it.

- **Interactive lux right-click menu (Tutorial + Browse) and the `pick` tool/verb** --- the z-spec MCP server is now a normal-path lux client: the FastMCP lifespan owns one persistent `LuxRestClient` under a per-session **app** identity (name `z-spec / <repo> / #<pid>`, 30s lease) plus a `LuxHubClient` listen leg, and registers two right-click menu entries per session. The identity **name** is ASCII-only and one cached `ClientIdentity` object is handed to both legs: luxd hashes the `X-Lux-Client-Name` header into the ConnectionId that links the REST menu registration to the `/ws` listen leg, and a non-ASCII separator (e.g. `·`, U+00B7) encodes to different bytes on the WebSocket handshake vs the REST call, so the two legs hash to different ids and luxd refuses the registration. The human menu **labels** keep the `·` — they ride `register_callback`'s JSON body, not a header. Registration is bounded-retry best-effort (idempotent by callback id): the `on_connect` happy path succeeds on the first attempt, and a transient refusal is retried a few times before being logged and dropped, never crashing the receive leg. **Tutorial** (`z-spec Tutorial · <repo> · #<pid>`) opens the shipped `tutorials/intro` collection; **Browse** (`z-spec Browse · <repo> · #<pid>`) renders the `.tex` Z specs discovered in the session's working directory. Both labels carry the tool axis *and* the session axis, so two z-spec sessions never cross wires. A click renders through the same command a menu tool would run — no duplicated render logic — and each callback raises a placeholder then renders the full scene into **one** Hub scene id (`raise-id == render-id`), so the placeholder is replaced rather than stranded. Menu registration re-runs from `on_connect` after every handshake (register-fresh), so a luxd restart heals the menu without restarting the server. The listener is strictly best-effort relative to the tool surface: a down luxd at startup is non-fatal (the check/test/animate tools keep working) and every blocking REST call — `register_callback`, the placeholder push, and `command.run` — is off-loaded via `asyncio.to_thread`, so a render never starves the event loop. The Browse content is exposed on both surfaces per CLI parity: a new `pick` MCP tool and `z-spec pick [DIRECTORY]` CLI verb discover a directory's Z specs (skipping `templates/preamble.tex` and LaTeX includes with no Z blocks) and render them in a tabbed picker. `show_z_spec`, `browse`, and `pick` now render through the one server-owned app-identity client instead of a throwaway cli-identity client per call.

### Changed

- **`punt-lux` pinned to `>=0.22.1,<0.23`** --- released 0.22.1 restores the `for_identity` / `listener` / `register_callback` API the persistent-listener menu path needs (removed for the 0.21 REST-only client). `render` and `RenderRequest` are unchanged from 0.21, so the shipped rendering half is untouched by the bump.

## [0.17.1] - 2026-07-27

### Fixed

- **Lux rendering now publishes to the punt_lux 0.21 Hub** --- z-spec pinned `punt-lux>=0.9.0` (resolving to 0.9.x) while the running lux daemon is 0.21.0. Across those versions lux completed a WebSocket-to-HTTP swap: `punt_lux.client.LuxClient`/`DisplayClient` are no longer package-root exports (the display socket is Hub-internal, one client — luxd), and the Hub is the scene authority. z-spec's `LuxClient(...).show(...)`-over-socket path therefore reached nothing the Hub tracked, so `show_z_spec` and `browse` returned `ok:true` but never landed a scene. The dependency is bumped to `punt-lux>=0.21,<0.22` and `LuxDisplay` now publishes each scene through `LuxRestClient.render(RenderRequest(...))` (REST `PUT /scenes/{id}`), the same path `lux show beads` uses; both tools now land Hub-tracked scenes (`GET /scenes` shows `z-spec` and `z-spec-browser` owned by the REST tier). The 0.21 element API changes are absorbed: `CollapsingHeaderElement.default_open` → `open`, `TabBarElement.tabs` takes `Tab(tab_id, label, children)` objects instead of dicts, `TableElement.flags` takes a `TableFlags` value object instead of `list[str]`. The tutorial browser and spec picker move off the removed paged `GroupElement` (`layout="paged"`/`pages`/`page_source`) to a `TabBarElement` with one tab per lesson/spec; `build_z_spec_scene` gains an `id_prefix` so the browser's embedded per-lesson scenes keep element ids unique, which the 0.21 Hub requires (it rejects a tree with a repeated element id). The dead menu/event machinery in `server.py` (the persistent `LuxClient`, `declare_menu_item`/`on_event` menu callbacks, and the eager-connect lifespan) is removed — that model does not exist for a 0.21 REST caller; a right-click menu affordance is deferred.

## [0.17.0] - 2026-07-26

### Added

- **Dev/prod plugin namespace isolation** --- the working tree is now the dev plugin (`plugin.json` name `z-spec-dev`, MCP server running the working tree via `uv run --directory ${CLAUDE_PLUGIN_ROOT} z-spec mcp`), so `claude --plugin-dir .` loads `z-spec-dev` alongside the installed marketplace `z-spec` for local pre-release testing. Every prod command `commands/<c>.md` gains a generated `commands/<c>-dev.md` twin (19 total) that rewrites MCP tool references to `mcp__plugin_z-spec-dev_zspec__*` and `/z-spec:<cmd>` self-references to `/z-spec-dev:<cmd>-dev`. The twins are produced and verified by `tools/gen_dev_commands.py` via `make gen-dev-commands` and `make check-dev-commands` (the latter wired into `make check`, failing on any drift). The `z-spec-dev` namespace carries a hyphen, matching the `hooks/hooks.json` matcher `mcp__(plugin_z-spec(-dev)?_)?zspec__.*`. README documents the exact `claude --plugin-dir .` local-test procedure.

- **OO gate suite (`make check-oo` / `check-coupling` / `check-suppressions`)** --- the canonical ratchet tools from vox are vendored under `tools/` (`oo_score.py` + `oo_ratchet/`, `oo_coupling.py` + `coupling/`, `suppression_ratchet.py` + `suppression/`), all stdlib-only and taking the source path as an argument. Each gate ratchets the current tree against a committed baseline (`.oo-baseline.json`, `.oo-coupling-baseline.json`, `.suppression-baseline.json`, with `.oo-audit.jsonl` / `.oo-coupling-audit.jsonl` / `.suppression-audit.jsonl` audit trails) and fails only on a green-to-red regression, never on the standing baseline. `check-oo`, `check-coupling`, and `check-suppressions` are wired into `make check`; `update-oo` / `update-coupling` / `update-suppressions` re-snapshot the baselines, and `make report` now prints the per-file OO breakdown.
- **`types/` package** --- the former `types.py` god-module (22 classes across six domains) is split into a `punt_zspec.types` package with one submodule per domain (`spec`, `fuzz`, `prob`, `partition`, `audit`, `tutorial`, `reports`). `__init__` re-exports every public name via `__all__`, so `from punt_zspec.types import X` is unchanged for all callers. Pure internal reorganization: no runtime behavior changes.
- **Shared `commands/` orchestration layer** --- the CLI and MCP server are now thin clients over one engine. Each capability (`check`, `report`, `doctor`, `test`, `animate`, `model-check`) is a single command class with injected collaborators, returning a typed `CommandResult`; both surfaces construct the command and render or return its result, eliminating the duplicated resolve/run/persist/serialize logic that previously lived twice.
- **CLI parity verbs `partition`, `audit`, `show`, `browse`** --- the four capabilities that were previously MCP-only are now CLI verbs too. `z-spec partition <spec>` and `z-spec audit <spec>` validate and persist an authored report read from stdin by default, or from `--report FILE` (`--report -` is stdin); an unreadable `--report` file exits 1 with `error: cannot read report: <exc>` and no traceback. `z-spec show <spec>` renders a spec and its reports in lux, and `z-spec browse <manifest>` opens a collection. Every deterministic capability is now reachable from both the CLI and the MCP server, enforced by a registry-driven parity test.
- **MCP `doctor` tool** --- toolchain health (`fuzz`/`probcli` resolution and version) is now available on the MCP surface as well as the `z-spec doctor` CLI verb.
- **`--no-plugin` CLI-only install** --- `install.sh` now accepts a `--no-plugin` flag and a `ZSPEC_NO_PLUGIN=1` environment variable (over the pipe as `sh -s -- --no-plugin` or `ZSPEC_NO_PLUGIN=1 sh`) to install the `z-spec` CLI while skipping the Claude Code marketplace-register and plugin-install steps, conforming to punt-kit [`install-cli-only.md`](https://github.com/punt-labs/punt-kit/blob/main/standards/install-cli-only.md). Unknown flags exit 2 with usage; only `ZSPEC_NO_PLUGIN=1` is honored.
- **PostToolUse `suppress-output` hook** --- now that the slash commands call the `zspec` MCP tools, each tool result would otherwise dump raw JSON into the conversation. `hooks/suppress-output.sh` (wired via `hooks/hooks.json`, referenced from `plugin.json`, matcher `mcp__(plugin_z-spec(-dev)?_)?zspec__.*`) renders a concise panel line instead --- `check` shows OK/FAIL plus the error count; `test`/`animate`/`model_check`/`get_report` show pass/total checks with states and transitions; `doctor` shows health plus `fuzz`/`probcli` presence; `save_partition_report`/`save_audit_report` show the saved path; `show_z_spec`/`browse` show what was displayed --- while the full JSON stays available to the model via `additionalContext`. Every one of the 10 tools has a handler.

### Changed

- **`release-plugin.sh` now swaps the MCP server command to the installed binary** --- the prod manifest previously shipped `command: "uv"` with `uv run --directory ...` args, which fails for marketplace users who have no uv project (violating the MCP Server Declaration standard). `release-plugin.sh` now rewrites the command to the installed `z-spec` binary with args `["mcp"]` alongside the name swap and `-dev` twin removal; `restore-dev-plugin.sh` restores all three from the release-prep commit's parent. Both scripts abort on an unclean working tree.
- **Deterministic slash commands are now thin clients over the `zspec` MCP tools** --- `/z-spec:check`, `/z-spec:test`, `/z-spec:doctor`, `/z-spec:partition`, and `/z-spec:audit` no longer shell raw `fuzz`/`probcli` or hand-parse their stdout, and no longer hand-roll ~170-line lux dashboards. `check` calls the `check` tool; `test` calls `test` + `show_z_spec`; `doctor` calls the `doctor` tool for the required `fuzz`/`probcli`/version trio (keeping Bash only for the optional fuzz.sty/Tcl/Lean checks); `partition` and `audit` author their `--json` report, hand it to `save_partition_report`/`save_audit_report` to validate and persist `<stem>.partition.json`/`<stem>.audit.json`, then call `show_z_spec` to render. This makes the Partition and Audit tabs reachable (previously nothing wrote those files) and removes the divergent second parser and renderer. The generative value-add is preserved verbatim: `check`'s six animation-readiness advisories and `test`'s counter-example explanation. The inline `fuzz.sty` fetch is dropped from `check`/`test` (`fuzz -t` does not need it); provisioning moves to `/z-spec:setup`. `b-check`/`b-animate` are unchanged — no `zspec` tool wraps B machines yet.
- **`z-spec check` now persists `<stem>.fuzz.json`** --- the CLI `check` command now writes its fuzz result alongside the spec, matching the MCP `check` tool. Both surfaces persist via one code path; every other command's stdout, stderr, exit code, and MCP JSON output is unchanged.
- **`show_z_spec` and `browse` MCP tools use the `{ok: ...}` convention** --- both tools previously returned `{"status": "displayed"|"error", ...}`; they now return `{"ok": true, ...}` on success and `{"ok": false, "error": ...}` on failure, matching every other tool. The error message strings are unchanged; only the discriminator key flips. The partition, audit, and report tool outputs are byte-for-byte unchanged.
- **Missing `claude`/`git` auto-skips the plugin step** --- `install.sh` previously aborted when the `claude` CLI or `git` was absent; both are now capability auto-skips that install the CLI and skip only the plugin. `curl` remains a hard prerequisite. The CLI-only success message is identical for the auto-skip and explicit-skip paths and prints no plugin-activation line.
- **Lux render lock now scopes to client acquisition/reset, not the full render** --- the MCP server's display lock is held only while acquiring or resetting the shared lux client, not for the duration of a scene render; menu callbacks already render unlocked. This is a deliberate narrowing for the single-user display; concurrent renders are no longer serialized end-to-end.

## [0.16.0] - 2026-05-10

## [0.15.0] - 2026-05-10

### Added

- **Proactive probcli animation hints** --- 7 patterns that cause silent probcli failures (unbounded `\finset`/`\pfun`, cross-product triples, bare-type quantifiers, missing operation bounds, underscored constructors, `\mu` in operations, `\t1` indentation) are now documented in `reference/probcli-guide.md` (all 7) and `reference/schema-patterns.md` (6 structural patterns), embedded in `/z-spec:code2model` generation prompts, and 6 are warned about by `/z-spec:check` after successful fuzz type-checking (`\t1` is caught by fuzz itself)
- **Animation hint test specs** --- `examples/animation-hints-good.tex` and `examples/animation-hints-bad.tex` demonstrate correct vs anti-pattern Z for probcli animation; good spec model-checks in 3s at setsize 2, bad spec explodes at setsize 4

### Changed

- **Makefile excludes `*-bad.tex` from test suite** --- intentionally broken specs are no longer model-checked by `make check`

### Fixed

- **Makefile `test-z-%` and `assert-%` now propagate probcli exit codes** --- previously, piping through `grep | head` swallowed non-zero exits, so counter-examples and assertion failures passed `make check` silently; now captures exit code before filtering output

## [0.14.1] - 2026-03-21

### Fixed

- **Lux menu apps now register at MCP server startup** --- "Z Notation Tutorial" and "Z Spec Browser" menu items previously only appeared after calling `show_z_spec` or `browse` tools; now register eagerly via FastMCP lifespan hook
- **Inline formatting rules in generation prompts** --- `code2model` and `elaborate` commands now include mandatory `\t1` ban, 80-char line limit, and `\quad~` indentation rules at the point of generation, preventing margin overflow and fuzz-incompatible indentation in produced specs

## [0.14.0] - 2026-03-14

## [0.13.0] - 2026-03-14

### Added

- **PyPI publishing** --- `release.yml` GitHub Actions workflow publishes `punt-z-spec` to PyPI on tag push via trusted publisher (build → TestPyPI → test-install → PyPI)
- **Full hybrid install.sh** --- installs uv, Python 3.13+, `punt-z-spec` CLI via `uv tool install`, registers marketplace, installs plugin, runs `z-spec doctor`; matches biff/quarry/vox install pattern

## [0.12.0] - 2026-03-14

## [0.11.0] - 2026-03-13

### Added

- **Tutorial browser** --- `browse` MCP tool loads all lessons from a manifest.toml and displays them in a paged lux view; combo-driven page switching is instant and client-side (no MCP round-trips); each page shows didactic annotations and spec tabs with section highlights auto-expanded
- **Collection manifest parser** --- `manifest.py` parses `manifest.toml` files into typed `Collection`/`Lesson` dataclasses with validation
- **`Lesson` and `Collection` types** --- frozen dataclasses in `types.py` for tutorial content with spec paths, annotations, and highlight lists

### Changed

- **Typed lux applet** --- `build_z_spec_scene` now returns a `TabBarElement` (from `punt-lux`) instead of a raw dict; all element construction uses typed dataclasses for construction-time validation and mypy/pyright coverage
- **`show_z_spec` MCP tool** --- now displays directly in lux via `LuxClient` (like vox's `show_vox`) instead of returning a scene dict; returns `{"status": "displayed"}` or `{"status": "error"}` with graceful degradation; loads all available reports (fuzz, ProB, partition, audit) and renders each as a tab
- **`check` MCP tool** --- now saves fuzz results as `<stem>.fuzz.json` alongside the .tex file
- **`punt-lux` promoted to required dependency** --- moved from optional `[lux]` extra to core dependencies

### Added

- **Fuzz tab** --- `show_z_spec` renders fuzz type-check results (pass/fail, error table with line/column/message) when a `.fuzz.json` report exists
- **Partition tab** --- `show_z_spec` renders TTF partition analysis (per-operation tables with class, branch, status, inputs, pre/post state) when a `.partition.json` report exists; summary metrics show accepted/rejected/pruned counts
- **Audit tab** --- `show_z_spec` renders test coverage audit (coverage percentage, per-category breakdown, covered constraints, uncovered constraints with suggestions) when a `.audit.json` report exists
- **`save_partition_report` MCP tool** --- validates and saves LLM-generated partition reports as `<stem>.partition.json`; called by `/z-spec:partition` skill
- **`save_audit_report` MCP tool** --- validates and saves LLM-generated audit reports as `<stem>.audit.json`; called by `/z-spec:audit` skill
- **Typed partition/audit models** --- `PartitionReport`, `OperationPartitions`, `Partition`, `AuditReport`, `AuditConstraint`, `AuditSuggestion` dataclasses in `types.py` with `to_dict()`/`from_dict()` roundtrip support

### Added

- **Python package (`punt-z-spec`)** --- CLI + MCP server hybrid following the vox pattern; deterministic L1 tools replace raw bash in skill prompts
- **CLI (`z-spec`)** --- typer CLI with `check`, `test`, `animate`, `model-check`, `report`, `doctor`, and `mcp` commands
- **MCP server (`zspec`)** --- FastMCP server with 6 tools: `check`, `test`, `animate`, `model_check`, `show_z_spec`, `get_report`; registered in plugin.json as `mcpServers.zspec`
- **LaTeX Z parser** --- extracts schemas, types, constants, and invariants from .tex files; LaTeX-to-Unicode conversion (35+ symbols); schema box rendering with open-right Unicode box-drawing
- **ProB report convention** --- `<stem>.report.json` files alongside .tex specs with ISO 8601 timestamps, all five check results, per-operation coverage, and counter-example traces; staleness detection
- **Binary wrappers** --- structured wrappers for `fuzz -t` and `probcli` with binary resolution via `$FUZZ`/`$PROBCLI` env vars, PATH, and conventional install locations
- **Lux applet** --- persistent `z-spec` frame with tabs: Spec (structure with collapsing headers), ProB (metrics/checks/coverage), Counter-Example (trace table with violation); pure scene builder with no lux dependency — callers push scenes via MCP
- **Python quality gates** --- ruff, mypy, pyright, pytest with 46 tests; added `lint-py`, `test-py`, and `report` Makefile targets

## [0.9.0] - 2026-03-09

### Added

- **Spec tab for Lux displays** --- `/z-spec:test` and `/z-spec:partition` now include a "Spec" tab that renders the Z specification as Unicode math with box-drawing schema boxes, collapsible by section; LaTeX Z commands are translated to BMP-safe Unicode symbols (ℕ, ℤ, ℙ, ∈, ⊆, ⇒, ∅, Δ, etc.)

## [0.8.0] - 2026-03-09

### Added

- **Lux visual dashboard for `/z-spec:test`** --- renders model check results (states, transitions, coverage, pass/fail) as an interactive lux dashboard when lux is available; degrades gracefully to text-only
- **Counter-example trace visualizer** --- when model checking finds a violation, displays the trace as a step-by-step table in a second lux tab with state values and violated invariant
- **Lux partition table for `/z-spec:partition`** --- renders test partition matrix as an interactive lux table with search and status filters when lux is available

## [0.2.0] - 2026-03-01

### Added

- **B-Method support** --- four new commands for B Abstract Machine Notation
  - `/z-spec:b-create` --- create B machines from descriptions or translate Z specs to B
  - `/z-spec:b-check` --- type-check B machines (`.mch`, `.ref`, `.imp`) with probcli
  - `/z-spec:b-animate` --- animate and model-check B machines with probcli
  - `/z-spec:b-refine` --- create or verify B refinement machines
- B notation reference (`reference/b-notation.md`) --- MACHINE/SETS/VARIABLES/INVARIANT/OPERATIONS syntax, substitution language, types, and probcli commands
- B machine patterns (`reference/b-machine-patterns.md`) --- Counter, Registry, Queue, State Machine, and Refinement patterns with complete Z-to-B translation table
- PRDs for all four B commands (`docs/prd/b-create.md`, `b-check.md`, `b-animate.md`, `b-refine.md`)

### Fixed

- Lean 4 product type notation: `X x Y` → `X × Y` (Unicode) in prove command, lean4-patterns reference, and z-prove PRD
- Lean 4 existential quantifier: `exists` → `∃` in type positions (lean4-patterns, z-prove PRD)
- Missing `[[lean_lib]]` section in lakefile.toml templates (prove command) --- `lake build` requires it to know what to compile
- Mathlib dependency: `version = "git#master"` → `rev = "main"` in lakefile.toml templates (Mathlib4 uses `main` branch, and `rev` is the correct TOML field)
- `omega` tactic import: noted as built-in since Lean 4.3.0, not a Mathlib dependency (lean4-patterns reference)
- Undocumented `--impl` flag: added to refine command argument list (was only referenced in error message)
- Missing `--strip` flag: added to contracts command per PRD scope (generates no-op stubs for production builds)
- Oracle PRD protocol: aligned with command's simpler flat JSON format (NDJSON, state unchanged on precondition violation)
