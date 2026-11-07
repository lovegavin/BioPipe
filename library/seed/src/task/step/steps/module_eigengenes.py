"""Module eigengenes for a co-expression module assignment.

Takes the expression matrix and the ``[feature, module]`` assignment produced
by ``coexpression_modules`` and returns one eigengene (first principal
component, sign-aligned to the module average) per module and sample.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step

from ._coexpression_common import expression_matrix, module_eigengenes, ordered


def align_modules(module_form, feature_dim: str, features: list[str]) -> np.ndarray:
    if module_form.data.ndim != 2 or module_form.data.shape[1] != 1:
        raise StepError("module assignment must be a [feature, module] form")
    dims = list(module_form.dims)
    if feature_dim not in dims:
        raise StepError(f"module assignment lacks dim {feature_dim!r}")
    if "module" not in dims:
        raise StepError("module assignment lacks dim 'module'")
    axis = dims.index(feature_dim)
    if axis != 0:
        raise StepError("module assignment must have features on the first axis")
    names = ordered(module_form.labels[feature_dim])
    if len(names) != module_form.data.shape[0]:
        raise StepError("module assignment labels do not match its data")
    lookup = {name: int(round(float(module_form.data[i, 0]))) for i, name in enumerate(names)}
    return np.array([lookup.get(name, 0) for name in features], dtype=int)


class ModuleEigengenesStep(Step):
    """Compute one eigengene per co-expression module."""

    provider = "operon-core"
    parameters_file = "module_eigengenes.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "module_eigengenes",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Module eigengenes",
        "description": (
            "Computes the first principal component of every module after "
            "per-gene scaling, sign-aligns it to the module average expression "
            "and reports the explained variance per module."
        ),
        "category": "Omics",
        "icon": "Layers",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        "sample",
                        "feature",
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                },
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        "feature",
                        "module",
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                },
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        shape = inputs[0].data.shape if inputs else (0, 0)
        return (max(int(shape[0]) * int(shape[-1]) * 16, 8 << 20), 0)

    def run(self, ctx, inputs):
        params = ctx.step_params
        sample_dim = str(params.get("sample_dim", "sample"))
        feature_dim = str(params.get("feature_dim", "feature"))
        X, samples, features = expression_matrix(inputs[0], sample_dim, feature_dim)
        labels = align_modules(inputs[1], feature_dim, features)
        ids, ME, variance = module_eigengenes(
            X, labels, scale=bool(params.get("scale", True))
        )
        out_name = str(params.get("output", "eigengenes"))
        out = Form(
            data=ME,
            dims=[sample_dim, "module"],
            labels={
                sample_dim: {name: index for index, name in enumerate(samples)},
                "module": {str(mid): index for index, mid in enumerate(ids)},
            },
            info={
                "n_samples": len(samples),
                "n_modules": len(ids),
                "module_sizes": {
                    str(mid): int(np.sum(labels == mid)) for mid in ids
                },
                "variance_explained": {
                    str(mid): float(variance[index]) for index, mid in enumerate(ids)
                },
                "mean_variance_explained": float(np.nanmean(variance)),
            },
        )
        out.validate()
        ctx[out_name] = out

    def export(self, ctx):
        form = ctx[str(ctx.step_params.get("output", "eigengenes"))]
        variance = form.info["variance_explained"]
        best = max(variance, key=lambda key: variance[key])
        return {
            "n_samples": int(form.info["n_samples"]),
            "n_modules": int(form.info["n_modules"]),
            "best_module": best,
            "best_variance_explained": float(variance[best]),
            "mean_variance_explained": float(form.info["mean_variance_explained"]),
        }
