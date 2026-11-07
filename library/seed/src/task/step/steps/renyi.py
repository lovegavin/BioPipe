"""Renyi diversity profiles."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._ecology_common import abundance
from ._ext_common import require_dims


def _profile(p, alpha):
    nonzero = p > 0.0
    if alpha == 0.0:
        return float(np.log(np.count_nonzero(nonzero)))
    if alpha == 1.0:
        return float(-np.sum(p[nonzero] * np.log(p[nonzero])))
    if np.isinf(alpha):
        return float(-np.log(np.max(p)))
    return float(np.log(np.sum(p ** alpha)) / (1.0 - alpha))


class RenyiStep(Step):
    provider = "operon-microbiome"
    parameters_file = "renyi.RenyiStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "renyi",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Renyi diversity profiles",
        "category": "Omics",
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "info": {},
                        "ndim": 2,
                        "dims": [{"param": "sample_dim", "default": "sample"},
                                 {"param": "taxon_dim", "default": "taxon"}],
                        "labels": [], "parallel": []}],
            "output": {"mode": "declare",
                       "schema": {"ndim": 2, "numeric": True,
                                  "info_open": True,
                                  "axis_info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False,
                      "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.26"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "description": (
            "Renyi generalised entropy of each sample across taxa for a "
            "requested set of alpha orders, following vegan renyi."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        taxon_dim = ctx.step_params.get("taxon_dim", "taxon")
        scales = ctx.step_params.get("scales", [0, 0.5, 1, 2, 4])
        include_inf = bool(ctx.step_params.get("include_inf", True))
        hill = bool(ctx.step_params.get("hill", False))
        out_name = ctx.step_params.get("output", self.name)
        require_dims(form, sample_dim, taxon_dim, label="renyi")
        if not isinstance(scales, (list, tuple)) or not scales:
            raise StepError("renyi: scales must be a non-empty list of numbers")
        alphas = []
        for value in scales:
            alpha = float(value)
            if not np.isfinite(alpha) and not np.isinf(alpha):
                raise StepError("renyi: scales must be finite or Inf")
            alphas.append(alpha)
        if include_inf and not any(np.isinf(a) for a in alphas):
            alphas.append(float("inf"))
        data, samples, taxa = abundance(form, sample_dim, taxon_dim, "renyi")
        totals = data.sum(axis=1)
        p = np.zeros_like(data)
        good = totals > 0.0
        p[good] = data[good] / totals[good, None]
        labels = []
        columns = []
        for alpha in alphas:
            values = np.full(len(samples), np.nan, dtype=np.float64)
            for i in range(len(samples)):
                if not good[i]:
                    continue
                values[i] = _profile(p[i], alpha)
            if hill:
                values = np.exp(values)
            label = "Inf" if np.isinf(alpha) else (
                str(int(alpha)) if float(alpha).is_integer() else str(alpha))
            labels.append(label)
            columns.append(values)
        data_out = np.column_stack(columns).astype(np.float32)
        ctx[out_name] = Form(
            data=data_out,
            dims=[sample_dim, "scale"],
            labels={sample_dim: {name: i for i, name in enumerate(samples)},
                    "scale": {name: i for i, name in enumerate(labels)}},
            info={"missing_code": np.nan, "method": "renyi",
                  "hill": hill, "n_taxa": len(taxa),
                  "zero_samples": int(np.sum(~good))},
        )
        self._export_data = {"scales": labels, "hill": hill}
        print(f"[{self.name}] samples={len(samples)} scales={len(labels)}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
