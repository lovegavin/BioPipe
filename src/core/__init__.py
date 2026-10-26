# src/core/__init__.py
"""Core kernel: forms and errors."""

from src.core.errors import (
    BioPipeError,
    ContextError,
    ManifestError,
    ReaderError,
    StepError,
    ValidationError,
)
def __getattr__(name):
    if name != "Form":
        raise AttributeError(name)
    from src.core.forms import Form
    globals()[name] = Form
    return Form

__all__ = [
    "BioPipeError",
    "ContextError",
    "ManifestError",
    "ReaderError",
    "StepError",
    "ValidationError",
    "Form",
]