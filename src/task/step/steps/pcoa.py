"""Classical principal coordinates analysis (PCoA)."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import distance


class PcoaStep(Step):
    """Principal coordinates from a symmetric distance matrix."""

    name = "pcoa"
    title = "Principal coordinates analysis"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.26"]
    dependency_imports = ["numpy"]
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
            "n_components": {"type": "integer", "minimum": 1, "default": 2},
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
        if n < 2:
            raise StepError(f"{self.name}: at least two samples are required")
        if not np.allclose(np.diag(D), 0.0, atol=1e-12):
            raise StepError(f"{self.name}: distance matrix diagonal must be zero")
        if np.any(D < 0):
            raise StepError(f"{self.name}: distances must be nonnegative")

        G = -0.5 * D**2
        G = G - G.mean(axis=0, keepdims=True) - G.mean(axis=1, keepdims=True) + G.mean()
        eigvals, eigvecs = np.linalg.eigh(G)
        order = np.argsort(eigvals)[::-1]
        eigvals = eigvals[order]
        eigvecs = eigvecs[:, order]
        scale = max(1.0, float(np.max(np.abs(eigvals))))
        positive = eigvals > scale * 1e-12
        n_positive = int(positive.sum())
        if n_positive < 1:
            raise StepError(f"{self.name}: no positive PCoA eigenvalues")
        requested = int(ctx.step_params.get("n_components", 2))
        components = min(requested, n_positive)
        eigen = eigvals[positive][:components]
        explained = eigvals[positive] / float(eigvals[positive].sum())
        coords = eigvecs[:, positive][:, :components] * np.sqrt(eigen)[None, :]

        out = Form(
            data=coords,
            dims=["sample", "component"],
            labels={
                "sample": {name: index for index, name in enumerate(samples)},
                "component": {
                    f"PC{index + 1}": index for index in range(components)
                },
            },
            info={
                "method": "pcoa",
                "n": int(n),
                "n_components": int(components),
                "eigenvalues": [float(value) for value in eigen],
                "explained": [float(value) for value in explained[:components]],
                "cumulative": [
                    float(value) for value in np.cumsum(explained[:components])
                ],
                "n_positive": n_positive,
                "n_negative": int(np.sum(eigvals < -scale * 1e-12)),
                "n_zero": int(
                    np.sum(np.abs(eigvals) <= scale * 1e-12)
                ),
                "total_positive_inertia": float(eigvals[positive].sum()),
            },
        )
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export = {
            "samples": samples,
            "eigenvalues": [float(value) for value in eigen],
            "explained": [float(value) for value in explained[:components]],
            "cumulative": [
                float(value) for value in np.cumsum(explained[:components])
            ],
            "coordinates": coords.tolist(),
            "n_positive": n_positive,
            "n_negative": int(np.sum(eigvals < -scale * 1e-12)),
        }
        print(f"[{self.name}] n={n}, components={components}")

    def export(self, ctx: Context) -> dict:
        return self._export
