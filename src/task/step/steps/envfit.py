"""Fit linear environmental vectors onto an ordination (vegan envfit vectors)."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._ext_common import labels_in_order, reorder, require_dims


class EnvfitStep(Step):
    name = "envfit"
    title = "Environmental vector fitting"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.26"]
    dependency_imports = ["numpy"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("component_dim", "component")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")]),
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "component_dim": {"type": "string", "default": "component"},
            "feature_dim": {"type": "string", "default": "feature"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        component_dim = ctx.step_params.get("component_dim", "component")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        ordination, environment = inputs
        require_dims(ordination, sample_dim, component_dim, label="envfit ordination")
        require_dims(environment, sample_dim, feature_dim, label="envfit environment")

        if ordination.dims != [sample_dim, component_dim]:
            ordination_data = reorder(ordination, sample_dim, component_dim)
        else:
            ordination_data = np.asarray(ordination.data, dtype=np.float64)
        if environment.dims != [sample_dim, feature_dim]:
            environment_data = reorder(environment, sample_dim, feature_dim)
        else:
            environment_data = np.asarray(environment.data, dtype=np.float64)

        ord_samples = labels_in_order(ordination, sample_dim)
        env_samples = labels_in_order(environment, sample_dim)
        ord_axes = labels_in_order(ordination, component_dim)
        env_features = labels_in_order(environment, feature_dim)
        if len(ord_samples) != ordination_data.shape[0]:
            raise StepError("envfit: ordination sample labels do not match rows")
        if len(env_samples) != environment_data.shape[0]:
            raise StepError("envfit: environment sample labels do not match rows")
        if len(ord_axes) != ordination_data.shape[1]:
            raise StepError("envfit: ordination component labels do not match columns")
        if len(env_features) != environment_data.shape[1]:
            raise StepError("envfit: environment feature labels do not match columns")
        if len(ord_axes) < 2:
            raise StepError("envfit: need at least 2 ordination components")

        env_index = {name: i for i, name in enumerate(env_samples)}
        common = [name for name in ord_samples if name in env_index]
        if len(common) < 3:
            raise StepError(f"envfit: need at least 3 shared samples, got {len(common)}")
        ord_index = {name: i for i, name in enumerate(ord_samples)}
        x = np.asarray(
            [ordination_data[ord_index[name]] for name in common], dtype=np.float64
        )
        y = np.asarray(
            [environment_data[env_index[name]] for name in common], dtype=np.float64
        )
        finite = np.isfinite(x).all(axis=1) & np.isfinite(y).all(axis=1)
        x = x[finite]
        y = y[finite]
        n = x.shape[0]
        if n < max(3, x.shape[1] + 2):
            raise StepError("envfit: too few finite samples for the number of components")
        if not np.isfinite(x).all() or not np.isfinite(y).all():
            raise StepError("envfit: ordination and environment must be finite")

        design = np.column_stack([np.ones(n), x])
        if np.linalg.matrix_rank(design) < design.shape[1]:
            raise StepError("envfit: ordination design is rank deficient")

        rows = []
        arrows = []
        r2_values = []
        for j, feature in enumerate(env_features):
            values = y[:, j]
            total = float(np.sum((values - values.mean()) ** 2))
            if total <= 0:
                raise StepError(f"envfit: environment feature {feature!r} has zero variance")
            beta = np.linalg.lstsq(design, values, rcond=None)[0]
            residual = float(np.sum((values - design @ beta) ** 2))
            r2 = 1.0 - residual / total
            direction = np.asarray(beta[1:], dtype=np.float64)
            norm = float(np.linalg.norm(direction))
            if norm > 0:
                direction = direction / norm
            else:
                direction = np.zeros_like(direction)
            r2_values.append(r2)
            arrows.append(direction)
            rows.append(np.concatenate([[r2], direction]))

        data = np.asarray(rows, dtype=np.float32)
        statistic_labels = {"r2": 0}
        for i in range(len(ord_axes)):
            statistic_labels[f"axis{i + 1}"] = i + 1
        info = {
            "method": "envfit",
            "n": n,
            "n_components": len(ord_axes),
            "n_features": len(env_features),
            "permutations": 0,
            "normalization": "unit_length",
        }
        form = Form(
            data=data,
            dims=[feature_dim, "statistic"],
            labels={
                feature_dim: {name: i for i, name in enumerate(env_features)},
                "statistic": statistic_labels,
            },
            info=info,
        )
        form.validate()
        ctx[ctx.step_params.get("output", self.name)] = form
        self._export = {
            "n": n,
            "n_components": len(ord_axes),
            "n_features": len(env_features),
            "permutations": 0,
            "normalization": "unit_length",
            "r2": {name: float(r2) for name, r2 in zip(env_features, r2_values)},
            "arrows": {
                name: [float(v) for v in direction]
                for name, direction in zip(env_features, arrows)
            },
        }
        print(f"[envfit] n={n} features={len(env_features)} components={len(ord_axes)}")

    def export(self, ctx: Context) -> dict:
        return self._export
