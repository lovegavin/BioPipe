# src/core/errors/__init__.py
"""Exception hierarchy for BioPipe.

All BioPipe exceptions inherit from :class:`BioPipeError`, allowing callers
to catch the entire family with a single ``except BioPipeError`` clause.

Design principles
-----------------
* Each exception carries enough context to be actionable.
* Error messages must state *what was expected* and *what was received*.
* No silent fallbacks: raise early, raise loudly.
"""

from __future__ import annotations


class BioPipeError(Exception):
    """Base class for all BioPipe-specific exceptions."""


class ReaderFormatError(BioPipeError):
    """Raised when a file cannot be mapped to a supported format.

    Typically triggered by an unknown extension or an unsupported
    compression combination.
    """


class ReaderSchemaError(BioPipeError):
    """Raised when a file's column layout violates the reader contract.

    Carries ``path``, ``expected`` and ``actual`` so the user can fix the
    input without consulting the documentation.
    """

    def __init__(
        self,
        path: str,
        expected: list[str] | str,
        actual: list[str] | str,
        hint: str | None = None,
    ) -> None:
        self.path = path
        self.expected = expected
        self.actual = actual
        self.hint = hint

        expected_str = expected if isinstance(expected, str) else ", ".join(expected)
        actual_str = actual if isinstance(actual, str) else ", ".join(actual)

        message = (
            f"Schema mismatch in '{path}'\n"
            f"  Expected: {expected_str}\n"
            f"  Actual:   {actual_str}"
        )
        if hint:
            message += f"\n  Hint:     {hint}"
        super().__init__(message)


class ValidationError(BioPipeError):
    """Raised when an in-memory form fails its ``validate()`` check."""

    def __init__(self, form_name: str, rule: str, detail: str = "") -> None:
        self.form_name = form_name
        self.rule = rule
        self.detail = detail

        message = f"{form_name} failed validation: {rule}"
        if detail:
            message += f"\n  Detail: {detail}"
        super().__init__(message)


class PipelineError(BioPipeError):
    """Raised for pipeline orchestration failures."""


__all__ = [
    "BioPipeError",
    "ReaderFormatError",
    "ReaderSchemaError",
    "ValidationError",
    "PipelineError",
]