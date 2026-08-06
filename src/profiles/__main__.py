"""ProFiles entry point for ``python -m profiles`` execution.

Enables running the application directly as a module::

    python -m profiles

Stdlib ships a single-file ``profiles`` module (the profiler) that
shadows our package. This shim reorders ``sys.path`` to put the
package's source directory first, then reimports.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from profiles.app import main

_loaded = importlib.import_module("profiles")
if not hasattr(_loaded, "__path__"):
    here = str(Path(__file__).resolve().parent.parent)
    sys.path[:] = [here] + [p for p in sys.path if p != here]
    for name in list(sys.modules):
        if name == "profiles" or name.startswith("profiles."):
            del sys.modules[name]
    # Reimport after path fix
    from profiles.app import main as _main

    main = _main

main()
