"""Entry point for the suppression counter and ratchet.

Run as ``python tools/suppression_ratchet.py <src> [flags]`` — the invocation the
Makefile and CI use. Python puts this script's directory (``tools/``) on
``sys.path``, so it imports the sibling ``suppression`` package directly
(``from suppression.cli import main``). For programmatic use, with the repo root
on the path, import the package as ``tools.suppression`` (how tests import it).
"""

from __future__ import annotations

import sys

from suppression.cli import main

if __name__ == "__main__":
    sys.exit(main())
