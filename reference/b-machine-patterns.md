# B Machine Patterns

Common patterns for B Abstract Machine Notation. Each pattern shows a complete,
probcli-ready machine.

## Counter Machine

The simplest stateful machine: a bounded integer counter.

```b
MACHINE Counter(max)
CONSTRAINTS
    max : NAT1 &
    max <= 1000

VARIABLES
    count

INVARIANT
    count : NAT &
    count <= max

INITIALISATION
    count := 0

OPERATIONS
    increment =
        PRE count < max
        THEN count := count + 1
        END;

    decrement =
        PRE count > 0
        THEN count := count - 1
        END;

    reset =
        count := 0;

    cc <-- get_count =
        cc := count
END
```

## Registry Machine

A partial function from keys to values with bounded capacity.

```b
MACHINE Registry(capacity)
CONSTRAINTS
    capacity : NAT1 &
    capacity <= 100

SETS
    ID;
    STATUS = {active, inactive}

VARIABLES
    entries,
    statuses

INVARIANT
    entries : ID +-> NAT &
    statuses : ID +-> STATUS &
    dom(entries) = dom(statuses) &
    card(entries) <= capacity

INITIALISATION
    entries := {} ||
    statuses := {}

OPERATIONS
    register(id, val) =
        PRE id : ID &
            val : NAT &
            id /: dom(entries) &
            card(entries) < capacity
        THEN
            entries := entries \/ {id |-> val} ||
            statuses := statuses \/ {id |-> active}
        END;

    deregister(id) =
        PRE id : ID & id : dom(entries)
        THEN
            entries := {id} <<| entries ||
            statuses := {id} <<| statuses
        END;

    update(id, val) =
        PRE id : ID & val : NAT & id : dom(entries)
        THEN
            entries := entries <+ {id |-> val}
        END;

    set_status(id, ss) =
        PRE id : ID & ss : STATUS & id : dom(entries)
        THEN
            statuses := statuses <+ {id |-> ss}
        END;

    vv <-- lookup(id) =
        PRE id : ID & id : dom(entries)
        THEN
            vv := entries(id)
        END;

    nn <-- size =
        nn := card(entries)
END
```

## Queue Machine

A FIFO queue using B sequences.

```b
MACHINE Queue(max_size)
CONSTRAINTS
    max_size : NAT1 &
    max_size <= 50

SETS
    ITEM

VARIABLES
    queue

INVARIANT
    queue : seq(ITEM) &
    size(queue) <= max_size

INITIALISATION
    queue := <>

OPERATIONS
    enqueue(item) =
        PRE item : ITEM & size(queue) < max_size
        THEN queue := queue <- item
        END;

    item <-- dequeue =
        PRE size(queue) > 0
        THEN
            item := first(queue) ||
            queue := tail(queue)
        END;

    item <-- peek =
        PRE size(queue) > 0
        THEN item := first(queue)
        END;

    bb <-- is_empty =
        bb := bool(size(queue) = 0);

    nn <-- length =
        nn := size(queue)
END
```

## State Machine Pattern

Model a finite-state machine with guarded transitions.

```b
MACHINE TrafficLight
SETS
    LIGHT = {red, yellow, green}

VARIABLES
    current

INVARIANT
    current : LIGHT

INITIALISATION
    current := red

OPERATIONS
    go_green =
        PRE current = red
        THEN current := green
        END;

    go_yellow =
        PRE current = green
        THEN current := yellow
        END;

    go_red =
        PRE current = yellow
        THEN current := red
        END
END
```

## Refinement Pattern

Refine the Counter machine to use a bounded array-like representation.

### Abstract Machine

```b
MACHINE AbstractCounter
VARIABLES
    count

INVARIANT
    count : NAT &
    count <= 100

INITIALISATION
    count := 0

OPERATIONS
    increment =
        PRE count < 100
        THEN count := count + 1
        END;

    cc <-- get_count =
        cc := count
END
```

### Refinement

```b
REFINEMENT ConcreteCounter
REFINES AbstractCounter

VARIABLES
    tally

INVARIANT
    /* Gluing invariant: concrete tally equals abstract count */
    tally : NAT &
    tally <= 100 &
    tally = count

INITIALISATION
    tally := 0

OPERATIONS
    increment =
        PRE tally < 100
        THEN tally := tally + 1
        END;

    cc <-- get_count =
        cc := tally
END
```

## Z-to-B Translation Table

Quick reference for translating Z specifications to B machines.

### Structural Mapping

| Z Construct | B Equivalent |
|------------|-------------|
| `\begin{zed}[ID]\end{zed}` (given set) | `SETS ID` (deferred set) |
| `Status ::= active \| inactive` (free type) | `SETS STATUS = {active, inactive}` |
| `\begin{axdef} max : \nat \where max = 100 \end{axdef}` | `CONSTANTS max PROPERTIES max : NAT & max = 100` |
| `\begin{schema}{State} ... \where ... \end{schema}` | `VARIABLES ... INVARIANT ...` |
| `\begin{schema}{Init} State' \where ... \end{schema}` | `INITIALISATION ...` |
| `\begin{schema}{Op} \Delta State \\ x? : T \where ... \end{schema}` | `OPERATIONS op(x) = PRE ... THEN ... END` |
| `\begin{schema}{Query} \Xi State \\ y! : T \where ... \end{schema}` | `OPERATIONS y <-- query = ...` |

### Type Mapping

| Z Type | B Type |
|--------|--------|
| `\nat` | `NAT` |
| `\nat_1` | `NAT1` |
| `\num` | `INT` |
| `\power S` | `POW(S)` |
| `S \pfun T` | `S +-> T` |
| `S \fun T` | `S --> T` |
| `S \pinj T` | `S >+> T` |
| `S \inj T` | `S >-> T` |
| `\seq S` | `seq(S)` |
| `S \rel T` | `S <-> T` |
| `S \cross T` | `S * T` |
| `a \mapsto b` | `a \|-> b` |
| `\emptyset` | `{}` |
| `S \cup T` | `S \/ T` |
| `S \cap T` | `S /\ T` |
| `S \setminus T` | `S - T` |
| `\dom R` | `dom(R)` |
| `\ran R` | `ran(R)` |
| `S \dres R` | `S <\| R` |
| `S \ndres R` | `S <<\| R` |
| `R \oplus S` | `R <+ S` |
| `\# S` | `card(S)` |
| `x \in S` | `x : S` |
| `x \notin S` | `x /: S` |
| `S \subseteq T` | `S <: T` |

### Predicate Mapping

| Z Predicate | B Predicate |
|------------|-------------|
| `P \land Q` | `P & Q` |
| `P \lor Q` | `P or Q` |
| `\lnot P` | `not(P)` |
| `P \implies Q` | `P => Q` |
| `\forall x : S \bullet P` | `!x.(x : S => P)` |
| `\exists x : S \bullet P` | `#x.(x : S & P)` |

### Operation Translation

Z operations use declarative predicates; B operations use substitutions.

**Z (declarative):**

```latex
\begin{schema}{Increment}
\Delta State
\where
count < max \\
count' = count + 1
\end{schema}
```

**B (substitution):**

```b
increment =
    PRE count < max
    THEN count := count + 1
    END
```

Key translation rules:

1. **Preconditions** (predicates on unprimed variables) go into `PRE ... THEN`
2. **Effects** (equalities on primed variables) become assignments: `x' = E` becomes `x := E`
3. **Frame conditions** (`x' = x`) are implicit in B (unmentioned variables don't change)
4. **Input variables** (`x?`) become operation parameters: `x? : T` becomes `op(x)`
5. **Output variables** (`x!`) become return values: `x! : T` becomes `x <-- op`
6. **Xi operations** (no state change) use only output assignments
7. **Parallel updates** use `||`: `x' = a /\ y' = b` becomes `x := a || y := b`
8. **ZBOOL** maps to B's native `BOOL` with `TRUE`/`FALSE`

### Translation Checklist

When converting a Z spec (`.tex`) to a B machine (`.mch`):

1. Map given sets to `SETS` (deferred sets)
2. Map free types to `SETS` (enumerated sets); `ZBOOL` becomes native `BOOL`
3. Map axiomatic definitions to `CONSTANTS` + `PROPERTIES`
4. Collect all state schema variables into `VARIABLES`
5. Combine all state schema predicates into `INVARIANT`
6. Convert `Init` schema to `INITIALISATION` substitutions
7. Convert each operation: extract preconditions, translate effects to assignments
8. For operations with outputs, use `result <-- op_name(inputs)` syntax
9. Drop explicit frame conditions (implicit in B)
10. Verify with `probcli Machine.mch -init`
