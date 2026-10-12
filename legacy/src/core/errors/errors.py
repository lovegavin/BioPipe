# src/core/errors/errors.py
"""Exception hierarchy."""

from __future__ import annotations


class BioPipeError(Exception):
    """Base class for all BioPipe errors."""


class ValidationError(BioPipeError):
    """A Form fails its structural check."""


class ReaderError(BioPipeError):
    """A reader cannot parse the file or the spec."""


class ManifestError(BioPipeError):
    """The task manifest is malformed."""


class ContextError(BioPipeError):
    """A form referenced in the context is missing."""


class StepError(BioPipeError):
    """A step fails its input or execution check."""