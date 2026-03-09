# Research: Lux Interactive State Explorer (claude-z-spec-plugin-7bf)

**Date:** 2026-03-09
**Context:** Feasibility assessment for interactive ProB state explorer in lux

---

## ProB Output → Lux Rendering Mapping

### Component 1: State Graph

**ProB output:** `-dot state_space output.dot` (GraphViz DOT format)

- Nodes: integer IDs with full state variable assignments as labels
- Edges: `state_id -> state_id` labeled with operation name + parameters
- Scale: claude-code-vox.tex produces 11,452 nodes and 52,792 transitions (87K-line DOT file)

**Lux target:** `show_diagram()` for small graphs, `draw` canvas for large graphs

**Challenge:** 11K nodes is too large for interactive display. Need:
- **Pruning**: Show only the neighborhood around the current state (depth 1-2)
- **Clustering**: Group states by session phase (spIdle, spProcessing, etc.)
- **Lazy loading**: Expand on click rather than rendering all at once
- **Alternative**: Use `show_diagram()` for ≤100 nodes (works today), draw canvas for larger

**Feasibility:** Medium. Small specs (≤100 states) work with existing diagram skill. Large specs need pruning/clustering, which is new work.

### Component 2: Operation Panel

**ProB output:** `-init` stdout lists all operations

```text
Z operation: StartSession(mode?,sid?,source?)
Z operation: SubmitPrompt(contextChunk?,hookResult?,prompt?)
...
```

28 operations for the vox spec.

**Lux target:** Button elements, one per operation. Disabled when preconditions fail.

**Challenge:** Determining which operations are enabled in a given state requires ProB evaluation. Two approaches:
- **Online**: Call `probcli -eval` for each operation's precondition in the current state (slow, ~100ms per eval)
- **Precomputed**: Model check produces the full transition graph; cache enabled operations per state ID

**Feasibility:** High for precomputed approach. Parse the DOT edges to know which operations fire from each state.

### Component 3: Invariant Dashboard

**ProB output:** `-cbc_assertions` gives binary pass/fail, no per-invariant breakdown

**Manual source:** Invariants are in the Z spec's State schema `\where` clause. Parse the LaTeX to extract individual predicates.

**Lux target:** Table element with columns [#, Invariant, Predicate, Status]. Combo filter for PASS/FAIL.

**Challenge:** Per-state invariant evaluation requires parsing the Z predicates and evaluating them against state variable values. ProB doesn't expose this per-invariant-per-state.

**Feasibility:** Medium. The invariant list is static (parse once from LaTeX). Evaluation per state requires either probcli eval or manual predicate matching.

### Component 4: Counter-Example Visualizer

**ProB output:** When `-model_check` finds a violation, it prints a trace:

```text
1: INITIALISATION(...)
2: StartSession(...)
3: SubmitPrompt(...)
...
*** COUNTER EXAMPLE FOUND ***
*** STATE = (var1=val1 & var2=val2 & ...)
```

**Lux target:** Group element with state boxes connected by operation arrows. Violating state highlighted in red, broken invariant shown.

**Feasibility:** High. The trace is a linear sequence — parse steps, render as a horizontal or vertical chain of state boxes with operation labels between them. This is a simpler version of the state graph.

### Component 5: TTF Partition Test Matrix

**ProB output:** `-csv quick_operation_coverage` gives operation coverage counts

**Partition source:** Derived from Z spec preconditions (each `\where` clause generates partition classes)

**Lux target:** Data explorer table. Columns: operation, partition class, test predicate, coverage status.

**Feasibility:** High. This is a data-explorer table with static data. The partition derivation is already done by `/z-spec:partition`.

---

## Architecture Assessment

### What works today (no new lux features needed)

| Component | Lux element | Constraint |
|-----------|------------|------------|
| Counter-example visualizer | `show_diagram()` | Linear trace ≤ 50 steps |
| Partition test matrix | `show_table()` / data-explorer | Standard table |
| Operation list | `show()` with buttons | Static list |

### What needs pruning/adaptation (LLM skill work)

| Component | Approach | Effort |
|-----------|---------|--------|
| State graph (small, ≤100 nodes) | `show_diagram()` with DOT→layers/edges translation | Medium |
| Operation panel with enabled/disabled | Parse DOT edges to precompute enabled ops per state | Medium |
| Invariant dashboard | Parse LaTeX `\where` clause + static table | Low |

### What needs new lux capabilities or significant work

| Component | Need | Effort |
|-----------|------|--------|
| State graph (large, >100 nodes) | Pruning/clustering/lazy-load in draw canvas | High |
| Per-state invariant evaluation | probcli eval integration or predicate parser | High |
| Interactive stepping (click op → advance) | recv() + re-render cycle with probcli backend | High |

---

## Recommended Phased Delivery

### Phase 1: Static Explorer (skill prompt only, no new code)

Compose existing lux elements into a read-only explorer:

1. **Model check results dashboard** — metrics cards (states, transitions, coverage) + operation coverage table. Uses `show_dashboard()`.
2. **Counter-example visualizer** — if model check found a violation, render the trace as a diagram. Uses `show_diagram()`.
3. **Partition test matrix** — TTF table from `/z-spec:partition` output. Uses `show_table()`.

This delivers immediate value with zero lux changes. The LLM runs probcli, parses output, composes lux scenes. Pure L4 data mapping over L1 rendering.

### Phase 2: Interactive Graph (needs DOT parser skill)

4. **State graph for small specs** — translate ProB DOT output to `show_diagram()` layers/edges. Prune to ≤100 interesting states (e.g., one representative per session phase).
5. **Operation panel** — buttons with enabled/disabled derived from DOT edges.

### Phase 3: Full Interactive Stepping (needs probcli integration)

6. **Click-to-step** — recv() captures operation button click, call probcli to evaluate the step, re-render with new state.
7. **Per-state invariant evaluation** — evaluate invariants against current state variables.
8. **Large graph navigation** — neighborhood view with expand-on-click.

---

## Data Flow Summary

```text
probcli -model_check → states/transitions/coverage stats → dashboard (Phase 1)
probcli -model_check → counter-example trace            → diagram   (Phase 1)
/z-spec:partition    → partition table                   → table     (Phase 1)
probcli -dot         → DOT graph                        → diagram   (Phase 2)
probcli -init        → operation list                    → buttons   (Phase 2)
probcli -eval        → per-state enabled ops             → buttons   (Phase 3)
LaTeX \where parse   → invariant predicates              → table     (Phase 3)
```
