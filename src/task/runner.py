# src/task/runner.py
"""Runner — resolves inputs, executes steps in order."""

from __future__ import annotations

import time

from src.core import ContextError, StepError
from src.task.context import Context
from src.task.step import STEPS


def run(ctx: Context, steps: list[dict]) -> None:
    total = len(steps)
    for i, spec in enumerate(steps, start=1):
        name = spec["name"]
        cls = STEPS.get(name)
        if cls is None:
            raise StepError(
                f"Unknown step '{name}'. Available: {sorted(STEPS)}"
            )
        step = cls()

        form_names = spec.get("inputs", [])
        _check_arity(name, step.inputs_arity, form_names)
        forms = [_resolve(ctx, n, name) for n in form_names]

        # Inject input names so steps that need them (e.g. concat)
        # can look them up by manifest name.
        ctx.step_params = dict(spec.get("params", {}))
        ctx.step_params["_input_names"] = list(form_names)

        t0 = time.perf_counter()
        step.run(ctx, forms)
        elapsed = time.perf_counter() - t0

        for out_name in step.outputs:
            if not ctx.has(out_name):
                raise StepError(
                    f"Step '{name}' declared output '{out_name}' but did "
                    f"not register it in the context."
                )

        ctx.metadata.setdefault("steps", []).append(
            {"name": name, "elapsed": elapsed}
        )
        print(f"[{i}/{total}] {name} done in {elapsed:.3f}s")


def _check_arity(name: str, arity, form_names: list[str]) -> None:
    if arity == "*":
        if not form_names:
            raise StepError(
                f"Step '{name}' accepts any number of inputs but got none"
            )
        return
    if len(form_names) != arity:
        raise StepError(
            f"Step '{name}' expects {arity} inputs, got {len(form_names)}"
        )


def _resolve(ctx: Context, name: str, step_name: str):
    if not ctx.has(name):
        raise ContextError(
            f"Step '{step_name}' requires form '{name}', which is not in "
            f"context. Available: {sorted(ctx.forms)}"
        )
    return ctx[name]