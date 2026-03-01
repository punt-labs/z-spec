# PRD: /z-spec:b-refine

## Problem

B-Method's core value proposition is its refinement chain: Abstract Machine ->
Refinement -> Implementation. Each step introduces more concrete detail while
provably preserving the abstract machine's properties. The gluing invariant
links concrete state to abstract state, and ProB can mechanically verify that
every refined operation correctly implements its abstract counterpart.

Today there is no command to create a refinement machine or verify that a
refinement is correct. Users must manually write `.ref` files and invoke
probcli's refinement checking flags.

## Solution

A new `/z-spec:b-refine` command with two modes:

1. **Create mode** --- generate a refinement (`.ref`) or implementation (`.imp`)
   from an abstract machine, with the user defining the data refinement strategy
2. **Verify mode** --- check that an existing refinement correctly refines its
   abstract machine using probcli's refinement checker

## Scope

### In Scope

- New `commands/b-refine.md` and `commands/b-refine-dev.md` skill prompts
- Refinement machine (`.ref`) scaffold generation
- Implementation machine (`.imp`) scaffold generation
- Gluing invariant guidance (user defines the data mapping)
- Refinement verification via probcli (`-refcheck`)
- Updates to `commands/help.md` and `README.md`

### Out of Scope

- Automatic gluing invariant inference
- Atelier B proof obligation generation (probcli only)
- Multi-level refinement chains (single refinement step per invocation)
- Code generation from implementation machines

## Refinement Conditions

B refinement requires these conditions (verified by probcli):

### 1. Initialisation Refinement

The concrete initial state, when linked via the gluing invariant, satisfies
the abstract initial state.

### 2. Operation Refinement

For each abstract operation, the concrete operation preserves the gluing
invariant: if the gluing invariant holds before, it holds after.

### 3. Non-divergence

Concrete operations terminate (no infinite internal loops).

### 4. Deadlock Freedom Preservation

If the abstract machine is deadlock-free, the refinement is too.

## User Workflow

```text
/z-spec:b-create A user registry with add and remove        # Abstract machine
/z-spec:b-check specs/registry.mch                          # Verify abstract
/z-spec:b-animate specs/registry.mch                        # Animate abstract
/z-spec:b-refine specs/registry.mch                         # Create refinement
/z-spec:b-refine specs/registry.mch specs/registry_r.ref    # Verify refinement
```

## Success Criteria

- Create mode produces a valid `.ref` file with gluing invariant and refined
  operations that passes `probcli Machine.mch -refcheck Refinement.ref`
- Verify mode runs `probcli -refcheck` and reports pass/fail with details
- User is guided through defining the gluing invariant (concrete-to-abstract
  state mapping) interactively
- Generated refinement preserves all abstract operations
