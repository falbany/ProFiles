"""ProFiles entry point for ``python -m profiles`` execution.

Enables running the application directly as a module::

    python -m profiles

Stdlib ships a single-file ``profiles`` module (the profiler) that
shadows our package. This shim reorders ``sys.path`` to put the
package's source directory first, then reimports.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Force the correct profiles package to be loaded first
here = str(Path(__file__).resolve().parent.parent)
sys.path[:] = [here] + [p for p in sys.path if p != here]

# Clear any previously loaded profiles modules
for name in list(sys.modules):
    if name == "profiles" or name.startswith("profiles."):
        del sys.modules[name]

# Now import from the correct location
from profiles.app import main  # noqa: E402

main()
