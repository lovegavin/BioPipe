# src/orchestration/runner.py
"""Runner — drives steps of a pipeline in order.

The runner is intentionally tiny: it iterates over the pipeline's step
list, times each step, enforces declared dependencies, and records
timings into ``ctx.metadata``. It knows nothing about GWAS or any
specific domain.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from src.core.errors import PipelineError
from src.orchestration.step import Step

if TYPE_CHECKING:  # pragma: no cover
    from src.orchestration.context import PipelineContext


def run_pipeline(steps: list[Step], ctx: "PipelineContext") -> None:
    """Run a list of steps in order against a single context.

    Parameters
    ----------
    steps : list of Step
        Ordered steps to execute.
    ctx : PipelineContext
        Shared context, mutated by each step.

    Raises
    ------
    PipelineError
        If a step's declared inputs are missing, or a step fails.
    """
    total = len(steps)
    ctx.logger.info("Pipeline start: %d steps", total)

    for i, step in enumerate(steps, start=1):
        ctx.logger.info("[%d/%d] %s", i, total, step.name)

        # Enforce the static dependency contract.
        try:
            step.check_inputs(ctx)
        except KeyError as exc:
            raise PipelineError(
                f"Step '{step.name}' dependency check failed: {exc}"
            ) from exc

        t0 = time.perf_counter()
        try:
            step.run(ctx)
        except Exception as exc:
            raise PipelineError(
                f"Step '{step.name}' failed: {exc}"
            ) from exc
        elapsed = time.perf_counter() - t0

        # Verify the step produced what it declared.
        for form_name in step.produces:
            if not ctx.has(form_name):
                raise PipelineError(
                    f"Step '{step.name}' declared form '{form_name}' "
                    f"but did not register it."
                )

        ctx.record_step(step.name, elapsed)
        ctx.logger.info(
            "[%d/%d] %s done in %.2fs", i, total, step.name, elapsed
        )

    ctx.logger.info("Pipeline finished successfully")