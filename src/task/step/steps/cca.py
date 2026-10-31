"""Canonical correspondence analysis (CCA)."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import table


class CcaStep(Step):
    """Constrained correspondence analysis of a count table."""

    name = "cca"
    title = "Canonical correspondence analysis"
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
        Y, y_samples, species = table(
            response, sample_dim, response_dim, self.name
        )
        X, x_samples, predictors = table(
            predictor, sample_dim, predictor_dim, self.name
        )
        if set(y_samples) != set(x_samples):
            raise StepError(f"{self.name}: response and predictor samples must match")
        x_pos = {name: index for index, name in enumerate(x_samples)}
        X = X[[x_pos[name] for name in y_samples]]
        samples = y_samples

        if Y.shape[0] < 3 or Y.shape[1] < 2:
            raise StepError(f"{self.name}: need at least three sites and two species")
        if np.any(Y < 0):
            raise StepError(f"{self.name}: response counts must be nonnegative")
        if X.shape[1] < 1:
            raise StepError(f"{self.name}: at least one predictor is required")
        total = float(Y.sum())
        if total <= 0:
            raise StepError(f"{self.name}: response table is empty")
        row_mass = Y.sum(axis=1)
        col_mass = Y.sum(axis=0)
        if np.any(row_mass <= 0) or np.any(col_mass <= 0):
            raise StepError(f"{self.name}: every site and species needs a positive margin")

        r = row_mass / total
        c = col_mass / total
        expected = np.outer(r, c)
        Q = (Y / total - expected) / np.sqrt(expected)
        total_inertia = float(np.sum(Q**2))
        if total_inertia <= 0:
            raise StepError(f"{self.name}: response table has no inertia")

        center = np.average(X, axis=0, weights=r)
        Xc = X - center
        Xw = Xc * np.sqrt(r)[:, None]
        rank = int(np.linalg.matrix_rank(Xw))
        if rank < 1:
            raise StepError(f"{self.name}: predictor matrix is rank deficient")
        if Y.shape[0] <= X.shape[1]:
            raise StepError(f"{self.name}: need more sites than predictors")
        # vegan fits the weighted design against the unweighted
        # correspondence matrix; this reproduces its constrained inertia.
        beta, _, _, _ = np.linalg.lstsq(Xw, Q, rcond=None)
        fitted = Xw @ beta
        U, singular, Vt = np.linalg.svd(fitted, full_matrices=False)
        constrained = float(np.sum(singular**2))
        unconstrained = max(0.0, total_inertia - constrained)
        requested = int(ctx.step_params.get("n_components", 2))
        components = min(
            requested,
            rank,
            len(singular),
            Y.shape[0] - 1,
            Y.shape[1] - 1,
        )
        if components < 1:
            raise StepError(f"{self.name}: no constrained components available")
        eigen = singular[:components] ** 2
        explained = eigen / total_inertia
        cumulative = np.cumsum(explained)
        site_scores = U[:, :components]
        species_scores = Vt[:components, :].T
        weighted_averages = (Y / row_mass[:, None]) @ species_scores

        out = Form(
            data=np.column_stack([eigen, explained, cumulative]),
            dims=["component", "statistic"],
            labels={
                "component": {
                    f"CCA{index + 1}": index for index in range(components)
                },
                "statistic": {
                    "eigenvalue": 0,
                    "explained": 1,
                    "cumulative": 2,
                },
            },
            info={
                "method": "cca",
                "n_sites": int(Y.shape[0]),
                "n_species": int(Y.shape[1]),
                "n_predictors": int(X.shape[1]),
                "rank": rank,
                "total_inertia": total_inertia,
                "constrained_inertia": constrained,
                "unconstrained_inertia": unconstrained,
                "constrained_fraction": constrained / total_inertia,
            },
        )
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export = {
            "samples": samples,
            "response_labels": species,
            "predictor_labels": predictors,
            "eigenvalues": [float(value) for value in eigen],
            "explained": [float(value) for value in explained],
            "cumulative": [float(value) for value in cumulative],
            "total_inertia": total_inertia,
            "constrained_inertia": constrained,
            "unconstrained_inertia": unconstrained,
            "constrained_fraction": constrained / total_inertia,
            "site_scores": site_scores.tolist(),
            "species_scores": species_scores.tolist(),
            "site_weighted_averages": weighted_averages.tolist(),
            "row_weights": [float(value) for value in r],
            "column_weights": [float(value) for value in c],
        }
        print(
            f"[{self.name}] sites={Y.shape[0]}, species={Y.shape[1]}, "
            f"components={components}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export
