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
    * ``outputs`` — names the step registers on exit.

    And implement ``run``.
    """

    name: ClassVar[str] = "unnamed"
    inputs_arity: ClassVar[int | str] = 0
    outputs: ClassVar[list[str]] = []

    @abstractmethod
    def run(self, ctx: Context, inputs: list[Form]) -> None:
        """Execute the step.

        Parameters
        ----------
        ctx : Context
            Read params from ``ctx.step_params``. Write results via
            ``ctx[name] = form``.
        inputs : list[Form]
            Input forms, in manifest order.
        """
        ...