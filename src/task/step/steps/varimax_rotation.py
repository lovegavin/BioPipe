"""Varimax rotation of a loading matrix."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import labels_in_order, reorder


class VarimaxRotationStep(Step):
    """Orthogonal varimax rotation, matching ``stats::varimax``."""

    name = "varimax_rotation"
    title = "Varimax rotation"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.26"]
    dependency_imports = ["numpy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("variable_dim", "variable"), param("factor_dim", "factor")])
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "variable_dim": {"type": "string", "default": "variable"},
            "factor_dim": {"type": "string", "default": "factor"},
            "normalize": {"type": "boolean", "default": True, "title": "行标准化"},
            "eps": {"type": "number", "exclusiveMinimum": 0, "default": 1e-5},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        variable_dim = ctx.step_params.get("variable_dim", "variable")
        factor_dim = ctx.step_params.get("factor_dim", "factor")
        out_name = ctx.step_params.get("output", self.name)
        normalize = bool(ctx.step_params.get("normalize", True))
        eps = float(ctx.step_params.get("eps", 1e-5))
        if eps <= 0:
            raise StepError("varimax_rotation: eps must be positive")
        loadings = reorder(form, variable_dim, factor_dim)
        if loadings.shape[1] < 2:
            raise StepError("varimax_rotation: at least two factors are required")
        if not np.isfinite(loadings).all():
            raise StepError("varimax_rotation: loadings must be finite")
        n_variables, n_factors = loadings.shape
        working = loadings.astype(np.float64).copy()
        scales = None
        if normalize:
            scales = np.sqrt(np.sum(working ** 2, axis=1))
            if np.any(scales <= 0):
                raise StepError(
                    "varimax_rotation: every variable must have a non-zero loading vector"
                )
            working = working / scales[:, None]

        rotation = np.eye(n_factors, dtype=np.float64)
        criterion = 0.0
        for _ in range(1000):
            rotated = working @ rotation
            squared = rotated ** 2
            weights = squared - squared.mean(axis=0, keepdims=True)
            cross = working.T @ (rotated * weights)
            u, singular, vt = np.linalg.svd(cross)
            rotation = u @ vt
            new_criterion = float(np.sum(singular))
            if new_criterion < criterion * (1.0 + eps):
                break
            criterion = new_criterion

        rotated = working @ rotation
        if scales is not None:
            rotated = rotated * scales[:, None]
        rotated = rotated.astype(np.float32)

        variables = labels_in_order(form, variable_dim)
        factors = labels_in_order(form, factor_dim)
        if len(variables) != n_variables or len(factors) != n_factors:
            raise StepError("varimax_rotation: labels do not match input shape")
        out = Form(
            data=rotated,
            dims=[variable_dim, factor_dim],
            labels={
                variable_dim: {name: i for i, name in enumerate(variables)},
                factor_dim: {name: i for i, name in enumerate(factors)},
            },
            info={
                "missing_code": np.nan,
                "rotation": rotation.tolist(),
                "ss_loadings": np.sum(rotated.astype(np.float64) ** 2, axis=0).tolist(),
                "normalize": normalize,
                "eps": eps,
                "criterion": criterion,
                "converged": criterion > 0,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "rotation": rotation.tolist(),
            "ss_loadings": np.sum(rotated.astype(np.float64) ** 2, axis=0).tolist(),
            "criterion": criterion,
            "n_variables": int(n_variables),
            "n_factors": int(n_factors),
            "normalize": normalize,
        }
        print(
            f"[varimax_rotation] {n_variables}x{n_factors}, "
            f"SS={np.sum(rotated.astype(np.float64) ** 2, axis=0).round(6).tolist()}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
