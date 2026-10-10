# src/task/step/base.py
"""Step abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from src.core import Form
from src.task.context import Context


class Step(ABC):
    """Abstract step.

    Subclasses declare:

    * ``name`` — matched against the manifest's ``name`` field.
    * ``inputs_arity`` — number of input forms, or ``"*"`` for any.
    * ``outputs`` — context keys the step registers on exit.

    And implement ``run``. They may also implement ``export`` to
    return a JSON-serializable dict of the step's full results.
    """

    name: ClassVar[str] = "unnamed"
    inputs_arity: ClassVar[int | str] = 0
    outputs: ClassVar[list[str]] = []

    @abstractmethod
    def run(self, ctx: Context, inputs: list[Form]) -> None:
        """Execute the step."""

    def export(self, ctx: Context) -> dict:
        """Return a JSON-serializable summary of this step's results.

        Called by the runner right after run(). The default returns
        an empty dict. Subclasses return everything a user would want
        to see. Do not truncate.
        """
        return {}