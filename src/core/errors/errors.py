# src/core/errors/errors.py
"""Exception hierarchy."""

from __future__ import annotations


class OperonError(Exception):
    """Base class for all Operon errors."""


class ValidationError(OperonError):
    """A Form fails its structural check."""


class ReaderError(OperonError):
    """A reader cannot parse the file or the spec."""


class ManifestError(OperonError):
    """The task manifest is malformed."""


class ContextError(OperonError):
    """A form referenced in the context is missing."""


class StepError(OperonError):
    """A step fails its input or execution check."""