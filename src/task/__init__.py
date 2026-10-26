"""Task public API, loaded only when used by an execution worker."""
from importlib import import_module
_EXPORTS = {"Context": "src.task.context", "load_manifest": "src.task.manifest", "run": "src.task.runner", "STEPS": "src.task.step", "Step": "src.task.step"}
__all__ = list(_EXPORTS)
def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    value = getattr(import_module(_EXPORTS[name]), name)
    globals()[name] = value
    return value
