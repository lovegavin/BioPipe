"""Non-metric multidimensional scaling (NMDS).

NMDS finds a low-dimensional configuration whose rank order of inter-point
distances best matches the observed dissimilarities.  The implementation uses
scikit-learn's SMACOF solver with a deterministic classical-MDS start.  Stress
is reported as raw Kruskal stress and as stress-1 (normalised by the observed
squared distances).
"""
from __future__ import annotations

import inspect
import math

import numpy as np
from sklearn.manifold import MDS

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import distance


class NmdsStep(Step):
    """Non-metric multidimensional scaling from a dissimilarity matrix."""

    name = "nmds"
    title = "Non-metric multidimensional scaling"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["scikit-learn>=1.3", "numpy>=1.26"]
    dependency_imports = ["sklearn", "numpy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(
            ndim=2,
            dims=[param("sample_dim", "sample"), param("sample_b_dim", "sample_b")],
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
            "sample_b_dim": {"type": "string", "default": "sample_b"},
            "n_components": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "default": 2,
            },
            "max_iter": {
                "type": "integer",
                "minimum": 10,
                "maximum": 10000,
                "default": 300,
            },
            "eps": {
                "type": "number",
                "exclusiveMinimum": 0,
                "maximum": 1,
                "default": 1e-9,
            },
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        sample_b_dim = ctx.step_params.get("sample_b_dim", "sample_b")
        D, samples = distance(form, sample_dim, sample_b_dim, self.name)
        n = len(samples)
        if n < 3:
            raise StepError(f"{self.name}: at least three samples are required")
        if not np.allclose(np.diag(D), 0.0, atol=1e-12):
            raise StepError(f"{self.name}: distance matrix diagonal must be zero")
        if np.any(D < 0):
            raise StepError(f"{self.name}: distances must be nonnegative")
        if not np.any(D > 0):
            raise StepError(f"{self.name}: distance matrix must contain positive distances")

        components = int(ctx.step_params.get("n_components", 2))
        if components >= n:
            raise StepError(
                f"{self.name}: n_components ({components}) must be smaller than "
                f"the number of samples ({n})"
            )
        max_iter = int(ctx.step_params.get("max_iter", 300))
        eps = float(ctx.step_params.get("eps", 1e-9))
        if eps <= 0:
            raise StepError(f"{self.name}: eps must be positive")

        parameters = inspect.signature(MDS.__init__).parameters
        kwargs = {
            "n_components": components,
            "init": "classical_mds",
            "n_init": 1,
            "max_iter": max_iter,
            "eps": eps,
            "normalized_stress": False,
            "random_state": 0,
        }
        if "metric_mds" in parameters:
            kwargs["metric_mds"] = False
            kwargs["metric"] = "precomputed"
        else:  # pragma: no cover - older scikit-learn
            kwargs["metric"] = False
            kwargs["dissimilarity"] = "precomputed"

        model = MDS(**kwargs).fit(D)
        coords = np.asarray(model.embedding_, dtype=np.float64)
        if coords.shape != (n, components) or not np.isfinite(coords).all():
            raise StepError(f"{self.name}: NMDS produced an invalid embedding")

        # Rotations/reflections are arbitrary; fix each axis sign deterministically
        # so repeated runs on the same input produce the same table.
        for axis in range(components):
            anchor = int(np.argmax(np.abs(coords[:, axis])))
            if coords[anchor, axis] < 0:
                coords[:, axis] *= -1.0

        stress = max(0.0, float(model.stress_))
        total = float(np.sum(D * D))
        stress1 = math.sqrt(stress / total) if total > 0 else float("nan")
        if not math.isfinite(stress1):
            raise StepError(f"{self.name}: could not compute finite stress")

        out = Form(
            data=coords,
            dims=[sample_dim, "component"],
            labels={
                sample_dim: {name: index for index, name in enumerate(samples)},
                "component": {
                    f"NMDS{index + 1}": index for index in range(components)
                },
            },
            info={
                "method": "nmds",
                "metric": False,
                "init": "classical_mds",
                "n": int(n),
                "n_components": int(components),
                "n_iter": int(model.n_iter_),
                "stress": stress,
                "stress1": stress1,
                "stress_percent": 100.0 * stress1,
                "max_iter": max_iter,
                "eps": eps,
            },
        )
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export = {
            "samples": samples,
            "coordinates": coords.tolist(),
            "stress": stress,
            "stress1": stress1,
            "stress_percent": 100.0 * stress1,
            "n": int(n),
            "n_components": int(components),
            "n_iter": int(model.n_iter_),
        }
        print(f"[{self.name}] n={n}, components={components}, stress1={stress1:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
