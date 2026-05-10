# ProB CLI Guide for Z Specifications

Reference for using probcli to validate and animate Z specifications.

## Basic Usage

```bash
probcli <model>.tex [OPTIONS]
```

ProB accepts `.tex` and `.zed` files for Z specifications.

## Common Commands

### Initialize and Parse

```bash
probcli model.tex -init
```

Parses the specification and attempts to find an initial state. Success indicates the spec is syntactically valid and has at least one valid initialization.

### Animation

```bash
probcli model.tex -animate 20
```

Randomly executes operations for N steps. Useful for:
- Verifying operations are executable
- Finding reachable states
- Checking operation coverage

Key output:
- `ALL OPERATIONS COVERED` - good sign
- Lists which operations were executed

### Constraint-Based Assertion Check

```bash
probcli model.tex -cbc_assertions
```

Uses constraint solving to check if any operation can violate assertions. Faster than model checking but may produce false positives (unreachable counter-examples).

### Constraint-Based Deadlock Check

```bash
probcli model.tex -cbc_deadlock
```

Checks if there exists a state where no operation is enabled. Note: may find unreachable deadlock states.

### Model Checking

```bash
probcli model.tex -model_check
```

Exhaustively explores reachable states. With preferences:

```bash
probcli model.tex -model_check \
    -p DEFAULT_SETSIZE 2 \
    -p MAX_INITIALISATIONS 100 \
    -p MAX_OPERATIONS 1000 \
    -p TIME_OUT 30000
```

Key preferences:
- `DEFAULT_SETSIZE` - size for given sets (default: 2)
- `MAX_INITIALISATIONS` - limit on init states to explore
- `MAX_OPERATIONS` - limit on transitions per state
- `TIME_OUT` - timeout in milliseconds

### Evaluate Expression

```bash
probcli model.tex -init -eval "dom users"
```

Evaluates a Z expression in the context of the current state.

### Interactive REPL

```bash
probcli model.tex -repl
```

Interactive mode for exploring the specification.

## Visualization

### State Space Graph

```bash
probcli model.tex -model_check -dot state_space graph.dot
```

Generates a DOT file of the state space.

### Current State

```bash
probcli model.tex -init -dot current_state state.dot
```

### Operation Enable Graph

```bash
probcli model.tex -dot enable_graph enables.dot
```

Shows which operations enable/disable each other.

## Common Issues and Solutions

### "Unbounded enumeration warning"

The specification uses unbounded sets or sequences. Solutions:
1. Add explicit bounds in the specification
2. Use `DEFAULT_SETSIZE` preference to limit exploration
3. Add scope predicates: `-scope "# users < 5"`

### "Timeout" or incomplete exploration

```bash
# Increase timeout
probcli model.tex -model_check -p TIME_OUT 60000

# Limit exploration depth
probcli model.tex -mc 1000

# Use smaller set sizes
probcli model.tex -model_check -p DEFAULT_SETSIZE 1
```

### "No counter example found, not all transitions computed"

Model checking was incomplete due to limits. Either:
- Increase limits (`MAX_OPERATIONS`, `MAX_INITIALISATIONS`)
- Accept bounded verification result
- Simplify the model

### Given set cardinality

```bash
# Set specific cardinality for a given set
probcli model.tex -card USERID 3 -model_check
```

## Animation Troubleshooting

Specifications that pass `fuzz -t` can still fail silently in probcli. These
7 patterns cause hangs, timeouts, or incorrect results during animation and
model checking. See `examples/animation-hints-good.tex` and
`examples/animation-hints-bad.tex` for complete working examples.

### 1. Cardinality Bounds Are Mandatory

Every `\finset` and `\pfun` over given sets needs a `#` constraint via axdef
constants. Without bounds, probcli enumerates all possible subsets or partial
functions, causing exponential state-space growth.

**Before** (hangs at DEFAULT_SETSIZE >= 4):
```latex
\begin{schema}{State}
  members : \finset NAME \\
  handles : NAME \pfun HANDLE
\end{schema}
```

**After** (bounded, animatable):
```latex
\begin{axdef}
  maxMembers : \nat
\where
  maxMembers = 3
\end{axdef}

\begin{schema}{State}
  members : \finset NAME \\
  handles : NAME \pfun HANDLE
\where
  \# members \leq maxMembers \\
  \dom handles \subseteq members
\end{schema}
```

### 2. Schemas Instead of Tuples

Use named schemas with fields instead of cross products (`X \cross Y \cross Z`).
probcli cannot project triples with `first`/`second`. Pattern matching
`(x, y, z) \in set` works but produces larger state spaces than schema field
access, and code that manipulates structured records becomes harder to write
and verify.

**Before** (no named field access, larger state space):
```latex
assignments : \finset (NAME \cross HANDLE \cross Relation)
```

**After** (named fields):
```latex
\begin{schema}{Assignment}
  aName : NAME \\
  aHandle : HANDLE \\
  aRelation : Relation
\end{schema}

assignments : \finset Assignment
```

### 3. Scope All Quantifiers

`\forall` and `\exists` must quantify over sets from state (e.g.,
`\forall n : members`), never over bare given types (e.g.,
`\forall n : NAME`). Bare type quantifiers cause probcli to enumerate the
entire given type, which is finite in model checking but grows exponentially
with `DEFAULT_SETSIZE`.

**Before** (enumerates all of NAME):
```latex
\forall n : NAME @ n \in members \implies n \in \dom handles
```

**After** (scoped to state):
```latex
\forall n : members @ n \in \dom handles
```

### 4. Operation Bounds

Preconditions should include `\# collection < maxBound` to prevent operations
from exceeding cardinality limits. Without this, operations can push the state
past the bounds declared in the state invariant, causing the operation to
silently fail (no valid after-state exists).

**Before** (no bound check):
```latex
\begin{schema}{AddMember}
  \Delta State \\
  name? : NAME
\where
  name? \notin members \\
  members' = members \cup \{ name? \}
\end{schema}
```

**After** (explicit capacity check):
```latex
\begin{schema}{AddMember}
  \Delta State \\
  name? : NAME
\where
  name? \notin members \\
  \# members < maxMembers \\
  members' = members \cup \{ name? \}
\end{schema}
```

### 5. Avoid Underscored Free Type Constructors

`reports\_to` works in fuzz but may cause issues in probcli's B translation.
Use camelCase or concatenated names.

**Before** (potential B translation issue):
```latex
Relation ::= reports\_to | mentors | peers
```

**After** (safe for B translation):
```latex
Relation ::= reportsTo | mentors | peers
```

### 6. No \mu for Record Construction in Operations

fuzz accepts `\mu Schema` for definite description, but probcli may not
translate it correctly. Use explicit set comprehension with field constraints
instead.

**Before** (may fail in probcli):
```latex
assignments' = assignments \cup
\quad~ \{ \mu Assignment | aName = name?
\quad~ \land aHandle = handle? \}
```

**After** (explicit comprehension):
```latex
assignments' = assignments \cup
\quad~ \{ a : Assignment | a.aName = name?
\quad~ \land a.aHandle = handle? \}
```

### 7. Use \quad~ for Indentation

`\t1`..`\t4` appear in some older Z templates and documentation, but fuzz does
not support them. pdflatex also interprets `\t` as an accent command in math
mode. Use `\quad~` throughout for portable indentation.

**Before** (breaks pdflatex):
```latex
\t1 condition1 \\
\t1 \land condition2
```

**After** (works everywhere):
```latex
\quad~ condition1 \\
\quad~ \land condition2
```

## Recommended Check Sequence

1. **Parse**: `probcli model.tex -init`
2. **Animate**: `probcli model.tex -animate 20`
3. **CBC Assertions**: `probcli model.tex -cbc_assertions`
4. **CBC Deadlock**: `probcli model.tex -cbc_deadlock`
5. **Model Check**: `probcli model.tex -model_check -p DEFAULT_SETSIZE 2`

## Exit Codes

- `0` - Success
- Non-zero - Error or counter-example found

Use `-strict` flag to ensure non-zero exit on any finding:

```bash
probcli model.tex -model_check -strict
```

## CSV Reports

```bash
# Operation coverage
probcli model.tex -model_check -csv quick_operation_coverage coverage.csv

# Variable coverage
probcli model.tex -model_check -csv variable_coverage vars.csv
```

## Environment

Set custom probcli path:
```bash
export PROBCLI="$HOME/Applications/ProB/probcli"
```

Check version:
```bash
probcli -version
```
