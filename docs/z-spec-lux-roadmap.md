# Z-Spec Lux Integration Roadmap

**Bead:** claude-z-spec-plugin-7bf (Lux integration: interactive state explorer)
**Date:** 2026-03-09
**Status:** Research complete, phased delivery planned

---

## Vision

A Z specification IDE in lux. Run `/z-spec:test` and instead of
scrolling through probcli text output, see an interactive visual
explorer: browse states, click operations, inspect invariants, walk
through counter-examples.

---

## Context

### ProB Output Formats

probcli produces structured output that feeds directly into lux
elements:

| Output | Flag | Content | Scale (vox spec) |
|--------|------|---------|-------------------|
| State space DOT | `-dot state_space file.dot` | Full graph: nodes with state variable labels, edges with operation labels | 11,452 nodes, 52,842 edges, 87K-line file |
| Operation list | `-init` stdout | `Z operation: Name(params)` per line | 28 operations |
| Model check stats | `-model_check` stdout | States analysed, transitions fired, coverage | Summary line |
| Counter-example trace | `-model_check` stdout (on violation) | Step-by-step: operation → state | Linear sequence |
| Assertion check | `-cbc_assertions` stdout | Pass/fail per assertion | Binary result |
| Coverage CSV | `-csv quick_operation_coverage` | Operation, covered (bool), times (count) | One row per operation |

### Lux Rendering Capabilities

| Element | Use case | Performance |
|---------|----------|-------------|
| `show_dashboard()` | Metric cards + charts + table | Excellent (built-in) |
| `show_diagram()` | Layered node/edge graph | Good for ≤100 nodes |
| `show_table()` | Filterable table with detail panel | Excellent (60fps filtering) |
| `draw` canvas | Custom rendering (circles, lines, text) | Good, no built-in zoom/pan |
| Buttons | Operation panel | Good, disabled state supported |
| `recv()` | User interaction (clicks, selections) | Blocking, ~1ms latency |

### The Scale Problem

11K nodes can't render interactively. Structural properties to exploit:

- **Session phase clustering**: States group by `sessionPhase` (spIdle,
  spProcessing, etc.). Within a phase, states differ only in tool/vox/biff
  state. Show phases as clusters, expand on click.
- **Edge collapsing**: `StartSession` with 5 permission modes × 4 sources
  = 20 edges to 5 targets. Collapse to one labeled edge with parameter
  dropdown.
- **Neighborhood view**: Show current state + 1-2 hops. Like a debugger
  stepping through code, not a map of all code.

---

## Phased Delivery

### Phase 1: Static Explorer (no lux changes)

**Effort:** Skill prompt enhancement to `/z-spec:test`
**Prerequisite:** lux-t1p (display mode toggle)
**Deliverable:** When lux is enabled, `/z-spec:test` renders results
visually instead of text.

#### 1a. Model Check Dashboard

**Lux element:** `show_dashboard()`
**Data source:** probcli `-model_check` stdout

Metric cards:
- States analysed (e.g., 11,452)
- Transitions fired (e.g., 48,802)
- Coverage (e.g., 25/26 operations)
- Result: PASS / FAIL

Operation coverage table:
- Columns: Operation, Times Fired, Status (covered/uncovered)
- Data: Parse probcli `-coverage` output or DOT edge counts
- Filters: search by operation name, combo for status

#### 1b. Counter-Example Visualizer

**Lux element:** `show_diagram()`
**Data source:** probcli trace output (when violation found)

Renders the trace as a linear chain:

```text
[Init] → StartSession → [state 2] → SubmitPrompt → [state 5] → ... → [VIOLATION]
```

- Layers: one per step (top to bottom)
- Nodes: state ID + key variable values
- Edges: operation name + parameters
- Final node: red, with broken invariant displayed

Only renders when a counter-example exists. Otherwise, the dashboard
shows "No counter-example found."

#### 1c. Partition Test Matrix

**Lux element:** `show_table()` (data-explorer pattern)
**Data source:** `/z-spec:partition` output

Columns: Operation, Partition Class, Test Predicate, Coverage Status
Filters: search by operation, combo by coverage (covered/uncovered/all)

#### Implementation

The LLM's job reduces to a data pipeline (the Lux blog post pattern):

1. Run `probcli <spec>.tex -model_check -coverage ...`
2. Parse stdout for stats, coverage, and traces
3. Compose lux scene JSON with metric cards + table + optional diagram
4. Call `show()` once

~40 lines of data mapping. ~100 lines of skill prompt instructions.
Zero lux code changes. This is the L4 composition over L1 rendering
that the blog post describes.

---

### Phase 2: Interactive Graph (DOT parser skill)

**Effort:** Medium — skill prompt work + DOT parsing logic
**Prerequisite:** Phase 1 proven valuable

#### 2a. State Graph for Small Specs

**Lux element:** `show_diagram()`
**Data source:** probcli `-dot state_space`

For specs with ≤100 states:
- Parse DOT nodes: extract state ID, variable values from label
- Parse DOT edges: extract source, target, operation name
- Map to `show_diagram()` format: layers (group by session phase),
  nodes (state ID + key variables), edges (operation labels)

For specs with >100 states:
- Cluster by session phase (one node per phase cluster)
- Show transition counts between clusters
- Click to expand a cluster into its individual states

#### 2b. Operation Panel

**Lux element:** Buttons
**Data source:** DOT edge list

One button per Z operation. For the current state (selected node in
the graph), parse DOT edges to determine which operations have outgoing
edges. Disable buttons for operations with no edge from the current
state.

No probcli eval needed — the DOT graph is the precomputed ground truth
for operation enablement.

#### 2c. Invariant List

**Lux element:** Table
**Data source:** Parse LaTeX `\where` clause from spec

Static table of invariants extracted from the State schema. Columns:
#, Invariant Name (derived from comment), Predicate (LaTeX), Status
(PASS for model-checked specs, UNKNOWN otherwise).

Per-state evaluation deferred to Phase 3.

---

### Phase 3: Full Interactive Stepping (probcli integration)

**Effort:** Significant — requires probcli as a live backend
**Prerequisite:** Phase 2 proven valuable

#### 3a. Click-to-Step Animation

- User clicks an enabled operation button
- Skill calls `probcli -eval` to compute the next state
- Re-renders the graph with the new current state highlighted
- recv() → eval → show() loop

Requires probcli to support incremental evaluation (it does via
`-repl` mode, but integrating the REPL with a skill's recv() loop
is new territory).

#### 3b. Per-State Invariant Evaluation

When user selects a state node:
- Extract state variable values from DOT label
- Evaluate each invariant predicate against the values
- Update invariant table: green for satisfied, red for violated

Two approaches:
- **probcli eval**: Pass each invariant as a predicate to
  `probcli -eval "predicate"` in the current state. Correct but slow.
- **Predicate parser**: Parse Z predicates into evaluable expressions.
  Fast but complex (needs to handle ⟹, ∈, #, ≤, etc.).

#### 3c. Large Graph Navigation

Neighborhood view for specs with >100 states:
- Show current state + adjacent states (depth 1-2)
- Click an adjacent state to recenter
- Breadcrumb trail showing the path taken
- Search: find a state by variable values

Requires either:
- draw canvas with custom layout (spring/hierarchical)
- Or a new lux element type for graph navigation

---

## Data Flow Architecture

```text
Phase 1:
  probcli -model_check  ──► parse stdout  ──► show_dashboard()
  probcli trace output   ──► parse steps   ──► show_diagram()
  /z-spec:partition      ──► parse table   ──► show_table()

Phase 2:
  probcli -dot           ──► parse DOT     ──► show_diagram()
  DOT edge list          ──► per-state ops ──► buttons (disabled/enabled)
  LaTeX \where clause    ──► parse preds   ──► table (static)

Phase 3:
  recv() click           ──► probcli -eval ──► show() re-render
  state variable values  ──► eval preds    ──► table (dynamic)
  DOT neighborhood       ──► prune/layout  ──► draw canvas
```

---

## Boundary Analysis (DES-009 / DES-010)

This is **z-spec consuming lux as a building block.** Per DES-009:

- z-spec owns the data pipeline (ProB output parsing, state
  classification, invariant extraction)
- lux owns the rendering (tables, diagrams, buttons, draw canvas)
- z-spec calls lux MCP tools — lux has no awareness of Z specs

Per DES-010:
- `/lux y` must be enabled for visual rendering
- z-spec's skill checks lux availability before composing scenes
- Without lux: degrade to text output (current behavior)

Per the L1/L4 boundary (blog post):
- L1 (deterministic): lux rendering, probcli model checking
- L4 (agentic): data mapping from probcli output to lux JSON
- The verification gap exists only in the ~40-line data pipeline

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| DOT files too large for diagram element | High (>100 states) | Phase clustering; neighborhood view in Phase 3 |
| probcli output format changes | Low (stable tool) | Pin probcli version; regex-based parsing |
| Skill prompt too complex for reliable LLM execution | Medium | Break into sub-skills; use MCP tools for heavy parsing |
| Phase 3 probcli REPL integration fragile | Medium | Defer until Phases 1-2 prove value |

---

## Relationship to Other Beads

| Bead | Relationship |
|------|-------------|
| `lux-t1p` (display mode toggle) | Prerequisite for all phases |
| `claude-z-spec-plugin-uq7` (L1 tooling) | Convention checker and coverage auditor could feed Phase 1 dashboard |
| `claude-z-spec-plugin-t2p` (SVG export) | Closed — superseded by lux native rendering |
| `claude-z-spec-plugin-2p2` (graphviz install) | Closed — superseded by lux diagram rendering |
