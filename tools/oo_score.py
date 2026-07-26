"""Entry point for the OO scorer and baseline ratchet.

Run as ``python tools/oo_score.py <src> [flags]`` — the invocation the Makefile
and CI use. Python puts this script's directory (``tools/``) on ``sys.path``, so
it imports the sibling ``oo_ratchet`` package directly (``from oo_ratchet.cli
import main``). For programmatic use, with the repo root on the path, import the
package as ``tools.oo_ratchet`` (this is how the tests import it).
"""

from __future__ import annotations

import sys

from oo_ratchet.cli import main

if __name__ == "__main__":
    sys.exit(main())
