"""Correlation of module eigengenes with sample traits.

Inputs: the ``[sample, module]`` eigengene matrix and a ``[sample, trait]``
numeric table.  Output: one row per module/trait pair with the Pearson
correlation, its two-sided p-value and the number of samples.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step

from ._coexpression_common import cor_pvalue, ordered

_STATISTICS = {"correlation": 0, "p_value": 1, "n_samples": 2}


def correlation_matrix(ME: np.ndarray, traits: np.ndarray) -> np.ndarray:
    if ME.shape[0] != traits.shape[0]:
        raise StepError("eigengenes and traits must share the sample axis")
    if ME.shape[1] < 1 or traits.shape[1] < 1:
        raise StepError("need at least one module and one trait")

    def standardise(matrix):
        mean = matrix.mean(axis=0, keepdims=True)
        sd = matrix.std(axis=0, ddof=1, keepdims=True)
        sd = np.where(sd > 0, sd, np.nan)
        return (matrix - mean) / sd

    Zm = standardise(ME)
    Zt = standardise(traits)
    with np.errstate(invalid="ignore", divide="ignore"):
        C = (Zm.T @ Zt) / float(ME.shape[0] - 1)
    C = np.clip(np.nan_to_num(C, nan=0.0), -1.0, 1.0)
    return C


class ModuleTraitCorrelationStep(Step):
    """Correlate module eigengenes with sample traits."""

    provider = "operon-core"
    parameters_file = "module_trait_correlation.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "module_trait_correlation",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Module-trait correlations",
        "description": (
            "Correlates every module eigengene with every sample trait, reports "
            "Pearson r, the two-sided p-value and the sample count, and returns "
            "the strongest association."
        ),
        "category": "Omics",
        "icon": "Table",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        "sample",
                        "module",
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                },
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        "sample",
                        "trait",
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
        "dependencies": ["numpy>=1.24", "scipy>=1.10"],
        "dependency_imports": ["numpy", "scipy"],
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        modules = inputs[0].data.shape[-1] if inputs else 0
        traits = inputs[1].data.shape[-1] if len(inputs) > 1 else 0
        return (max(int(modules) * int(traits) * 24, 4 << 20), 0)

    def run(self, ctx, inputs):
        params = ctx.step_params
        sample_dim = str(params.get("sample_dim", "sample"))
        trait_dim = str(params.get("trait_dim", "trait"))
        eigengenes, traits_form = inputs[0], inputs[1]
        if eigengenes.data.ndim != 2 or traits_form.data.ndim != 2:
            raise StepError("both inputs must be 2D forms")

        modules = ordered(eigengenes.labels["module"])
        traits = ordered(traits_form.labels[trait_dim])
        samples = ordered(eigengenes.labels[sample_dim])
        other_samples = ordered(traits_form.labels[sample_dim])
        if samples != other_samples:
            raise StepError("input forms have different sample labels")
        ME = np.asarray(eigengenes.data, dtype=np.float64)
        Y = np.asarray(traits_form.data, dtype=np.float64)
        if ME.shape != (len(samples), len(modules)):
            raise StepError("eigengene labels do not match the data shape")
        if Y.shape != (len(samples), len(traits)):
            raise StepError("trait labels do not match the data shape")

        C = correlation_matrix(ME, Y)
        P = cor_pvalue(C, len(samples))
        rows = []
        labels = {}
        for mi, module in enumerate(modules):
            for ti, trait in enumerate(traits):
                labels[f"{module}|{trait}"] = len(rows)
                rows.append([C[mi, ti], P[mi, ti], len(samples)])
        data = np.array(rows, dtype=np.float64)

        finite = np.isfinite(P)
        n_significant = int(np.sum(P[finite] < 0.05))
        flat = int(np.nanargmax(np.where(np.isfinite(C), np.abs(C), -1.0)))
        mi, ti = divmod(flat, len(traits))
        out_name = str(params.get("output", "module_traits"))
        out = Form(
            data=data,
            dims=["module_trait", "statistic"],
            labels={"module_trait": labels, "statistic": dict(_STATISTICS)},
            info={
                "n_samples": len(samples),
                "n_modules": len(modules),
                "n_traits": len(traits),
                "n_significant": n_significant,
                "strongest_pair": f"{modules[mi]}|{traits[ti]}",
            },
        )
        out.validate()
        ctx[out_name] = out

    def export(self, ctx):
        form = ctx[str(ctx.step_params.get("output", "module_traits"))]
        pair = str(form.info["strongest_pair"])
        index = form.labels["module_trait"][pair]
        return {
            "n_pairs": int(form.data.shape[0]),
            "n_samples": int(form.info["n_samples"]),
            "n_significant": int(form.info["n_significant"]),
            "strongest_pair": pair,
            "strongest_correlation": float(form.data[index, 0]),
            "strongest_p_value": float(form.data[index, 1]),
        }
