"""Redundancy analysis (RDA) for a response matrix and explanatory table."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._multivariate35_common import frame_matrix


def _align(response, explanatory, sample_dim, response_dim, predictor_dim, label):
    samples_y, names_y, y = frame_matrix(
        response, sample_dim, response_dim, f"{label}: response"
    )
    samples_x, names_x, x = frame_matrix(
        explanatory, sample_dim, predictor_dim, f"{label}: explanatory"
    )
    x_map = {name: index for index, name in enumerate(samples_x)}
    keep = [index for index, name in enumerate(samples_y) if name in x_map]
    if len(keep) < 3:
        raise StepError(f"{label}: fewer than three shared samples")
    y = y[keep]
    x = x[[x_map[samples_y[index]] for index in keep]]
    valid = np.isfinite(x).all(axis=1) & np.isfinite(y).all(axis=1)
    x = x[valid]
    y = y[valid]
    if x.shape[0] < 3:
        raise StepError(f"{label}: fewer than three finite shared samples")
    if x.shape[1] > x.shape[0] or y.shape[1] > y.shape[0]:
        raise StepError(f"{label}: fewer samples than variables")
    if np.linalg.matrix_rank(x) < x.shape[1]:
        raise StepError(f"{label}: explanatory matrix is rank deficient")
    if np.linalg.matrix_rank(y) < y.shape[1]:
        raise StepError(f"{label}: response matrix is rank deficient")
    selected = [samples_y[index] for index in keep]
    samples = [name for name, ok in zip(selected, valid) if ok]
    return samples, names_y, names_x, x.astype(float), y.astype(float)


class RedundancyAnalysisStep(Step):
    """Constrained ordination of a response matrix by explanatory variables."""

    name = "redundancy_analysis"
    title = "Redundancy analysis"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["numpy"]
    dependency_imports = ["numpy"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(
            ndim=2,
            dims=[param("sample_dim", "sample"), param("response_dim", "response")],
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
            "response_dim": {"type": "string", "default": "response"},
            "predictor_dim": {"type": "string", "default": "predictor"},
            "n_components": {"type": "integer", "minimum": 1, "default": 2},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        response_dim = ctx.step_params.get("response_dim", "response")
        predictor_dim = ctx.step_params.get("predictor_dim", "predictor")
        samples, response_names, predictor_names, x, y = _align(
            inputs[0],
            inputs[1],
            sample_dim,
            response_dim,
            predictor_dim,
            self.name,
        )
        n = x.shape[0]
        y_centered = y - y.mean(axis=0, keepdims=True)
        x_centered = x - x.mean(axis=0, keepdims=True)

        coefficients = np.linalg.lstsq(x_centered, y_centered, rcond=None)[0]
        fitted = x_centered @ coefficients
        total_inertia = float(np.sum(y_centered**2) / (n - 1))
        constrained_inertia = float(np.sum(fitted**2) / (n - 1))
        if total_inertia <= 0.0 or constrained_inertia <= 0.0:
            raise StepError(f"{self.name}: response has no finite variance")
        unconstrained_inertia = max(0.0, total_inertia - constrained_inertia)

        u, singular, vt = np.linalg.svd(fitted, full_matrices=False)
        all_eigenvalues = singular**2 / (n - 1)
        rank = int(np.sum(all_eigenvalues > max(1e-12, constrained_inertia * 1e-12)))
        requested = int(ctx.step_params.get("n_components", 2))
        if requested < 1:
            raise StepError(f"{self.name}: n_components must be at least 1")
        n_components = max(1, min(requested, rank, y.shape[1], x.shape[1]))
        eigenvalues = all_eigenvalues[:n_components]
        explained = eigenvalues / total_inertia
        cumulative = np.cumsum(explained)

        rows = [
            [float(eigenvalues[i]), float(explained[i]), float(cumulative[i])]
            for i in range(n_components)
        ]
        names = [f"RDA{i + 1}" for i in range(n_components)]
        site_scores = (u[:, :n_components] * singular[:n_components]).tolist()
        response_scores = vt[:n_components].T.tolist()
        predictor_scores = (
            np.corrcoef(x_centered, site_scores, rowvar=False)[
                : x.shape[1], x.shape[1] :
            ].tolist()
            if n_components
            else []
        )

        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float64),
            dims=["component", "statistic"],
            labels={
                "component": {name: index for index, name in enumerate(names)},
                "statistic": {
                    "eigenvalue": 0,
                    "explained": 1,
                    "cumulative": 2,
                },
            },
            info={
                "method": "RDA",
                "scaling": "sites",
                "n": n,
                "n_response": len(response_names),
                "n_predictor": len(predictor_names),
                "total_inertia": total_inertia,
                "constrained_inertia": constrained_inertia,
                "unconstrained_inertia": unconstrained_inertia,
                "constrained_fraction": constrained_inertia / total_inertia,
                "n_components": n_components,
            },
        )
        self._export = {
            "samples": samples,
            "response_names": response_names,
            "predictor_names": predictor_names,
            "eigenvalues": eigenvalues.tolist(),
            "explained": explained.tolist(),
            "cumulative": cumulative.tolist(),
            "site_scores": site_scores,
            "response_scores": response_scores,
            "predictor_scores": predictor_scores,
            "total_inertia": total_inertia,
            "constrained_inertia": constrained_inertia,
            "unconstrained_inertia": unconstrained_inertia,
            "n": n,
        }
        print(
            f"[{self.name}] n={n}, responses={len(response_names)}, "
            f"predictors={len(predictor_names)}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export
