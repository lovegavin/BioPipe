"""Tsallis diversity profiles."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._ecology_common import abundance
from ._ext_common import require_dims


def _transform(entropy, q, richness, hill, norm):
    with np.errstate(divide="ignore", invalid="ignore"):
        if norm:
            if q == 1.0:
                entropy = entropy / np.log(richness)
            else:
                entropy = entropy / ((richness ** (1.0 - q) - 1.0) / (1.0 - q))
        if hill:
            if q == 1.0:
                return np.exp(entropy)
            return (1.0 - (q - 1.0) * entropy) ** (1.0 / (1.0 - q))
    return entropy


def _profile(p, q, richness, hill, norm):
    if q == 0.0:
        values = richness - 1.0
    elif q == 1.0:
        values = np.zeros(p.shape[0], dtype=np.float64)
        positive = p > 0.0
        values = -np.sum(np.where(positive, p * np.log(np.where(positive, p, 1.0)), 0.0),
                         axis=1)
    else:
        with np.errstate(divide="ignore", invalid="ignore"):
            values = (1.0 - np.sum(p ** q, axis=1)) / (q - 1.0)
    return _transform(values, q, richness, hill, norm)


class TsallisStep(Step):
    provider = "operon-microbiome"
    parameters_file = "tsallis.TsallisStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "tsallis",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Tsallis diversity profiles",
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
            "Tsallis generalised entropy of each sample across taxa for a "
            "requested set of q orders, following vegan tsallis."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        taxon_dim = ctx.step_params.get("taxon_dim", "taxon")
        scales = ctx.step_params.get("scales", [0, 0.5, 1, 2])
        hill = bool(ctx.step_params.get("hill", False))
        norm = bool(ctx.step_params.get("norm", False))
        out_name = ctx.step_params.get("output", self.name)
        if hill and norm:
            raise StepError("tsallis: 'norm' and 'hill' cannot be enabled together")
        require_dims(form, sample_dim, taxon_dim, label="tsallis")
        if not isinstance(scales, (list, tuple)) or not scales:
            raise StepError("tsallis: scales must be a non-empty list of numbers")
        orders = []
        for value in scales:
            order = float(value)
            if not np.isfinite(order):
                raise StepError("tsallis: scales must be finite (Inf is not supported)")
            orders.append(order)
        data, samples, taxa = abundance(form, sample_dim, taxon_dim, "tsallis")
        if len(taxa) < 2:
            raise StepError("tsallis: need at least two taxa")
        totals = data.sum(axis=1)
        p = np.zeros_like(data)
        good = totals > 0.0
        p[good] = data[good] / totals[good, None]
        richness = np.count_nonzero(data > 0.0, axis=1).astype(np.float64)
        columns = []
        labels = []
        for order in orders:
            values = np.full(len(samples), np.nan, dtype=np.float64)
            if np.any(good):
                values[good] = _profile(p[good], order, richness[good], hill, norm)
            columns.append(values)
            labels.append(str(int(order)) if float(order).is_integer() else str(order))
        matrix = np.column_stack(columns).astype(np.float32)
        out = Form(
            data=matrix,
            dims=[sample_dim, "scale"],
            labels={sample_dim: {name: i for i, name in enumerate(samples)},
                    "scale": {name: i for i, name in enumerate(labels)}},
            info={"missing_code": np.nan, "method": "tsallis",
                  "hill": hill, "norm": norm, "n_taxa": len(taxa),
                  "zero_samples": int(np.sum(~good))},
        )
        ctx[out_name] = out
        self._export_data = {"scales": labels, "hill": hill, "norm": norm}
        print(f"[{self.name}] samples={len(samples)} scales={len(labels)}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
