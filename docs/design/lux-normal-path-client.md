# ADR: z-spec as a normal-path lux client

Status: Proposed (design converged with the lux agent, biff, 2026-08-01)
Date: 2026-08-01
Author: edt
Closes: z-spec-2xt, z-spec-i6s (one implementation closes both)
Supersedes: the dead 0.13 socket menu path removed in 0.17.1
(`declare_menu_item` + `on_event` + background listener +
`_on_tutorial_click` / `_on_spec_browser_click`)

## 1. Context

z-spec is its own FastMCP server (`src/punt_zspec/server.py`), not a lux MCP
session. It draws two things from the lux Hub:

- **Rendering** (shipped, z-spec 0.17.1). `LuxDisplay.show` in
  `src/punt_zspec/display.py:58` builds a `RenderRequest` and PUTs it via
  `LuxRestClient.connect().render` (`display.py:56`, `display.py:70`). This is
  push-only: the scene is attributed to the git repo through the connect-derived
  **cli identity**. Two MCP tools use it — `show_z_spec` (`server.py:159`) and
  `browse` (`server.py:216`). Each **constructs a throwaway `LuxDisplay()` per
  call**: `ShowCommand(build=build, display=LuxDisplay())` and
  `BrowseCommand(build=build, display=LuxDisplay())`. There is no long-lived
  client and no connection a click could arrive on.

- **Interactive menu entries** (this ADR). z-spec wants two right-click menu
  affordances — open the shipped Tutorial, and browse the specs discovered in
  the session's working directory. Under the 0.13 socket model these existed as
  `_on_tutorial_click` / `_on_spec_browser_click`; 0.21 removed the socket
  `LuxClient`, so they have had no channel since. 0.22.1 restores the mechanism:
  a persistent listener leg plus `register_callback`.

This ADR covers the **interactive half and the server-client lifecycle**. It
does not re-derive the architecture — that is converged with the lux agent
(claude:tty4). It grounds each decision in the reference code and z-spec's
actual `server.py`, and surfaces the implementation risks.

The reference implementation is vox's music player — repo `punt-labs/vox`,
package `src/punt_vox/voxd/music_player/` (locally `../vox/...` in the
sibling-repo workspace). Read it in the order the lux agent gave (claude:tty4,
2026-08-01):

1. `lux_clients.py` — the one long-lived `LuxRestClient` and the `on_connect`
   pattern, built from one explicit app identity.
2. `lux_menu.py` — the guarded `register_callback` / menu registration.
3. `ports.py` and `hub_ports.py` — the Protocols around them: `ports.py` defines
   `LuxRenderer` (the `render` method, `ports.py:46-56`); `hub_ports.py` defines
   `HubListener` (subscribe/listen/stop), `MenuClient` (`register_callback`), and
   their union `LuxClient` (`hub_ports.py:31-59`).

`lux_subscription.py` (the receive leg: `on_connect`, `on_callback`, the guarded
`run` loop) and `composition.py` (the wiring) show the two legs assembled. The
library contract is repo `punt-labs/lux`, `docs/library.md` (locally
`../lux/docs/library.md`), section **"Listening: a persistent hub client"**
(lines 39-95).

## 2. Decision

### 2.1 Per-session app identity, not the derived cli identity

> **Superseded (2026-08-06).** The identity is now `kind="applet"`,
> `name="z-spec #<pid>"`, `repo=<absolute project root>`, `lease_ttl=60`.
> What changed is whose job disambiguation is. This section folded the repo
> into the *name* because lux had no client grouping; lux 0.23's Clients menu
> supplies one — one submenu per live client, labelled from `ClientIdentity`,
> numbered on collision, never merged. `ClientIdentity.menu_label` returns
> `self._repo_name or self.name`, so **once `repo` is set the name is never
> displayed at all**: the submenu reads the project-root basename and answers
> "which repo", nothing else. The pid stays in the name — not for display, but
> because `ConnectionId` is a hash of `(kind, name, repo, agent)`, and two
> same-repo sessions sharing all four collapse onto one connection where
> `attach_listener` evicts the first session's callbacks. lux calls it "a
> distinctness token and not something to read aloud". `lease_ttl` is no longer
> declared at all: absent is luxd's documented "use my kind's length", and an
> applet's length is already the one written for a client that lives and dies
> with a session — naming a number would copy a constant lux owns and pin us to
> today's value of it. Resolved rather than assumed:
> `SessionLease.for_kind("applet", now).ttl_seconds` is 60.0 with `lease_ttl`
> None on the wire. The old 30 was copied from voxd, a machine-wide daemon, and
> never had a z-spec reason.

The z-spec MCP server declares an explicit **app** identity:

```text
LuxRestClient.for_identity(ClientIdentity(
    kind="app",
    name="z-spec · <repo-basename> · #<pid>",
    lease_ttl=30,
))
```

Verified present in **released** punt_lux 0.22.1 (the version vox ships on):
`LuxRestClient.for_identity`, `listener`, and `register_callback` are all present,
and `ClientIdentity` carries `(kind, name, repo, agent, lease_ttl)`. The menu,
identity, and render mechanics all work at the pinned version. (`raise_frame` is
the one exception — next-release only; see 2.4.)

- The **name is the menu disambiguator luxd shows** (voxd names itself `voxd`,
  `lux_clients.py:28`). z-spec folds `repo-basename` and `#pid` into the name so
  two sessions never collide.
- `lease_ttl=30` (seconds): when a session dies, luxd sweeps its menu entries
  ~30s after the last heartbeat. Matches voxd (`_LEASE_TTL_SECONDS = 30.0`,
  `lux_clients.py:29`).
- `pid` from `os.getpid()`. `repo-basename` from the git repo root, falling back
  to the working-directory basename.

The rendering path (`display.py`) keeps using the same identity once it moves to
the server-owned client (see 2.3). Attribution shifts from cli-derived (repo) to
app (repo + pid) — a strict improvement for the multi-session case, invisible for
the single-session case.

### 2.2 Two menu entries per session: Tutorial and Browse

> **Superseded (2026-08-06).** The labels are now exactly `Tutorial` and
> `Browse`. The composite forms below repeated the client and session inside a
> submenu that already states both — noise beside `voxd ▸ Music` and every
> other client's `Beads`. A leaf is named for its command alone.

Each session registers **both** callbacks on its one app client:

| Callback id | Label | Content source |
|-------------|-------|----------------|
| `z-spec-tutorial` | `z-spec Tutorial · <repo> · #<pid>` | shipped `plugin/tutorials/intro/manifest.toml` (uniform) |
| `z-spec-browse` | `z-spec Browse · <repo> · #<pid>` | `.tex` specs discovered in the session's working directory (repo-specific) |

**Two-axis labeling is mandatory and operator-confirmed.** The label carries the
**tool axis** (Tutorial vs Browse) *and* the **session axis** (repo + pid). The
Tutorial content is uniform (the shipped manifest), but the Browse content is
**repo-specific** — each Browse callback renders the `.tex` models that session
discovered in *its own* working directory. Without both axes on the label, a
human with two z-spec sessions open clicks "Browse" and gets the wrong repo's
specs. The tool axis alone is insufficient; the session axis alone is
insufficient.

### 2.3 Persistent listener lifecycle; register only from `on_connect`

The FastMCP server owns **one long-lived `LuxRestClient`** with a listener leg,
replacing the per-call throwaway `LuxDisplay()`. Registration happens **only from
`on_connect`**:

- The Hub **refuses** `register_callback` from a connection that holds no
  listener leg (`library.md:82-85`). The handshake that `on_connect` fires after
  is what gives the connection that leg.
- `on_connect` **re-runs after every handshake** — first connect and every
  internal reconnect (`library.md:50-52`, voxd `lux_subscription.py:191-208`).
  A luxd restart or a >30s outage lapses the lease and luxd sweeps the entries;
  the reconnect fires `on_connect` and re-registers them ("register-fresh").
- An **outer register-then-listen** sequence runs once and loses the entries on
  the first reconnect — the menu stays gone until the MCP server restarts.

`on_connect` registers **both** callbacks (2.2). This mirrors voxd's single-entry
`on_connect` (`lux_subscription.py:204`), extended to two entries.

### 2.4 Raise-first click contract (<100-200ms visible response)

> **Superseded (2026-08-06).** The pin is now `>=0.23,<0.24`, `raise_frame`
> exists, and `_raise_scene`'s placeholder-then-full-scene sequence is gone —
> a click raises the frame in one call. The guard below did its job for the
> whole `<0.23` pin lifetime and is now retired rather than merely unused.
>
> One prediction here was wrong and is worth recording. This section called the
> collapse "a one-line change to the method body; nothing else moves". It was
> not: the subscription raised through `Display.show`, and `Display` has no
> raise, so a REST port had to be introduced. Rather than take
> `ZSpecSubscription` to six constructor parameters, the click path moved into
> its own class — which took `subscription.py` from 278 lines and 3 classes to
> 166 and 1. The lesson is the general one about swap points: "one line in the
> body" holds only if the new call needs nothing the old path did not already
> have.

A click must produce a visible response in **100-200ms** (operator-ruled,
lux-side absolute). The Browse scene renders 153 elements; a full re-render on
every click misses that budget on the cold path.

**`raise_frame` does NOT exist in released punt_lux 0.22.1.** Verified against
vox's released-0.22.1 install: `hasattr(LuxRestClient, "raise_frame")` is
`False`. It ships in the **next release (0.23)**. A z-spec build pinned
`>=0.22.1,<0.23` that calls `LuxRestClient.raise_frame` raises `AttributeError`.
(An earlier draft reported it present; that check ran against the `../lux` repo's
venv, which is an unreleased branch build carrying a stale `0.22.1` version
string — a false positive. See 2.5.)

**The click handler routes through one internal method, `_raise_scene(scene_id)`.**
Every click calls it, and it is the only place the raise behavior lives. This is
a **hard guard against an unreleased API**, not merely a latency optimization —
the callback never names `raise_frame`, so the unreleased method can never leak
into a shipped z-spec:

- **For the entire `>=0.22.1,<0.23` pin lifetime** `_raise_scene` does the
  minimal-placeholder-then-full-scene sequence for **every** click, cold and warm
  alike: push a minimal frame instantly (title + "loading" text) under
  `scene_id`, then render the full scene into the same `scene_id` behind it.
  Calling `raise_frame` at this pin would `AttributeError`, so the placeholder
  path is the **shipped behavior**, not a stopgap. The lux agent measured this
  raise-first approach at **63ms median** — inside the 100-200ms budget.
- **Only when the pin bumps to the 0.23 release that carries `raise_frame`** does
  `_raise_scene` collapse to a single `LuxRestClient.raise_frame(scene_id)` call.
  That is a one-line change to the method body, gated on the release existing;
  nothing else moves.

Isolating the behavior in `_raise_scene` is the decision: the callback always
calls `_raise_scene(scene_id)`, unaware of which implementation is inside. The
placeholder-path latency (the 63ms figure re-measured in z-spec's own tool
surface) is the live-verify item that matters for the whole pin lifetime (6.2) —
`raise_frame` cannot be verified until 0.23 ships.

### 2.5 Cutover: pin punt-lux `>=0.21,<0.22` → `>=0.22.1,<0.23`

> **Superseded (2026-08-06).** The pin is now `punt-lux>=0.23,<0.24`. 0.23
> shipped `raise_frame` (2.4), the `applet` client kind and `menu_label` (2.1),
> and `header_value.py`, which percent-encodes non-ASCII on the wire — so the
> ASCII-only identity-name rule this document was written under no longer
> applies. The "verify against a released install, never `../lux`" warning
> below stands and earned itself twice more: a consumer's pin can be a release
> behind the lux tree, so "what the source does" and "what we can construct"
> are different questions. Ask which release a behavior landed in.

`pyproject.toml:26` currently pins `punt-lux>=0.21,<0.22`. Bump to
`punt-lux>=0.22.1,<0.23`. Everything the interactive half needs is present in
**released 0.22.1** (verified against vox's released-0.22.1 install):
`for_identity`, `listener`, `register_callback`, `render`. vox already ships on
released 0.22.1. `raise_frame` is the **only** exception — next-release (0.23),
absent at this pin, and reached solely through `_raise_scene` (2.4) so its
absence never surfaces. No lux-side change blocks the work; the `on_connect`
pattern is forward-compatible with lux's listener-leg enforcement.

**Verify punt-lux APIs against a released install, never against the `../lux`
repo venv.** That venv is a branch build (`feat/session-mcp-serve`, installed by
lux's `make restart`) whose version string was never bumped past `0.22.1`, so it
reports `0.22.1` while carrying unreleased methods. Checking `raise_frame` there
returned a false positive. Ground API claims in a released install (e.g. what vox
pins) or ask the lux agent.

## 3. Cardinality model

```text
N Claude Code sessions
  → N z-spec MCP server processes  (one per session, distinct pid)
    → N app clients                (kind=app, name = z-spec · repo · #pid)
      → 2N menu entries            (Tutorial + Browse per client)
```

- Same-repo sessions are **still distinct clients** — the pid in the identity
  name separates them. This is the whole reason for app identity over cli
  identity (4.1).
- `lease_ttl=30`: a dead session's 2 entries are swept ~30s after its last
  heartbeat.
- **Idle sessions keep their entries.** z-spec's tool surface is idle for long
  stretches — unlike voxd, it pushes no periodic renders. The lease does not lapse
  anyway: the held-open listen leg **renews the lease on every WebSocket contact**
  (`library.md:45`), so the persistent listener's own keepalive traffic keeps a
  quiet session's two entries alive. The 30s sweep fires only when the session is
  actually **dead** (the socket is gone), not merely quiet.
- Each Browse entry renders **that session's** working-directory specs, so the
  2N entries are not 2N views of one dataset — the N Browse entries are N
  different repos' specs. This is exactly why both label axes are required (2.2).

## 4. Rejected alternatives

### 4.1 cli identity (`LuxRestClient.connect()`) for the menu — WRONG

`connect()` derives identity from the git repo / working directory
(`library.md:17-19`). Two same-repo sessions would resolve to **one identity →
one connection**. Because the menu callback lives on that identity's lease, the
second session's `register_callback` would land on the same session key as the
first: lux succession has the later client **steal** the earlier client's menu
entry. N same-repo sessions would share a single pair of entries, and clicks
would route to whichever session most recently registered — the wrong repo's
specs on every collision. cli identity is correct for **push-only rendering**
(the scene is legitimately attributed to the repo, which is why 0.17.1's
render-only path uses it) but wrong the moment a session needs its **own** menu
entry. App identity with pid gives each session a distinct key.

### 4.2 `register_callback` outside `on_connect` — WRONG

An outer `register-then-listen` sequence (register the callbacks, then start the
listen loop) is wrong on two counts:

1. **The Hub refuses it.** `register_callback` from a connection with no listener
   leg is rejected (`library.md:82-85`). The registration must happen *after* the
   handshake that establishes the leg — which is exactly when `on_connect` fires.
2. **It runs once.** The listener reconnects internally across transient drops
   and after a luxd restart. `on_connect` re-runs on **every** handshake; an
   outer sequence runs only on the first. A >30s outage lapses the lease, luxd
   sweeps the entries, the internal reconnect restores the socket — but the outer
   sequence never re-registers, so the menu stays permanently gone until the MCP
   server process restarts. voxd's history records this exact bug class
   (`lux_subscription.py:120-130`: the registration "no longer lives here").

## 5. Server-client lifecycle (concrete)

### 5.1 Where the client is created and what owns the loop

FastMCP supports a `lifespan` async context manager (verified: `FastMCP.__init__`
accepts `lifespan`). The server runs on an asyncio event loop
(`FastMCP.run(transport="stdio")` → anyio/asyncio). The lifespan is where the
long-lived client and the listener task are born and reaped:

```text
@asynccontextmanager
async def lifespan(server):
    clients = ZSpecLuxClients()          # one app identity (2.1)
    subscription = ZSpecSubscription(     # owns on_connect / on_callback
        tutorial_manifest=<shipped path>,
        cwd=Path.cwd(),
        clients=clients,
    )
    task = asyncio.create_task(subscription.run())   # the listener loop
    try:
        yield
    finally:
        subscription.stop()
        task.cancel()
        await _drain(task)
```

- **What owns the listener loop:** an **asyncio task** created in the FastMCP
  lifespan, matching voxd. voxd's `LuxSubscription.run` (`lux_subscription.py:83`)
  is an async coroutine driven under an `asyncio.TaskGroup` in
  `MusicPlayerSubsystem.run` (`composition.py:65-105`), itself a fire-and-forget
  task the daemon spawns. z-spec's equivalent is one task in the MCP server's
  own event loop — no separate thread, no second event loop. The process lifetime
  equals the Claude Code session (stdio transport spawns one server per session),
  which is exactly the per-session identity boundary the cardinality model needs.
- **The render path joins the same client.** `display.py`'s `_default_connect`
  currently calls `LuxRestClient.connect()` (cli identity) fresh per render. It
  moves to the server-owned app-identity client so pushes and the listen stream
  share one identity — the precondition for a callback registered over REST to be
  delivered on the WebSocket (`library.md:42-46`, voxd `lux_clients.py:5-8`). The
  `LuxDisplay` protocol boundary (`display.py:21-30`) stays; only the injected
  connector changes from "connect fresh" to "return the server-owned client."

### 5.2 How `on_connect` registers both callbacks and how a click routes

`on_connect` (fired after every handshake) registers both entries best-effort:

Both `register_callback` and `render` are **synchronous blocking REST calls**, so
`on_connect` and `on_callback` must offload them to a worker thread with
`asyncio.to_thread` — never run them inline on the FastMCP event loop (see 5.3).

```text
async def on_connect():
    # register_callback is a blocking REST call — offload it (voxd lux_menu.py:54-57).
    await asyncio.to_thread(client.register_callback,
                            "z-spec-tutorial", f"z-spec Tutorial · {repo} · #{pid}")
    await asyncio.to_thread(client.register_callback,
                            "z-spec-browse",   f"z-spec Browse · {repo} · #{pid}")
```

mirroring voxd's guarded `LuxMenuRegistrar.register`, which offloads
`register_callback` via `asyncio.to_thread` (`lux_menu.py:54-57`) and swallows a
down/refusing luxd into a log line so a missing entry never crashes the receive
leg.

A click arrives as `on_callback(callback_id)` and routes through the one raise
method, then to **the same command objects the MCP tools call** — no duplicated
render logic. Every blocking step (the raise, the full render inside
`command.run`) is handed to a worker thread so the callback returns to the event
loop promptly.

**The raise `scene_id` and the command's render `frame_id` must be the same id,
and each menu callback owns a distinct one.** `LuxDisplay.show` uses `frame_id`
as the Hub `scene_id` (`display.py:64,67`), so a placeholder raised on one id
while the command renders into another leaves the placeholder on a scene the
command never fills — and the final scene never gets raised. Today
`BrowseCommand` hardcodes `frame_id="z-spec-browser"` (`browse.py:94`); the
implementation must make the command's target `frame_id` a **parameter** so each
caller renders into its own scene: the MCP `browse` tool keeps `"z-spec-browser"`,
the Tutorial callback renders **and** raises `"z-spec-tutorial"`, and the Browse
callback renders **and** raises `"z-spec-picker"`. Distinct ids also stop a
Tutorial click and an MCP `browse()` call from clobbering each other's scene.

```text
async def on_callback(callback_id):
    if callback_id == "z-spec-tutorial":
        await self._raise_scene("z-spec-tutorial")   # instant visible response (2.4)
        cmd = BrowseCommand(build=browser_build, display=self._display)
        # render into the SAME id the raise targets (parameterized frame_id):
        await asyncio.to_thread(cmd.run, tutorial_manifest, frame_id="z-spec-tutorial")
    elif callback_id == "z-spec-browse":
        await self._raise_scene("z-spec-picker")
        cmd = PickerCommand(build=picker_build, display=self._display)
        await asyncio.to_thread(cmd.run, cwd, frame_id="z-spec-picker")

async def _raise_scene(scene_id):
    # 0.22.1 pin: push a minimal placeholder frame under scene_id (63ms median),
    # off-loop — the placeholder push is itself a blocking render:
    #   await asyncio.to_thread(self._display.show, placeholder, frame_id=scene_id, ...)
    # raise_frame is 0.23-only — do NOT call it here; it AttributeErrors at 0.22.1.
    # 0.23 pin: this body becomes one to_thread call around client.raise_frame(scene_id).
    ...
```

- **Tutorial** re-uses the existing `BrowseCommand` (`commands/browse.py`) against
  the shipped `plugin/tutorials/intro/manifest.toml` — identical to what the `browse`
  MCP tool does (`server.py:208-217`), only with a fixed manifest path.
- **Browse** needs a **new `PickerCommand`** that discovers the working
  directory's `.tex` specs and renders `build_spec_picker`
  (`browser.py:131-157`). This builder exists today but **has no command wrapper
  and no MCP tool** — it is the one genuinely new piece of orchestration (see
  6.1). `PickerCommand` follows the `ShowCommand`/`BrowseCommand` pattern:
  injected builder + injected `Display`, returning a typed `CommandResult`.

The routing rule: **a click re-runs the same command the MCP tool would run.** The
callback is a second caller of the command, not a fork of it. Both the tool and
the callback construct the command with the server-owned `Display`. This keeps
the humble-object boundary — the command holds all logic; the tool and the
callback are thin entry points.

### 5.3 Thread boundary for the blocking REST render

`Display.show` → `LuxRestClient.render` (`display.py:70`) is a **synchronous,
blocking REST round-trip**. `on_callback` runs on the **same asyncio event loop**
`FastMCP.run(transport="stdio")` uses to serve `check` / `test` / `animate`.
Rendering the 153-element Browse scene **inline** in `on_callback` would block
that loop for the whole round-trip and starve every in-flight tool call.

**Decision (leader ruling): offload the blocking command run to a worker thread
at the callback boundary** — `await asyncio.to_thread(command.run, ...)` — and
likewise `await asyncio.to_thread(client.register_callback, ...)` in `on_connect`
and the placeholder push in `_raise_scene`. The callback awaits the thread and
yields the loop; it never runs REST inline. Rationale:

1. **It mirrors what FastMCP already does for the tools.** `show_z_spec` and
   `browse` are plain synchronous `def` tools (`server.py:133`, `server.py:196`);
   the MCP runtime offloads each to a worker thread, which is why the tools do not
   starve the loop today. The callback is a second entry point into the same
   blocking commands and must do the same offload the runtime does for the tools.
2. **z-spec's renders are click-triggered and user-paced**, so voxd's
   `SceneMailbox` latest-wins coalescing (the alternative, option a) is unneeded
   machinery — there is no stream of state changes to collapse. Note it as the
   upgrade path only if coalescing is ever required.
3. **It keeps the shipped synchronous `Display` / command layer untouched.**
   Making `Display`, `ShowCommand`, `BrowseCommand`, `PickerCommand`, and the MCP
   tools async (option c) would ripple through the shipped render path for no
   benefit. The thread boundary lives only at the callback, where the async
   listener meets the sync command.

voxd is the precedent: it never renders inline — `LuxScenePublisher._publish`
does `await asyncio.to_thread(client.render, request)`
(`lux_scene_publisher.py:78`) and `LuxMenuRegistrar` offloads `register_callback`
the same way (`lux_menu.py:54-57`).

## 6. Test / verify plan

### 6.1 Unit tests (Humble-Object, no live Hub)

Following PL-TT-5, the command and identity logic test without a Hub, subprocess,
or network — construct with a fake `Display` and assert on result fields.

- **Callback routing.** A fake subscription driven with a fake `Display` and a
  fake command factory. Assert `on_callback("z-spec-tutorial")` runs the Tutorial
  command against the shipped manifest; `on_callback("z-spec-browse")` runs the
  Picker command against the injected cwd; an unknown id is a no-op. Mirrors
  voxd's `on_callback` guard (`lux_subscription.py:181-189`).
- **Callback does not block the loop (5.3 regression guard).** A fake `Display`
  whose `show` blocks on a latch (an `asyncio.Event` the test controls). Assert
  `on_callback` returns to the event loop **before** the latch releases — proving
  the blocking render is off-loaded via `asyncio.to_thread`, not awaited inline.
  Without this test the loop-starvation regression is invisible.
- **`on_connect` registers both.** A fake registrar records `(callback_id, label)`
  pairs. Assert `on_connect` registers exactly `z-spec-tutorial` and
  `z-spec-browse` with two-axis labels, and that a raising `register` does not
  propagate (best-effort).
- **Identity / label construction.** Given a repo basename and a pid, assert the
  app-identity name is `z-spec · <repo> · #<pid>` and both labels carry both axes.
  Pure function, no I/O.
- **`PickerCommand`.** Point it at a temp dir with two `.tex` files and a fake
  `Display`; assert it discovers both, builds the picker, and calls
  `show(scene, frame_id="z-spec-picker", ...)`; assert a missing/empty dir yields
  a typed failure, and a down `Display` (raising `DisplayError`) yields
  `CommandFailure.display_failed` — the same error contract as `BrowseCommand`
  (`commands/browse.py:96-99`).

### 6.2 Live cross-repo click-verify (with the lux agent)

The lux agent (claude:tty4) drives the click; z-spec confirms the render.

1. Start luxd (0.22.1). Start two z-spec MCP sessions in **different repos**.
2. Confirm **4 menu entries** (2 per session), each label carrying repo + pid.
3. claude:tty4 clicks each Browse entry; z-spec confirms each renders **its own**
   repo's specs (the two-axis label guarantee).
4. Measure the click→visible latency of `_raise_scene` (2.4) against the <200ms
   budget — re-confirming the lux agent's 63ms median from z-spec's own tool
   surface. After the later pin bump, re-confirm the single `raise_frame` call
   holds the same budget.
5. Kill one session; confirm its 2 entries are swept within ~lease_ttl (30s).
6. Restart luxd under a live session; confirm `on_connect` re-registers both
   entries without restarting the MCP server (register-fresh).

## 7. Cutover and resolved confirms

### 7.1 Confirm (a): the voxd reference file

The reference is the **package** `../vox/src/punt_vox/voxd/music_player/`. Per
the lux agent, read in this order:

1. `lux_clients.py` — the one long-lived `LuxRestClient` and the live `on_connect`
   pattern: the explicit app identity (`kind=app`, `name=voxd`, `lease_ttl=30`,
   `lux_clients.py:28-29`, `43-46`) backing both legs; `for_identity` for REST
   (`:55`), `LuxHubClient.connect` for the listener (`:74-79`).
2. `lux_menu.py` — `LuxMenuRegistrar`: the failure-tolerant `register_callback`
   wrapper (`register`, `lux_menu.py:44-69`).
3. `ports.py` and `hub_ports.py` — the Protocols: `LuxRenderer.render`
   (`ports.py:46-56`); `HubListener` / `MenuClient.register_callback` / their
   union `LuxClient` (`hub_ports.py:31-59`).

`lux_subscription.py` shows the same `on_connect` / `on_callback` z-spec needs,
assembled with `composition.py`.

### 7.2 Confirm (b): render/RenderRequest API unchanged 0.21 → 0.22.1

**Yes, unchanged — the pin bump does not disturb the shipped rendering.** `render`
is a core API present in released 0.22.1. Verified against z-spec's 0.21.0 venv
and **vox's released-0.22.1 install** (not the `../lux` branch venv):

- `LuxRestClient.render(self, request: RenderRequest) -> SceneShown | OpError` —
  **identical** signature in both.
- `RenderRequest` pydantic fields **identical** in both: `scene_id` (required),
  `elements` (required), `title`, `layout`, `frame` (optional).

So `display.py`'s `RenderRequest(scene_id=..., elements=[...], title=...,
frame=FrameSpec(...))` construction and its `.render(request)` call are
untouched by the bump. The rendering half shipped in 0.17.1 keeps working as-is.

**Independent live evidence (lux agent, claude:tty4):** z-spec 0.17.1 — built
against the 0.21-pinned client — **already rendered live against a running
0.22.1 Hub** (`browse` → `z-spec-browser`, 153 elements; `show_z_spec` →
`z-spec`, 52 elements, both confirmed in `list_scenes`). The wire behavior, not
just the Python signature, is unchanged across the versions. The pin bump to
`>=0.22.1,<0.23` therefore carries zero rendering risk.

## 8. Bead outcome

This design's implementation **closes z-spec-2xt and z-spec-i6s together**:

- **z-spec-2xt** — the rendering half shipped in 0.17.1; the remaining actionable
  work is the Browse menu entry via `listener` + `register_callback` from
  `on_connect`. This ADR specifies it.
- **z-spec-i6s** — re-home the two menu items (open tutorial, browse specs) onto
  the Hub model. This ADR's two-entry design (Tutorial + Browse) is that re-home.

They are the same menu work; one implementation mission closes both.

## 9. Top implementation risks

1. **The placeholder-first path must hold the budget for the whole 0.22.1 pin
   lifetime.** `raise_frame` is next-release (0.23), so `_raise_scene` uses the
   minimal-placeholder-then-full sequence for **every** click across the entire
   `>=0.22.1,<0.23` pin — this is the shipped behavior, not a temporary stopgap
   (2.4). The lux agent measured 63ms median for the raise-first approach, but
   that was in luxd's own context; z-spec's listener runs in the FastMCP event
   loop, so implementation must re-measure end to end (6.2) against the 100-200ms
   budget with the 153-element Browse scene. If z-spec's number drifts above
   budget, the fix is inside `_raise_scene` alone. The one-line swap to
   `raise_frame` is gated on the 0.23 release existing — do not write that call at
   the 0.22.1 pin (it `AttributeError`s).

2. **The new `PickerCommand` orchestration.** The Browse callback's content is
   repo-specific and has **no existing command or MCP tool** — `build_spec_picker`
   is only a builder (`browser.py:131`). Implementation must add `PickerCommand`
   (discover cwd `.tex` → `build_spec_picker` → display) following the
   `ShowCommand`/`BrowseCommand` pattern, plus decide whether it is also exposed
   as an MCP tool or only reachable via the callback. This is the one net-new unit
   of logic; everything else re-uses shipped commands. Two impl traps:
   - **Tuple order differs.** `build_spec_picker` takes `list[tuple[Path,
     SpecModel]]` (`browser.py:132`), but `BrowseCommand`/`build_browser_scene`
     use `(SpecModel, Path)` (`commands/browse.py:27`). `PickerCommand` must pass
     `(path, model)`, not `(model, path)`.
   - **Discovery must filter non-spec `.tex`.** A cwd `**/*.tex` glob picks up
     `plugin/templates/preamble.tex` and any LaTeX include that is not a Z spec; these
     fail `parse_spec`. Discovery must skip the preamble/template files (and any
     `.tex` that does not parse) rather than error the whole picker.

3. **FastMCP lifespan owning a long-lived socket in a stdio server.** The listener
   task lives in the MCP server's event loop for the whole session. It must:
   never block the loop with an inline REST call (every render/register is
   off-loaded via `asyncio.to_thread` per 5.3); tolerate a down luxd at startup
   (guarded retry loop, like voxd's `lux_subscription.py:97-118`); and shut down
   cleanly when the session ends (cancel + drain in the lifespan `finally`). A
   leaked task, a blocking connect at startup, or an inline render would degrade
   the MCP server the session depends on for type-checking — the listener must be
   strictly best-effort relative to the tool surface.
