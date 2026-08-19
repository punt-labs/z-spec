---
description: Create or verify a B refinement machine
argument-hint: "[machine.mch] [refinement.ref]"
allowed-tools: Bash(probcli:*), Bash($PROBCLI:*), Bash(which:*), Read, Glob, Grep, Write
---

# /z-spec:b-refine - B Refinement

Create or verify a B refinement machine. B-Method's refinement chain
(Machine -> Refinement -> Implementation) lets you introduce concrete
data structures while provably preserving the abstract machine's properties.

This command has two modes:

1. **Create mode** (one argument): Generate a refinement `.ref` from an abstract `.mch`
2. **Verify mode** (two arguments): Check that a `.ref` correctly refines its `.mch`

## Input

Arguments: $ARGUMENTS

Parse arguments:

- One argument (`.mch` file): **create mode** — generate a refinement
- Two arguments (`.mch` + `.ref`): **verify mode** — check the refinement
- `--imp`: Generate an implementation (`.imp`) instead of a refinement (`.ref`)

## Process

### 0. Check Prerequisites

Verify probcli is installed:

```bash
PROBCLI="${PROBCLI:-$HOME/Applications/ProB/probcli}"
if ! which probcli >/dev/null 2>&1 && [ ! -x "$PROBCLI" ]; then
    echo "PROBCLI_NOT_FOUND"
fi
```

**If probcli not found**: Stop and tell the user:
> probcli is not installed. Run `/z-spec:setup probcli` first.

### 1a. Create Mode

#### Read the Abstract Machine

Load the `.mch` file and identify:

- Machine name
- SETS (deferred and enumerated)
- VARIABLES and their types (from INVARIANT)
- OPERATIONS (names, parameters, preconditions, effects)
- Key invariants

#### Guide the Refinement Strategy

Ask the user what data refinement they want. Common strategies:

| Abstract | Concrete | Gluing Invariant |
|----------|----------|-----------------|
| Set | Array + count | `ran(array(1..count)) = abstract_set` |
| Partial function | Two parallel arrays | `!i.(i:1..count => keys(i) \|-> vals(i) : abstract_fn)` |
| Sequence | Array + length | `!i.(i:1..length => array(i) = abstract_seq(i))` |
| Enumerated status | Integer code | `status = active <=> code = 1` |
| Unbounded NAT | Bounded 0..MAX | `concrete_val = abstract_val` |

If the user doesn't specify, suggest the simplest refinement: same data representation
with tighter bounds or minor restructuring.

#### Generate the Refinement

Create a `.ref` file:

```b
REFINEMENT MachineName_r
REFINES MachineName

VARIABLES
    /* Concrete variables */

INVARIANT
    /* Typing for concrete variables */
    /* Gluing invariant: links concrete to abstract */

INITIALISATION
    /* Must establish the gluing invariant */

OPERATIONS
    /* Must refine every abstract operation */
    /* Same signature (name, parameters, outputs) */
    /* Concrete substitution that preserves gluing invariant */
END
```

Requirements for the refinement:

1. **Every abstract operation** must appear in the refinement (same name and signature)
2. **Gluing invariant** must link concrete to abstract state
3. **INITIALISATION** must establish the gluing invariant
4. **Each operation** must preserve the gluing invariant

#### Write the File

Save to `specs/<machine_name>_r.ref` (or `specs/<machine_name>_i.imp` with `--imp`).

### 1b. Verify Mode

#### Check Refinement

Run probcli's refinement checker:

```bash
probcli <machine>.mch -refcheck <refinement>.ref
```

#### Interpret Results

**Success**: probcli confirms the refinement is correct.

**Failure**: probcli reports which refinement condition failed:

| Condition | Meaning | Fix |
|-----------|---------|-----|
| Initialisation | Concrete init doesn't establish gluing invariant | Fix INITIALISATION to satisfy gluing invariant |
| Operation X | Concrete operation X doesn't preserve gluing invariant | Ensure operation maintains the abstract-concrete link |
| Missing operation | Abstract operation not refined | Add the missing operation to the refinement |
| Deadlock | Refinement introduces deadlock | Ensure concrete preconditions aren't stricter than abstract |

### 2. Verify the Result (Create Mode)

After generating, verify the refinement:

```bash
# Type-check the refinement
probcli <machine>.mch -refcheck <refinement>.ref

# Animate the refined machine
probcli <machine>.mch -refcheck <refinement>.ref -animate 20

# Model-check the refined machine
probcli <machine>.mch -refcheck <refinement>.ref -model_check
```

### 3. Report Results

Summarize:

- Refinement file path
- Concrete variables introduced
- Gluing invariant
- Operations refined
- Verification result (pass/fail for each condition)
- Suggest next steps:
  - If create mode: `/z-spec:b-animate` to exercise the refined machine
  - If refinement: consider a second refinement step toward implementation

## Implementation Machines

With `--imp`, generate an implementation (`.imp`) instead:

```b
IMPLEMENTATION MachineName_i
REFINES MachineName_r

/* IMPORTS for reuse */

VARIABLES
    /* Must be concrete (arrays, integers, booleans) */

INVARIANT
    /* Links to refinement variables */

INITIALISATION
    /* Must be deterministic */

OPERATIONS
    /* Must be deterministic: no ANY, CHOICE, or SELECT */
    /* Loops require INVARIANT and VARIANT clauses */
END
```

Implementation restrictions:

- No nondeterministic substitutions (ANY, CHOICE, SELECT, `::`, `:`)
- WHILE loops must have INVARIANT and VARIANT for termination
- Only concrete types (no deferred sets in variables)

## Reference

- B notation: `reference/b-notation.md`
- B machine patterns: `reference/b-machine-patterns.md`
- Refinement pattern example: `reference/b-machine-patterns.md` (Refinement section)
- probcli options: `reference/probcli-guide.md`
