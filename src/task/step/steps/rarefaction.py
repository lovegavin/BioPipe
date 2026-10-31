"""Expected species richness by individual-based rarefaction."""
from __future__ import annotations

import numpy as np
from scipy.special import gammaln

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._multivariate35_common import frame_matrix


def _expected_richness(counts: np.ndarray, depth: int) -> float:
    total = float(counts.sum())
    if total <= 0:
        return 0.0
    expected = 0.0
    for count in counts:
        n = float(count)
        if n <= 0:
            continue
        remaining = total - n
        if remaining < depth:
            # Not enough other individuals to fill the subsample without
            # this species, so it is always observed.
            expected += 1.0
            continue
        log_probability = (
            gammaln(remaining + 1.0)
            - gammaln(remaining - depth + 1.0)
            - gammaln(total + 1.0)
            + gammaln(total - depth + 1.0)
        )
        expected += 1.0 - float(np.exp(log_probability))
    return expected


class RarefactionStep(Step):
    """Expected species richness at a fixed number of individuals."""

    name = "rarefaction"
    title = "Individual-based rarefaction"
    category = "Omics"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.26", "scipy>=1.11"]
    dependency_imports = ["numpy", "scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(
            ndim=2,
            dims=[param("sample_dim", "sample"), param("feature_dim", "feature")],
        )
    ]
    output_contract = {
        "mode": "declare",
        "schema": {
            "ndim": 2,
            "numeric": True,
            "info_open": True,
            "axis_info_open": True,
        },
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "depth": {"type": "integer", "minimum": 1},
            "output": {"type": "string"},
        },
        "required": ["depth"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        depth = ctx.step_params.get("depth")
        if not isinstance(depth, int) or isinstance(depth, bool) or depth < 1:
            raise StepError("rarefaction: depth must be a positive integer")

        samples, features, matrix = frame_matrix(
            inputs[0], sample_dim, feature_dim, self.name
        )
        if matrix.shape[0] == 0:
            raise StepError("rarefaction: input has no samples")
        if not np.isfinite(matrix).all():
            raise StepError("rarefaction: counts must be finite")
        if (matrix < 0).any():
            raise StepError("rarefaction: counts must be non-negative")
        if not np.allclose(matrix, np.floor(matrix)):
            raise StepError("rarefaction: counts must be integers")

        totals = matrix.sum(axis=1)
        too_small = [samples[i] for i, total in enumerate(totals) if total < depth]
        if too_small:
            raise StepError(
                "rarefaction: depth exceeds total counts for sample(s): "
                + ", ".join(too_small)
            )

        values = np.asarray(
            [_expected_richness(row, depth) for row in matrix],
            dtype=np.float64,
        )
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=values.reshape(-1, 1).astype(np.float32),
            dims=["sample", "feature"],
            labels={
                "sample": {name: i for i, name in enumerate(samples)},
                "feature": {"rarefied": 0},
            },
            info={
                "method": "rarefaction",
                "depth": depth,
                "n_samples": len(samples),
                "n_features": len(features),
            },
        )
        self._export = {
            "samples": samples,
            "features": features,
            "depth": depth,
            "rarefied": values.tolist(),
            "n": totals.astype(int).tolist(),
        }
        print(f"[{self.name}] samples={len(samples)}, depth={depth}")

    def export(self, ctx: Context) -> dict:
        return self._export
