from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path

_PYW_PATH = Path(__file__).with_name("ProFiles.pyw")
# ``.pyw`` is only registered as a source suffix on Windows; passing an
# explicit loader keeps the launcher module loadable on every OS.
_LOADER = importlib.machinery.SourceFileLoader("_pro_files_launcher", str(_PYW_PATH))
_SPEC = importlib.util.spec_from_loader(_LOADER.name, _LOADER, origin=str(_PYW_PATH))
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Unable to load launcher module from {_PYW_PATH}")

_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

for _name in dir(_MODULE):
    if _name.startswith("__") and _name not in {
        "__annotations__",
        "__builtins__",
        "__doc__",
        "__file__",
        "__loader__",
        "__name__",
        "__package__",
        "__spec__",
    }:
        continue
    if not _name.startswith("__"):
        globals()[_name] = getattr(_MODULE, _name)

__all__ = [name for name in globals() if not name.startswith("_") and name != "__builtins__"]

if __name__ == "__main__":
    _MODULE._relaunch_in_venv()
