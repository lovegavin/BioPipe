"""Approximate entropy (ApEn), matching R pracma::approx_entropy."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._entropy69_common import default_radius, numeric_series
from ._stats20_common import scalar_form


class ApproxEntropyStep(Step):
    """Approximate entropy for a univariate series.

    ``ApEn(m, r) = phi(m) - phi(m+1)`` where ``phi(m)`` is the mean log
    fraction of embedded vectors within Chebyshev distance ``r``
    (including the vector itself).  With the defaults this is the same
    quantity reported by R ``pracma::approx_entropy``.
    """

    name = "approx_entropy"
    title = "Approximate entropy"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.24"]
    dependency_imports = ["numpy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "value_label": {"type": "string", "title": "数值字段"},
            "embedding_dim": {"type": "integer", "default": 2, "minimum": 1, "maximum": 5},
            "radius": {"type": "number", "exclusiveMinimum": 0},
            "output": {"type": "string"},
        },
        "required": ["value_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        values = numeric_series(
            inputs[0],
            ctx.step_params.get("sample_dim", "sample"),
            ctx.step_params.get("feature_dim", "feature"),
            ctx.step_params["value_label"],
            "approx_entropy",
        )
        m = int(ctx.step_params.get("embedding_dim", 2))
        radius = ctx.step_params.get("radius")
        r = float(radius) if radius is not None else default_radius(values)
        if not np.isfinite(r) or r <= 0:
            raise StepError("approx_entropy: radius must be positive")
        n = int(values.size)
        if n <= m + 2:
            raise StepError("approx_entropy: series is too short for the embedding dimension")
        if n > 2000:
            raise StepError("approx_entropy: at most 2000 finite values are supported")

        def phi(dim: int) -> float:
            embedded = np.lib.stride_tricks.sliding_window_view(values, dim)
            similarities = np.max(np.abs(embedded - embedded[:, None, :]), axis=2)
            fractions = np.mean(similarities <= r, axis=1)
            if np.any(fractions <= 0):
                raise StepError("approx_entropy: no template matches at this radius")
            return float(np.mean(np.log(fractions)))

        apen = phi(m) - phi(m + 1)
        out = scalar_form([apen, float(m), r, float(n)], ["approx_entropy", "embedding_dim", "radius", "n"], "approx_entropy")
        out.info.update({"method": "approximate entropy", "matching": "Chebyshev", "self_matches": True})
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export_data = {"approx_entropy": apen, "embedding_dim": m, "radius": r, "n": n}
        print(f"[approx_entropy] ApEn={apen:.8f}, m={m}, r={r:.6g}, n={n}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
