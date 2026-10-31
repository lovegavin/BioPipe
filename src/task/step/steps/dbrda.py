"""Distance-based redundancy analysis (db-RDA)."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import table


def _bray_curtis(y: np.ndarray) -> np.ndarray:
    """Return the Bray-Curtis distance matrix for a site x species table."""
    if np.any(y < 0):
        raise StepError("dbrda: response values must be nonnegative")
    row_sums = y.sum(axis=1)
    if np.any(row_sums <= 0):
        raise StepError("dbrda: every sample needs a positive response sum")
    n = y.shape[0]
    distance = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            denominator = row_sums[i] + row_sums[j]
            if denominator <= 0:
                continue
            value = float(np.abs(y[i] - y[j]).sum() / denominator)
            distance[i, j] = distance[j, i] = value
    return distance


def _euclidean(y: np.ndarray) -> np.ndarray:
    difference = y[:, None, :] - y[None, :, :]
    return np.sqrt(np.sum(difference * difference, axis=2))


def _align(response, predictor, sample_dim, response_dim, predictor_dim):
    y, y_samples, _species = table(
        response, sample_dim, response_dim, "dbrda"
    )
    x, x_samples, _predictors = table(
        predictor, sample_dim, predictor_dim, "dbrda"
    )
    if set(y_samples) != set(x_samples):
        raise StepError("dbrda: response and predictor samples must match")
    x_pos = {name: index for index, name in enumerate(x_samples)}
    x = x[[x_pos[name] for name in y_samples]]
    if y.shape[0] < 3:
        raise StepError("dbrda: need at least three samples")
    if y.shape[1] < 2:
        raise StepError("dbrda: need at least two response features")
    if not np.isfinite(y).all() or not np.isfinite(x).all():
        raise StepError("dbrda: response and predictor values must be finite")
    if x.shape[1] < 1:
        raise StepError("dbrda: at least one predictor is required")
    if y.shape[0] <= x.shape[1]:
        raise StepError("dbrda: need more samples than predictors")
    centered = x - x.mean(axis=0, keepdims=True)
    if np.linalg.matrix_rank(centered) < x.shape[1]:
        raise StepError("dbrda: predictor matrix is rank deficient")
    return y.astype(np.float64), x.astype(np.float64), y_samples


class DbrdaStep(Step):
    """Constrain a PCoA of a distance matrix by explanatory variables."""

    name = "dbrda"
    title = "Distance-based redundancy analysis"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.26"]
    dependency_imports = ["numpy"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(
            ndim=2,
            dims=[param("sample_dim", "sample"), param("response_dim", "feature")],
        ),
        port(
            ndim=2,
            dims=[param("sample_dim", "sample"), param("predictor_dim", "predictor")],
        ),
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
            "response_dim": {"type": "string", "default": "feature"},
            "predictor_dim": {"type": "string", "default": "predictor"},
            "distance": {
                "type": "string",
                "enum": ["bray", "euclidean"],
                "default": "bray",
            },
            "n_components": {"type": "integer", "minimum": 1, "default": 2},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        response, predictor = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        response_dim = ctx.step_params.get("response_dim", "feature")
        predictor_dim = ctx.step_params.get("predictor_dim", "predictor")
        method = ctx.step_params.get("distance", "bray")
        y, x, samples = _align(
            response, predictor, sample_dim, response_dim, predictor_dim
        )

        distance = _bray_curtis(y) if method == "bray" else _euclidean(y)
        if not np.isfinite(distance).all() or np.any(distance < 0):
            raise StepError("dbrda: distance matrix must be finite and nonnegative")

        n = y.shape[0]
        gower = -0.5 * distance * distance
        centering = np.eye(n) - np.ones((n, n), dtype=np.float64) / n
        gower = centering @ gower @ centering
        total_inertia = float(np.linalg.eigvalsh(gower).sum())
        if not np.isfinite(total_inertia) or total_inertia <= 0:
            raise StepError("dbrda: distance matrix has no positive inertia")

        x_centered = x - x.mean(axis=0, keepdims=True)
        q, _ = np.linalg.qr(x_centered, mode="reduced")
        fitted = q @ q.T @ gower @ q @ q.T
        fitted = (fitted + fitted.T) / 2.0
        values = np.linalg.eigvalsh(fitted)[::-1]
        cutoff = max(1e-12, 1e-10 * float(abs(values[0])))
        positive = values[values > cutoff]
        if positive.size == 0:
            raise StepError("dbrda: model has no positive constrained eigenvalue")
        constrained_inertia = float(positive.sum())
        unconstrained_inertia = float(total_inertia - constrained_inertia)
        requested = int(ctx.step_params.get("n_components", 2))
        components = min(requested, positive.size)
        if components < 1:
            raise StepError("dbrda: no constrained components available")
        eigen = positive[:components]
        explained = eigen / total_inertia
        cumulative = np.cumsum(explained)

        output = ctx.step_params.get("output", self.name)
        ctx[output] = Form(
            data=np.column_stack([eigen, explained, cumulative]),
            dims=["component", "statistic"],
            labels={
                "component": {
                    f"dbRDA{index + 1}": index
                    for index in range(components)
                },
                "statistic": {
                    "eigenvalue": 0,
                    "explained": 1,
                    "cumulative": 2,
                },
            },
            info={
                "method": "dbrda",
                "distance": method,
                "n": n,
                "n_features": int(y.shape[1]),
                "n_predictors": int(x.shape[1]),
                "total_inertia": total_inertia,
                "constrained_inertia": constrained_inertia,
                "unconstrained_inertia": unconstrained_inertia,
                "constrained_fraction": constrained_inertia / total_inertia,
                "n_positive_eigenvalues": int(positive.size),
            },
        )
        self._export_data = {
            "method": "dbrda",
            "distance": method,
            "n": n,
            "n_predictors": int(x.shape[1]),
            "total_inertia": total_inertia,
            "constrained_inertia": constrained_inertia,
            "unconstrained_inertia": unconstrained_inertia,
            "constrained_fraction": constrained_inertia / total_inertia,
            "eigenvalues": [float(value) for value in positive],
            "explained": [float(value) for value in positive / total_inertia],
            "cumulative": [float(value) for value in np.cumsum(positive / total_inertia)],
            "samples": samples,
        }
        print(
            f"[dbrda] total={total_inertia:.6g} constrained={constrained_inertia:.6g} "
            f"components={components}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
