---
description: Create a B machine from description or translate an existing Z spec
argument-hint: "[description or file.tex]"
allowed-tools: Bash(probcli:*), Bash($PROBCLI:*), Bash(which:*), Read, Glob, Grep, Write
---

# /z-spec:b-create - Create B Machine

You are creating a B Abstract Machine Notation (AMN) specification. B machines are
executable formal specifications that can be type-checked, animated, model-checked,
and refined toward implementation --- all using probcli.

This command has two modes:

1. **Description mode**: Create a B machine from a natural language description
2. **Translation mode**: Translate an existing Z specification (`.tex`) to a B machine

## Input

Hint: $ARGUMENTS

Determine the mode:

- If the argument is a path to a `.tex` file: **translation mode**
- Otherwise: **description mode** (treat as natural language description)

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

### 1. Create specs/ Directory

```bash
mkdir -p specs
```

Update `.gitignore` if needed:

```bash
for pattern in "specs/*.prob" "specs/*.prob2project"; do
    grep -qxF "$pattern" .gitignore 2>/dev/null || echo "$pattern" >> .gitignore
done
```

### 2a. Description Mode

If working from a natural language description:

#### Analyze the Description

Extract:

- **Entities**: What things does the system track?
- **Attributes**: What properties do entities have?
- **Constraints**: What must always be true?
- **Operations**: What state transitions exist?
- **Relationships**: How do entities relate to each other?

#### Generate the Machine

Create a `.mch` file following this structure:

```b
MACHINE MachineName

SETS
    /* Deferred sets for entity identifiers */
    ID;
    /* Enumerated sets for status values */
    STATUS = {active, inactive}

CONSTANTS
    max_capacity

PROPERTIES
    max_capacity : NAT &
    max_capacity = 100

VARIABLES
    /* State variables */
    entries,
    statuses

INVARIANT
    /* Typing constraints */
    entries : ID +-> NAT &
    statuses : ID +-> STATUS &
    /* Domain consistency */
    dom(entries) = dom(statuses) &
    /* Business invariants */
    card(entries) <= max_capacity

INITIALISATION
    entries := {} ||
    statuses := {}

OPERATIONS
    /* Operations with PRE/THEN substitutions */
    add(id, val) =
        PRE id : ID & val : NAT &
            id /: dom(entries) &
            card(entries) < max_capacity
        THEN
            entries := entries \/ {id |-> val} ||
            statuses := statuses \/ {id |-> active}
        END;

    remove(id) =
        PRE id : ID & id : dom(entries)
        THEN
            entries := {id} <<| entries ||
            statuses := {id} <<| statuses
        END;

    nn <-- count =
        nn := card(entries)
END
```

### 2b. Translation Mode

If translating from a Z specification (`.tex` file):

#### Read the Z Spec

Load and parse the Z specification, identifying:

- Given sets (`\begin{zed}[TYPE1, TYPE2]\end{zed}`)
- Free types (`Status ::= active | inactive`)
- Axiomatic definitions (`\begin{axdef}...\end{axdef}`)
- State schemas (`\begin{schema}{State}...\end{schema}`)
- Init schemas (`\begin{schema}{Init}...\end{schema}`)
- Operations (`\Delta` and `\Xi` schemas)

#### Apply Translation Rules

Use the Z-to-B mapping from `reference/b-machine-patterns.md`:

1. **Given sets** -> `SETS` (deferred sets)
2. **Free types** -> `SETS` (enumerated sets); `ZBOOL` becomes native `BOOL`
3. **Axiomatic definitions** -> `CONSTANTS` + `PROPERTIES`
4. **State schema variables** -> `VARIABLES`
5. **State schema predicates** -> `INVARIANT`
6. **Init schema** -> `INITIALISATION` (convert equalities to assignments)
7. **Operations**:
   - Predicates on unprimed variables -> `PRE`
   - Equalities on primed variables -> assignments (`x' = E` becomes `x := E`)
   - Input variables (`x?`) -> operation parameters
   - Output variables (`x!`) -> return values (`result <-- op_name`)
   - Drop frame conditions (`x' = x`) — implicit in B
   - Parallel updates -> `||` syntax

#### Translation Examples

**Z given set:**

```latex
\begin{zed}[USERID]\end{zed}
```

**B:**

```b
SETS
    USERID
```

**Z free type:**

```latex
\begin{zed}
ZBOOL ::= ztrue | zfalse
\end{zed}
```

**B:** Drop entirely — use native `BOOL` with `TRUE`/`FALSE`.

**Z state schema:**

```latex
\begin{schema}{State}
users : USERID \pfun \nat \\
count : \nat
\where
count = \# users \\
count \leq 1000
\end{schema}
```

**B:**

```b
VARIABLES
    users, count

INVARIANT
    users : USERID +-> NAT &
    count : NAT &
    count = card(users) &
    count <= 1000
```

**Z operation:**

```latex
\begin{schema}{AddUser}
\Delta State \\
id? : USERID \\
age? : \nat
\where
id? \notin \dom users \\
count < 1000 \\
users' = users \cup \{ id? \mapsto age? \} \\
count' = count + 1
\end{schema}
```

**B:**

```b
add_user(id, age) =
    PRE id : USERID & age : NAT &
        id /: dom(users) &
        count < 1000
    THEN
        users := users \/ {id |-> age} ||
        count := count + 1
    END
```

**Z query (Xi operation):**

```latex
\begin{schema}{GetCount}
\Xi State \\
result! : \nat
\where
result! = count
\end{schema}
```

**B:**

```b
result <-- get_count =
    result := count
```

### 3. Write the File

Save to `specs/<machine_name>.mch` where `<machine_name>` is derived from:

- The system name in the description
- The Z spec filename (without `.tex`)

### 4. Type-Check with probcli

```bash
probcli specs/<machine_name>.mch
```

If errors occur:

- Fix syntax and type errors iteratively
- Common issues: missing PROPERTIES clause, wrong operator syntax, clause ordering

### 5. Verify Initialization

```bash
probcli specs/<machine_name>.mch -init
```

Verify the machine can reach a valid initial state.

### 6. Report Results

Summarize:

- Machine name and file path
- SETS defined (deferred and enumerated)
- VARIABLES and their types
- OPERATIONS defined
- Key invariants
- Any translation decisions made (for translation mode)
- Suggest next: `/z-spec:b-check` then `/z-spec:b-animate`

## Key Principles

1. **Substitutions, not predicates**: B operations use assignments, not equalities
2. **Implicit framing**: Unmentioned variables are unchanged (no need for `x' = x`)
3. **PRE guards everything**: All preconditions go in the PRE clause
4. **Parallel for independence**: Use `||` for simultaneous independent assignments
5. **Bounded for animation**: Add bounds to deferred set sizes for model checking

## Reference

Consult the reference files for:

- B notation syntax: `reference/b-notation.md`
- B machine patterns: `reference/b-machine-patterns.md`
- Z-to-B translation: `reference/b-machine-patterns.md` (Translation section)
- probcli options: `reference/probcli-guide.md`
