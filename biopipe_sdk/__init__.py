"""BioPipe SDK v1: stable imports for operators and readers.

Implementations remain in the engine for compatibility with existing projects.
Lazy exports keep plugin discovery independent of engine import order.
"""
from importlib import import_module

__version__ = "1.2.0"
PROTOCOL_VERSION = 1
_EXPORTS = {
    "Form": ("src.core", "Form"),
    "Step": ("src.task.step.base", "Step"),
    "Reader": ("src.reader.base", "Reader"),
    "DenseDiskWriter": ("src.reader.disk", "DenseDiskWriter"),
    "StreamInput": ("biopipe_sdk.resources", "StreamInput"),
    "SourceProbe": ("biopipe_sdk.resources", "SourceProbe"),
    "Operator": ("biopipe_sdk.operator", "Operator"),
    "Context": ("src.task.context.base", "Context"),
    "StepError": ("src.core", "StepError"),
    "ReaderError": ("src.core", "ReaderError"),
    "port": ("src.core.contracts", "port"),
    "param": ("src.core.contracts", "param"),
    "MISSING": ("src.core.contracts", "MISSING"),
    "reader_contract": ("src.core.contracts", "reader_contract"),
    "project_metadata": ("src.core.forms.metadata", "project_metadata"),
    "concat_metadata": ("src.core.forms.metadata", "concat_metadata"),
}
__all__ = [*_EXPORTS, "PROTOCOL_VERSION", "__version__"]


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module, attribute = _EXPORTS[name]
    value = getattr(import_module(module), attribute)
    globals()[name] = value
    return value
