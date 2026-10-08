# src/orchestration/step.py
"""Step and LoopStep — the atomic unit of pipeline execution.

A ``Step`` runs once. A ``LoopStep`` runs an inner loop (used by
training routines in ML pipelines). Both declare what forms they
consume and produce, enabling static dependency checks.

Steps are stateless with respect to the pipeline: all mutable state
lives in the ``PipelineContext``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from src.orchestration.context import PipelineContext


class Step:
    """A single, non-iterative pipeline step.

    Subclasses must set ``name``, ``consumes`` and ``produces``, and
    implement :meth:`run`.

    Attributes
    ----------
    name : str
        Human-readable step name, used in logs and metadata.
    consumes : tuple[str, ...]
        Form names that must be present before this step runs.
    produces : tuple[str, ...]
        Form names this step is expected to register in the context.
    """

    name: str = "unnamed"
    consumes: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()

    def run(self, ctx: "PipelineContext") -> None:
        """Execute the step. Must be overridden."""
        raise NotImplementedError

    def check_inputs(self, ctx: "PipelineContext") -> None:
        """Fail early if a consumed form is missing."""
        for form_name in self.consumes:
            if not ctx.has(form_name):
                raise KeyError(
                    f"Step '{self.name}' requires form '{form_name}' "
                    f"but it is not present in the context."
                )


class LoopStep(Step):
    """A step that runs an inner loop.

    Reserved for ML/DL pipelines (training loops, cross-validation).
    The default implementation raises :class:`NotImplementedError`.
    """

    def setup(self, ctx: "PipelineContext") -> None:
        """Run once before the loop starts."""

    def step(self, ctx: "PipelineContext", iteration: int) -> None:
        """Run one loop iteration. Must be overridden."""
        raise NotImplementedError

    def should_stop(self, ctx: "PipelineContext", iteration: int) -> bool:
        """Return True to terminate the loop. Default: single iteration."""
        return iteration >= 0

    def teardown(self, ctx: "PipelineContext") -> None:
        """Run once after the loop ends."""

    def run(self, ctx: "PipelineContext") -> None:
        """Drive setup -> step* -> teardown."""
        self.setup(ctx)
        i = 0
        while not self.should_stop(ctx, i):
            self.step(ctx, i)
            i += 1
        self.teardown(ctx)