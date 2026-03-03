# Graphviz + xdot Installation (macOS)

ProB (`probcli`) uses Graphviz DOT format for state space visualization. Two tools needed:

## Graphviz (dot renderer)

```bash
brew install graphviz
```

Provides `dot`, `neato`, `fdp`, etc. Used by probcli's `-dot` flag to generate `.dot` files, then rendered with:

```bash
dot -Tpng graph.dot -o graph.png
```

## xdot (interactive DOT viewer)

Replaces the deprecated `dotty` viewer. Opens `.dot` files directly — no render step needed.

```bash
brew install pipx
pipx install xdot
```

Do **not** use `uv tool install xdot` — PyGObject requires Homebrew's native GLib/GTK shared libraries at runtime, and uv's isolated venvs can't find them. pipx uses Homebrew's Python, so the dylibs resolve correctly.

### Prerequisites

```bash
brew install pkg-config cairo gtk+3 gobject-introspection py3cairo pygobject3
```

Most of these come in as transitive deps of `graphviz` and `gtk+3`, but `pkg-config`, `gobject-introspection`, `py3cairo`, and `pygobject3` may need explicit install.

## Usage with ProB

```bash
# State space graph
probcli model.tex -model_check -dot state_space graph.dot

# Current state
probcli model.tex -init -dot current_state state.dot

# Operation enable/disable graph
probcli model.tex -dot enable_graph enables.dot

# View interactively
xdot graph.dot
```
