# Development Workflow

All work in this repository runs as three nested loops. The outermost loop
owns the backlog: what is worth doing and in what order. The middle loop owns
one pull request: a single shippable, revertible change. The innermost loop
owns one mission: a single delegated piece of work inside that change.

```text
Level 1 — Backlog loop   one iteration = one work batch     (beads)
  Level 2 — PR loop      one iteration = one pull request
    Level 3 — Mission    one iteration = one delegated mission
                         (design, code, test — a do-while)
```

Each level hands work down and receives finished results back. Escalation of
scope only goes up: a mission that uncovers a bigger problem grows its PR; a
PR that uncovers a new line of work files a bead for the backlog loop. Defects
move the other way — anything found while a PR is open is fixed in that PR,
never sent back to the backlog.

The pseudocode at each level gives the control flow; a small Z schema at each
level gives the doorway conditions — what must be true to enter an iteration
and what must be true to leave it. This repo is the Z toolkit; its own workflow
is stated in Z. The state those schemas observe:

```text
LoopState
  signals       : ℙ SIGNAL  -- issues, alerts, messages not yet triaged
  open          : ℙ BEAD    -- open beads: the single work funnel
  validated     : ℙ BEAD    -- re-proven against current main
  claimed       : ℙ BEAD    -- the current batch
  closed        : ℙ BEAD    -- beads completed by a merged PR
  activeWorkers : ℙ WORKER  -- sub-agents editing the shared worktree
  testCount     : ℕ         -- tests collected by the suite
  ------------------------------------------------------------------
  validated ⊆ open
  claimed   ⊆ validated
  open ∩ closed = ∅         -- a bead is open or closed, never both
```

A bead's lifecycle is a walk through these sets: `open → validated → claimed
→ closed`. Steps that were performed ("the acceptance flight passed") appear as
named predicates over declared terms, never as bare primed flags.

## Roles

The operator owns requirements and design direction, rules on genuine design
forks, and confirms the acceptance flight on screen. Claude runs everything
else: the backlog, the missions, the review cycles, and the merges. Review of
code is done by agents — the local review agents plus Copilot and Bugbot on the
PR. There is no human review gate. The operator reads code in the IDE, but that
inspection is separate, feeds design discussion only, and nothing in these loops
waits on it.

## Level 1 — The backlog loop

The backlog loop keeps the bead tracker true and decides what to work on
next. Beads are the single funnel: every piece of work, whatever its origin,
is a bead before it is anything else. One iteration selects and completes one
batch of work. The loop runs at session start and again whenever the current
batch is done.

```text
function backlog_loop():

    # 1. INTAKE — every signal becomes a bead or is disposed at the door
    for signal in [github_issues, dependabot_alerts, biff_messages,
                   operator_requests, new_scope_found_while_working]:
                   # a defect inside an open PR's unit is fixed in that PR,
                   # never filed — only genuinely NEW scope arrives here
        if duplicate(signal):  close_at_door(signal, link_existing_bead)
        elif invalid(signal):  close_at_door(signal, stated_reason)
        else:                  bd_create(signal, labels, link_back_to_source)

    # 2. VALIDATE — a bead must be true before it is workable
    for bead in candidates(bd_ready):
        confirm it is still real against current main
        confirm nothing merged or decided has superseded it
        confirm it is one rollback-coherent unit (split or merge if not)
        confirm its blocked-by links reflect reality
        otherwise: fix the bead, or close it with the reason

    # 3. ASSESS — automatic ordering; escalate only on a genuine fork
    order = sort(validated, by:
        security severity                  # open HIGH/CRITICAL first, always
        > broken user journeys             # a spec that will not type-check,
                                           #   a menu entry that renders nothing,
                                           #   an MCP tool that crashes
        > active epic continuity           # finish what is started
        > debt that blocks throughput      # decomposition, ratchet paydown
        > features)                        # v1 scope before v2
    if the ordering hits a fork the charter cannot resolve:
        ask the operator for a focus ruling
    else:
        proceed without asking

    # 4. SELECT AND EXECUTE
    batch = claim a realistic set from the top of the order
    for unit in rollback_coherent_units(batch):
        pr_loop(unit)                      # Level 2

    # 5. CLOSE OUT
    close GitHub issues resolved by the merged PRs, linking each PR
    send the batch recap via beadle-email  # to jim@punt-labs.com; covers what
                                           # the per-merge recaps do not: intake
                                           # dispositions, beads closed at
                                           # validation, order changes
    return to intake — new signals have accrued while working
```

Entry and exit for one batch iteration:

```text
EnterBatch ≙ [ LoopState ]                -- no precondition: the backlog loop
                                          -- is a do-while(true); intake always
                                          -- has standing to run

ExitBatch ≙ [ Δ LoopState |
  intakeDisposed(signals)                 -- every signal observed at this
                                          --   iteration's intake became a bead
                                          --   or was closed at the door with a
                                          --   reason; new signals keep accruing,
                                          --   so the live queue is never empty
  ∧ claimed′ = ∅ ∧ claimed ⊆ closed′      -- the batch drained: every claimed
                                          --   bead closed by a merged PR
  ∧ resolvedIssuesClosed(mergedPRs)       -- GitHub issues answered with their PR
  ∧ batchRecapSent(claimed) ]
```

### Intake

Work arrives from five places: GitHub issues, Dependabot security alerts, biff
messages from agents in other repositories, requests from the operator, and new
lines of work discovered while building. That last source carries a boundary: a
defect found inside the unit of an open PR is fixed in that PR and never becomes
a bead; only genuinely new scope — discovered outside any open PR, or clearly a
separate rollback unit — enters at intake. At intake, each signal is either
turned into a bead or closed at the door with a stated reason — duplicate of an
existing bead, or invalid. Nothing is left sitting in an external queue: a
GitHub issue gets a reply naming its bead, and it is closed when that bead
closes.

Security alerts map severity to priority: a critical or high alert becomes a
P1 bead and goes to the front of the order. Security work does not wait.

Intake must not depend on remembering to look. A recurring poll (via the
`/loop` skill) or a session-start sweep checks the GitHub issue list and the
Dependabot alert list, so an alert filed overnight is a bead by the time the
first batch is selected. Start every session with `/loop 2m /biff:read` so
messages from sibling repos — lux and vox both consume z-spec — surface too.

### Validation

The codebase moves; beads rot. Before a bead is workable, confirm it is still
real: reproduce the bug or re-check the premise against current main, confirm
no merged PR or design decision has superseded it, confirm it describes one
rollback-coherent unit of work, and confirm its dependency links are correct.
A stale bead is closed with the reason. A bloated bead is split. Validation
covers the candidates for the coming batch, not the whole backlog every time.

### Assessment

Ordering is automatic in the steady state. The sort is:

1. **Security severity.** Open high or critical alerts outrank everything.
2. **Broken user journeys.** A bug on a path users actually hit — a spec that
   will not type-check, a `check` that reports a false pass, a menu entry that
   renders an empty pane, an MCP tool that raises instead of reporting — beats
   new work.
3. **Active epic continuity.** An epic in flight keeps its claim until it is
   done. Interleaving epics is how a backlog churns without shipping.
4. **Debt that blocks throughput.** Decomposition, ratchet paydown, and test
   infrastructure that makes the next ten changes cheaper.
5. **Features.** v1 scope before v2; beads labeled `v2` wait.

The operator is asked for a focus ruling only when the ordering hits a genuine
fork the rules above cannot resolve: two epics competing to be the active one, a
strategic pivot, or a drift in the debt-versus-feature balance that changes what
shipping means. Direction belongs to the operator; sequencing inside a settled
direction does not require asking.

## Level 2 — The PR loop

One iteration of the PR loop produces one merged pull request. It is entered
when the backlog loop hands down a unit of work sized for throughput, and it
runs the missions (Level 3) needed to build that unit.

### Sizing: throughput, not purity

Nobody reads these diffs. Agents review them, and they squash-merge. So the
size of a PR is an economic decision, not a hygiene one:

- **The floor is transaction cost.** Every PR pays a roughly fixed overhead —
  branch, full-diff review rounds, the acceptance flight, CI, remote review
  cycles, the merge gate, the recap. A PR too small pays that overhead for too
  little value.
- **The ceiling is reviewer effectiveness.** The reviewers are agents, and
  past a certain diff size their quality drops: local review agents lose focus
  across a sprawling diff, and the remote reviewers degrade outright on very
  large ones. A PR too large buys throughput at the cost of review quality.
- **The typical right size** is several small beads batched together, or one
  coherent slice of a larger bead. A bead too large to slice into one PR is
  mis-filed: decompose it into an epic whose child beads fit the band.
- **Rollback coherence still binds.** Whatever merges must revert together
  sensibly. That is the one structural constraint. "Purity," "one concern per
  PR," and "keep the diff small" are not criteria — a docs fix, a ratchet
  paydown, or an adjacent bug fix riding along is welcome, and an improvement
  is never held back or split out for tidiness.

**One branch, one PR.** A design step is a commit in the same PR, never a
separate design branch with its own doc-PR and review cycle. That ceremony was
tried on PR #81/#82 and it cost a full extra review loop for nothing.

```text
function pr_loop(unit):

    # A. BUILD — missions, one at a time
    branch from main
    if unit is architectural (new command, new client surface, cross-cutting
                              state, a stateful protocol):
        design mission first, with no prescribed write-set
        leader reviews the design end-to-end and STRIKES any migration,
            compat, shim, or version-bridge element before it reaches code
        substantive issues go to the operator as concrete decisions
            (each with a recommendation), one ASK per issue
        implementation waits for the operator's ratification
    for mission in unit:
        mission_loop(mission)             # Level 3
        # bug fixes are TDD: a failing test reproduces the defect first
        # coverage rises with every mission; stateful work is modelled in Z
        #   before it is implemented

    # B. FULL-DIFF VERIFICATION (local, before any PR exists)
    make check                            # full gate on the accumulated diff
    agents = 2 to 6 review agents by scope
    repeat:
        findings = run all agents on the full diff
        fix every finding in this PR      # no deferrals
    until a round produces zero findings

    # C. ACCEPTANCE FLIGHT — the feature is RUN, before the PR exists
    make uat                              # build the wheel, install the CLI
    reconnect the z-spec MCP server       # a reinstall does NOT restart it;
                                          #   a stale server demos the old build
    write down the expected outcome, then drive the real entry point:
        the CLI verb, the MCP tool, and the lux menu entry
    run every applicable row of docs/testing/manual-tests.md
    capture machine evidence on both tiers:
        Hub store (list_menus, list_scenes, inspect_scene) and
        Display behavior (list_recent_events, list_errors, screenshot)
    the operator confirms the sensory outcome: what actually rendered,
        the labels, the interaction — the part no introspection API attests

    # D. SHIP
    bd close the bead(s)
    push; create the PR (description carries the flight rows and their results)
    request Copilot review once, on open
    schedule a background poll with /loop   # never gh pr checks --watch,
                                            # never foreground sleep loops

function poll_tick(pr):
    state = current reviews, threads, checks
    for finding in unaddressed(state):    # handled now, never on a later tick
        delegate the fix to a bare agent  # or reply with the concrete reason
                                          # the finding does not apply
        make check; commit; push          # each push restarts the gate
        resolve the thread ONLY after a landed commit closes it, one by one,
            never in bulk — the leader resolves, not the agent
    if merge_gate(state): merge (squash, --delete-branch); close_out()

function merge_gate(state) -> bool:
    return CI green on the latest commit
       and Copilot has reviewed the latest commit   # main's ruleset REQUIRES a
                                                    #   Copilot review to exist
       and (Bugbot has reviewed the latest commit
            or Bugbot never reviewed this PR and more than six minutes
               have passed since CI went green)
       and zero unresolved review threads
       and the latest review round had zero material findings
    # When this returns true: merge EXPLICITLY. No --auto. No --admin.
    # Do not ask, do not wait.

function close_out():
    cancel the poll loop
    delete the branch; checkout main; pull
    send the merge recap via beadle-email # to jim@punt-labs.com, every merge,
                                          # unprompted — a permanent record in
                                          # the 8-part recap structure
    start the next unit immediately       # no stopping to report
```

Entry and exit for one PR iteration. `merge_gate` in the pseudocode is the
pre-merge subset of these conditions; `ExitPR` describes the state after
close-out completes.

```text
EnterPR ≙ [ LoopState; unit : ℙ BEAD |
  unit ⊆ claimed
  ∧ rollbackCoherent(unit)                -- reverts together sensibly
  ∧ inThroughputBand(unit)                -- above transaction cost,
                                          --   below reviewer degradation
  ∧ (architectural(unit) ⇒ designRatified(unit)) ]  -- operator has ruled

ExitPR ≙ [ Δ LoopState; pr : PR |
  merged(pr)
  ∧ localFindings(pr) = ∅                 -- held BEFORE the PR opened
  ∧ flightPassed(pr)                      -- held BEFORE the PR opened
  ∧ ciGreen(head(pr))
  ∧ reviewedByBots(head(pr))              -- Copilot + Bugbot on the latest
                                          --   commit, per the merge_gate rules
  ∧ unresolvedThreads(pr) = ∅
  ∧ materialFindings(latestRound(pr)) = ∅
  ∧ beadsOf(pr) ⊆ closed′
  ∧ mergeRecapSent(pr) ]
```

`flightPassed` and `localFindings = ∅` are conditions on `ExitPR`, but both are
established **before the PR is opened**. A PR that opens without them is not
early — it is a procedural violation that spends remote review cycles on code
that has never run.

### Local review before the PR

Full-diff local review is where issues die cheaply. A local round costs
seconds; a remote review cycle costs minutes to hours. The 2–6 agents are
chosen by scope: `code-reviewer` and `silent-failure-hunter` always — the latter
matters especially here, where a swallowed `fuzz` or `probcli` failure becomes a
false "type-checked" the user cannot distinguish from a real one; the
type-design analyzer when a new type, dataclass, or Protocol appears; the
comment analyzer for significant documentation changes; the test analyzer when
tests are added or restructured; the code simplifier last, once the others are
clean. Every finding is fixed in this PR. A dismissal requires the exact
finding, the specific reason it does not apply, and the code reference. Opening
a PR with unresolved local findings is a procedural violation.

### The acceptance gate

`make check` passing means the code compiles, the types hold, the unit tests
pass, and every spec in `examples/` type-checks and model-checks. It does not
mean the feature works. Every user-facing surface z-spec ships — the `z-spec`
CLI, the `zspec` MCP tools, the slash commands, the lux menu and its scenes — is
driven by a human before any PR opens.

The sequence is fixed:

1. `make check` green.
2. `make uat` — build the wheel and install the CLI.
3. Reconnect the z-spec MCP server. A reinstall does **not** restart a running
   stdio server; the dev plugin's `uv run --directory` picks up source only on
   restart. Demoing a stale server proves nothing about the change.
4. Write down the expected outcome for each row of
   [`docs/testing/manual-tests.md`](testing/manual-tests.md), then run the row
   and compare. Every difference is a bug, fixed in this PR.
5. For lux surfaces, capture Hub-side introspection **and look at the window**.
   The two diverge: a scene can hold 838 elements and render an empty pane. A
   `screenshot` is evidence; `inspect_scene` alone is not.
6. The operator confirms what no API attests — that what rendered is what a
   person would want to see.

This is the one human gate in the loops, and it is a demo, not a diff. It is
also the gate whose absence produced PR #82: the feature was declared verified
from unit tests plus Hub introspection, taken to PR, and only then found
unusable — scratch files listed as specs, tabs labelled with truncated paths, an
empty content pane, a Tutorial stuck on "Loading…". Review agents and Bugbot
cannot catch that class of defect. Only running it can.

## Level 3 — The mission loop (design, code, test)

One iteration is one delegated mission: a single piece of design,
implementation, test, or review work executed by a specialist sub-agent under
an ethos mission contract. The next mission does not start until this loop
completes on the current one.

The mission loop is a do-while: the work runs at least once, and the
review-and-fix cycle repeats until a round comes back clean.

```text
function mission_loop(mission):
    contract = write_contract(mission)   # problem, invariants, quality bar,
                                         # commit discipline — never a
                                         # write-set for design work
    dispatch(contract)                   # mission create + background spawn;
                                         # verify the worker is running
    do:
        worker designs / codes / tests   # tests lead; TDD for bug fixes;
                                         # stateful work is modelled in Z
                                         # BEFORE implementation
        worker commits locally           # each commit passes make check
        result   = worker submits
        findings = evaluator review      # a DISTINCT specialist
                 + leader verification   # make uat; drive the real entry
                                         # point; review agents on the
                                         # mission diff
        if findings: reflect(findings)   # another round, same mission
    while findings remain
    close(mission)
```

Entry and exit for one mission iteration:

```text
EnterMission ≙ [ LoopState; m : MISSION |
  contracted(m)                           -- problem, invariants, quality bar
  ∧ workerRunning(m)                      -- dispatch is two operations; a
                                          --   contract alone is orphaned work
  ∧ activeWorkers = {workerOf(m)}         -- one worker at a time in a shared
                                          --   worktree
  ∧ (statefulClass(m) ⇒ modelChecked(m)) ]  -- Z model before code

ExitMission ≙ [ Δ LoopState; m : MISSION |
  verdict(m) = accept                     -- from an evaluator ≠ worker
  ∧ findings(m) = ∅                       -- the do-while ran dry
  ∧ (∀ c : commitsOf(m) • checkGreen(c))  -- every commit passed make check
  ∧ testCount′ ≥ testCount                -- coverage never decreases
  ∧ ratchetsHeld(m)                       -- OO, coupling, suppression: no
                                          --   metric regressed; ≥ 1 improved
  ∧ missionClosed(m) ]
```

`statefulClass(m)` holds when the mission changes a subsystem with three or more
modes and transitions between them, or an invariant that must hold across
transitions — the lux session lifecycle (`disconnected → registering → listening
→ swept`), the menu registration and lease discipline, the report persistence
protocol. It does NOT hold for pure parsing helpers, binary wrappers, formatting
changes, or single-function fixes with no state. When it holds, the model
(`docs/<feature>.tex`) is `fuzz`-clean and, for higher-stakes invariants,
ProB-model-checked, BEFORE the implementation mission dispatches. This repo
ships that capability; it uses it on itself.

### Who does what

The leader runs the workflow; the specialists produce the work. The boundary
is strict in both directions.

**The leader owns the workflow.** The backlog, the mission contract, dispatch,
monitoring, the local review agents (run on each mission's diff and on the full
diff), the acceptance flight, and every git and GitHub operation: branches,
pushes, opening the PR, driving remote review, resolving threads, merging, and
closing out. The leader does not write production code. The only files the
leader authors directly are the doc set — `CHANGELOG.md`, `CLAUDE.md`,
`README.md`, `TESTING.md`, this `WORKFLOW.md`, design docs, and plan files — and
those still ship through PRs.

**The worker owns the work.** The thinking and the code inside its mission —
the design decisions its contract leaves open, the tests, the implementation,
and local commits on the current branch. A worker never creates branches, never
pushes, never opens PRs, and never touches review threads. Putting workflow
operations into a worker's prompt is a contract defect.

**The evaluator** — always a different specialist from the worker — reviews the
worker's result inside the mission before the leader accepts it. The pairings
live in `CLAUDE.md`.

**Remote review findings are the one delegation that is not a mission.** When
Copilot or Bugbot report on the PR, the leader reads each finding and hands the
mechanical fix to a bare `Agent()`, then pushes and resolves the thread itself.

### The lifecycle

1. **Contract.** The leader writes the mission contract: the problem, the
   invariants, the quality bar, and the commit discipline — one commit per
   logical step, each passing `make check`, never more than thirty minutes of
   work uncommitted. A design mission's contract never prescribes a write-set;
   the specialist decides what to create, split, or extract. For protocol or
   data work the contract cites the OO rules (`../.claude/rules/python-*.md`)
   with a BEFORE/AFTER example, because sub-agents revert to procedural habits
   when the prompt is not explicit.
2. **Dispatch is two operations.** `ethos mission create` writes the contract;
   a separate `Agent(subagent_type=<worker>, run_in_background=true)` spawn
   starts the worker. Verify the worker is actually running — a contract with
   no agent behind it is orphaned work.
3. **The worker executes.** Tests lead: a bug fix starts from a failing test
   that reproduces the defect, and the fix is done when it passes; a feature
   ships its tests with the code; the test count never goes down. Stateful work
   gets its Z model before implementation. Every commit passes `make check` —
   zero exceptions, zero unauthorized suppressions.
4. **The leader monitors by the filesystem, never by git activity.** A worker
   editing files is working, even with zero commits — analysis and reading are
   invisible. Progress is judged by whether the working tree is changing and
   advancing. An empty commit log is never a reason to intervene, commit by
   proxy, or stop the agent. A genuine stall — no file changes over a long
   window and no response to a status message — is the only cause for taking
   over. Monitoring is silent: concrete facts or action, no narration of the
   wait.
5. **Result and evaluation.** The worker submits its result; a distinct
   evaluator reviews it; reflect-and-advance rounds continue until the
   evaluator accepts.
6. **The leader verifies and closes.** Check the result against the contract:
   `make uat`, reconnect the MCP server, and exercise the change through its
   real entry point with the expected output written first — one invalid input,
   one missing dependency (`fuzz` or `probcli` absent), one boundary. Run the
   applicable local review agents on the mission diff and fix every finding; a
   dismissal requires the exact finding, the specific reason it does not apply,
   and the code reference. If the result raises a design question, it goes to
   the operator as a concrete decision — with a recommendation — before any
   dependent mission dispatches. Then close the mission.

## Invariants

1. **Beads are the single funnel.** Every piece of work is a bead before it is
   anything else; external queues (issues, alerts) drain into it at intake.
2. **The feature is run before the PR opens.** `make check` is necessary and
   never sufficient. The acceptance flight against the installed artifact is
   the verification of record for every user-facing surface.
3. **A satisfied merge gate means merge now.** The gate is the only path to a
   merge, and nothing waits once it passes. Merge is always explicit — never
   `--auto`, never `--admin`.
4. **Findings never wait.** Review feedback is handled the moment it arrives,
   not on the next poll tick and never in a follow-up PR. Threads are resolved
   only against a landed commit, one by one, never in bulk.
5. **Every push restarts the merge gate.** Fresh CI and fresh reviews on the
   new commit, with the single Bugbot exception stated in the gate.
6. **Defects flow inward, scope flows outward.** A defect found while a PR is
   open is fixed in that PR. Only genuinely new lines of work become beads.
7. **One branch, one PR.** Design is a commit inside the PR that implements it,
   never a separate branch, doc-PR, and review cycle.
8. **The operator gates the acceptance flight and direction, never diffs or
   sequencing.**
9. **No migration, compat, shim, or version-bridge code.** Punt Labs products
   have no installed base to migrate; the leader strikes any such element at
   design review, before it reaches implementation.
10. **Close-out is inside the loop.** The recap email, branch hygiene, and
    starting the next unit are steps of the loop, not afterthoughts.
