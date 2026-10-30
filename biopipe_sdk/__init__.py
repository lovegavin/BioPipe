"""BioPipe SDK v3: stable imports for operators and readers.

Implementations remain in the engine for compatibility with existing projects.
Lazy exports keep plugin discovery independent of engine import order.
"""
from importlib import import_module

__version__ = "3.0.0"
from .protocol import PROTOCOL_VERSION
_EXPORTS = {
    "publication_style": ("biopipe_sdk.figures", "publication_style"),
    "register_figure": ("biopipe_sdk.figures", "register_figure"),
    "figure_collection": ("biopipe_sdk.figures", "figure_collection"),
    "save_matplotlib": ("biopipe_sdk.figures", "save_matplotlib"),
    "run_r": ("biopipe.r_runtime", "run_r"),
    "load_class": ("biopipe_sdk.declarations", "load_class"),
    "bind_class": ("biopipe_sdk.declarations", "bind_class"),
    "Form": ("src.core", "Form"),
    "FileArtifact": ("src.core", "FileArtifact"),
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
