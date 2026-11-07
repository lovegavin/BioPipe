"""Operon SDK v3: stable imports for operators and readers.

Implementations remain in the engine for compatibility with existing projects.
Lazy exports keep plugin discovery independent of engine import order.
"""
from importlib import import_module

__version__ = "3.7.0"
from .protocol import PROTOCOL_VERSION
_EXPORTS = {
    "publication_style": ("operon_sdk.figures", "publication_style"),
    "register_figure": ("operon_sdk.figures", "register_figure"),
    "figure_collection": ("operon_sdk.figures", "figure_collection"),
    "save_matplotlib": ("operon_sdk.figures", "save_matplotlib"),
    "run_r": ("operon.r_runtime", "run_r"),
    "load_class": ("operon_sdk.declarations", "load_class"),
    "bind_class": ("operon_sdk.declarations", "bind_class"),
    "Form": ("src.core", "Form"),
    "NativeArray": ("operon_sdk.native_array", "NativeArray"),
    "FileArtifact": ("src.core", "FileArtifact"),
    "Step": ("src.task.step.base", "Step"),
    "Reader": ("src.reader.base", "Reader"),
    "DenseDiskWriter": ("src.reader.disk", "DenseDiskWriter"),
    "StreamInput": ("operon_sdk.resources", "StreamInput"),
    "SourceProbe": ("operon_sdk.resources", "SourceProbe"),
    "Operator": ("operon_sdk.operator", "Operator"),
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
