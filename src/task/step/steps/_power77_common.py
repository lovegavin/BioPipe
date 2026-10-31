"""Shared validation and output helpers for the 0.77 power operators."""
from __future__ import annotations

import math

import numpy as np

from src.core import Form, StepError


def floating(ctx, name: str, *, default=None, low=None, high=None) -> float:
    raw = ctx.step_params.get(name, default)
    if raw is None:
        raise StepError(f"power: parameter {name!r} is required")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise StepError(f"power: parameter {name!r} must be numeric") from exc
    if not math.isfinite(value):
        raise StepError(f"power: parameter {name!r} must be finite")
    if low is not None and value <= low:
        raise StepError(f"power: parameter {name!r} must be greater than {low}")
    if high is not None and value >= high:
        raise StepError(f"power: parameter {name!r} must be less than {high}")
    return value


def integer(ctx, name: str, *, minimum: int = 2) -> int:
    raw = ctx.step_params.get(name)
    if raw is None:
        raise StepError(f"power: parameter {name!r} is required")
    try:
        numeric = float(raw)
    except (TypeError, ValueError) as exc:
        raise StepError(f"power: parameter {name!r} must be an integer") from exc
    if not math.isfinite(numeric) or not numeric.is_integer():
        raise StepError(f"power: parameter {name!r} must be an integer")
    value = int(numeric)
    if value < minimum:
        raise StepError(f"power: parameter {name!r} must be at least {minimum}")
    return value


def alternative(ctx) -> str:
    value = str(ctx.step_params.get("alternative", "two-sided"))
    if value not in {"two-sided", "greater", "less"}:
        raise StepError("power: alternative must be two-sided, greater, or less")
    return value


def form(rows, info) -> Form:
    names = [name for name, _ in rows]
    data = np.asarray([[float(value)] for _, value in rows], dtype=np.float64)
    result = Form(
        data=data,
        dims=["statistic", "value"],
        labels={
            "statistic": {name: index for index, name in enumerate(names)},
            "value": {"value": 0},
        },
        info={"missing_code": np.nan, **info},
    )
    result.validate()
    return result
