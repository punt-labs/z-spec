---
paths:
  - '**/*.tex'
  - examples/**
---
# Z conventions (ProB-compatible) — do not "modernize"

- `\quad~` for continuation lines inside `\begin{zed}`; fuzz has no `\t1`.
- `ZBOOL ::= ztrue | zfalse`, not a native Bool.
- Two-letter lowercase free-type prefixes to avoid B keyword conflicts.
- Flat schemas; bounded integers so ProB can animate.
