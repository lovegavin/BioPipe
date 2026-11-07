"""Beta diversity indices computed from presence/absence data."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._ecology_common import abundance
from ._ext_common import require_dims

METHODS = ("w", "-1", "c", "wb", "r", "I", "e", "t", "me", "j", "sor", "m",
           "-2", "co", "cc", "g", "-3", "l", "19", "hk", "rlb", "sim", "gl", "z")

MAXDIST = {
    "w": 1.0, "-1": 1.0, "c": None, "wb": None, "r": 1.0, "I": float(np.log(2.0)),
    "e": 1.0, "t": 1.0, "me": 1.0, "j": 0.0, "sor": 0.0, "m": None, "-2": None,
    "co": 1.0, "cc": 1.0, "g": 1.0, "-3": 1.0, "l": 1.0, "19": None, "hk": 1.0,
    "rlb": 0.0, "sim": 1.0, "gl": None, "z": 1.0,
}


def _xlogx(values):
    out = np.zeros_like(values)
    positive = values > 0.0
    out[positive] = values[positive] * np.log(values[positive])
    return out


def _pair_values(a, b, c, method):
    """vegan::betadiver formulas for one method, element-wise on pairs."""
    total = 2.0 * a + b + c
    richness = a + b + c
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        if method in ("w", "-1", "t", "me", "hk"):
            return (b + c) / total
        if method in ("c", "l"):
            return (b + c) / 2.0
        if method == "wb":
            return b + c
        if method == "r":
            return 2.0 * b * c / (richness ** 2 - 2.0 * b * c)
        if method == "I":
            return (np.log(total) - 2.0 * a * np.log(2.0) / total
                    - (_xlogx(a + b) + _xlogx(a + c)) / total)
        if method == "e":
            return np.exp(np.log(total) - 2.0 * a * np.log(2.0) / total
                          - (_xlogx(a + b) + _xlogx(a + c)) / total) - 1.0
        if method == "j":
            return a / richness
        if method == "sor":
            return 2.0 * a / total
        if method == "m":
            return total * (b + c) / richness
        if method == "-2":
            return np.minimum(b, c) / (np.maximum(b, c) + a)
        if method == "co":
            return (a * c + a * b + 2.0 * b * c) / (2.0 * (a + b) * (a + c))
        if method in ("cc", "g"):
            return (b + c) / richness
        if method == "-3":
            return np.minimum(b, c) / richness
        if method == "19":
            return 2.0 * (b * c + 1.0) / richness / (richness - 1.0)
        if method == "rlb":
            return a / (a + c)
        if method == "sim":
            return np.minimum(b, c) / (np.minimum(b, c) + a)
        if method == "gl":
            return 2.0 * np.abs(b - c) / total
        if method == "z":
            return (np.log(2.0) - np.log(total) + np.log(richness)) / np.log(2.0)
    raise StepError(f"betadiver: unknown method {method!r}")


class BetadiverStep(Step):
    provider = "operon-microbiome"
    parameters_file = "betadiver.BetadiverStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "betadiver",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Beta diversity from presence/absence",
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
            "Pairwise beta diversity between samples from a presence/absence "
            "transformation of an abundance table, following vegan betadiver."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        taxon_dim = ctx.step_params.get("taxon_dim", "taxon")
        sample_b_dim = ctx.step_params.get("sample_b_dim", "sample_b")
        method = str(ctx.step_params.get("method", "w"))
        out_name = ctx.step_params.get("output", self.name)
        if method not in METHODS:
            raise StepError(
                f"betadiver: unknown method {method!r}; expected one of {list(METHODS)}"
            )
        require_dims(form, sample_dim, taxon_dim, label="betadiver")
        data, samples, taxa = abundance(form, sample_dim, taxon_dim, "betadiver")
        presence = (data > 0.0).astype(np.float64)
        sizes = presence.sum(axis=1)
        shared = presence @ presence.T
        rows, cols = np.tril_indices(len(samples), -1)
        a = shared[rows, cols]
        b = sizes[rows] - a
        c = sizes[cols] - a
        values = _pair_values(a, b, c, method)
        if not np.all(np.isfinite(values)):
            raise StepError(
                "betadiver: method is undefined for degenerate sample pairs "
                "(empty samples or a zero denominator)"
            )
        matrix = np.zeros((len(samples), len(samples)), dtype=np.float64)
        matrix[rows, cols] = values
        matrix[cols, rows] = values
        label_map = {name: i for i, name in enumerate(samples)}
        out = Form(
            data=matrix.astype(np.float32),
            dims=[sample_dim, sample_b_dim],
            labels={sample_dim: dict(label_map), sample_b_dim: dict(label_map)},
            info={"missing_code": np.nan, "method": f"beta.{method}",
                  "maxdist": MAXDIST[method], "n_samples": len(samples),
                  "n_taxa": len(taxa), "presence_only": True},
        )
        ctx[out_name] = out
        self._export_data = {"method": method, "n_samples": len(samples),
                             "n_taxa": len(taxa)}
        print(f"[{self.name}] method={method} samples={len(samples)}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
