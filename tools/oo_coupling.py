"""Entry point for the module coupling/cohesion scorer and regression ratchet.

Run as ``python tools/oo_coupling.py <src> [flags]`` — the invocation the
Makefile and CI use. Python puts this script's directory (``tools/``) on
``sys.path``, so it imports the sibling ``coupling`` package directly
(``from coupling.cli import main``). For programmatic use, with the repo root on
the path, import the package as ``tools.coupling`` (this is how tests import it).
"""

from __future__ import annotations

import sys

from coupling.cli import main

if __name__ == "__main__":
    sys.exit(main())
