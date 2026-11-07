"""Morisita dispersal index and spatial distribution types."""
from __future__ import annotations

import numpy as np
from scipy.stats import chi2

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._ecology_common import abundance
from ._ext_common import require_dims


def _indices(values, crit):
    n = values.size
    total = float(values.sum())
    if total <= 1.0:
        return np.full(5, np.nan, dtype=np.float64)
    imor = n * ((np.sum(values * values) - total) / (total * total - total))
    upper = float(chi2.ppf(1.0 - crit / 2.0, n - 1))
    lower = float(chi2.ppf(crit / 2.0, n - 1))
    mclu = (upper - n + total) / (total - 1.0)
    muni = (lower - n + total) / (total - 1.0)
    pchi = float(chi2.sf(imor * (total - 1.0) + n - total, n - 1))
    imst = imor
    if imor >= mclu and mclu > 1.0:
        if n != mclu:
            imst = 0.5 + 0.5 * ((imor - mclu) / (n - mclu))
    elif mclu > imor and imor >= 1.0:
        if mclu != 1.0:
            imst = 0.5 * ((imor - 1.0) / (mclu - 1.0))
    elif 1.0 > imor and imor > muni:
        if muni != 1.0:
            imst = -0.5 * ((imor - 1.0) / (muni - 1.0))
    elif 1.0 > muni and muni > imor:
        if muni != 0.0:
            imst = -0.5 + 0.5 * ((imor - muni) / muni)
    return np.array([imor, mclu, muni, imst, pchi], dtype=np.float64)


class MorisitaStep(Step):
    provider = "operon-microbiome"
    parameters_file = "morisita.MorisitaStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "morisita",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Morisita dispersal index",
        "category": "Omics",
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "info": {},
                        "ndim": 2,
                        "dims": [{"param": "sample_dim", "default": "sample"},
                                 {"param": "feature_dim", "default": "feature"}],
                        "labels": [], "parallel": []}],
            "output": {"mode": "declare",
                       "schema": {"ndim": 2, "numeric": True,
                                  "info_open": True, "axis_info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False,
                      "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.26", "scipy>=1.11"],
        "dependency_imports": ["numpy", "scipy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "description": (
            "Morisita index of dispersion with its clustering and uniform "
            "critical values, the standardised index and the chi-square "
            "probability for every feature, following vegan dispindmorisita."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        crit = float(ctx.step_params.get("crit", 0.05))
        unique_rm = bool(ctx.step_params.get("unique_rm", False))
        out_name = ctx.step_params.get("output", self.name)
        require_dims(form, sample_dim, feature_dim, label="morisita")
        if not np.isfinite(crit) or not 0.0 < crit < 1.0:
            raise StepError("morisita: crit must lie strictly between 0 and 1")
        data, samples, features = abundance(form, sample_dim, feature_dim, "morisita")
        if len(samples) < 2:
            raise StepError("morisita: need at least two samples")
        if len(features) == 0:
            raise StepError("morisita: need at least one feature")
        presence = data > 0.0
        removed = [name for name, count in zip(features, presence.sum(axis=0))
                   if unique_rm and count == 1]
        keep = np.ones(len(features), dtype=bool)
        if unique_rm:
            keep = presence.sum(axis=0) != 1
        kept = [name for name, flag in zip(features, keep) if flag]
        if not kept:
            raise StepError("morisita: no feature remains after unique.rm")
        rows = []
        skipped = []
        for index, name in enumerate(features):
            if not keep[index]:
                continue
            values = data[:, index]
            if float(values.sum()) <= 1.0:
                skipped.append(name)
                rows.append(np.full(5, np.nan, dtype=np.float64))
                continue
            rows.append(_indices(values, crit))
        matrix = np.asarray(rows, dtype=np.float64)
        out = Form(
            data=matrix.astype(np.float32),
            dims=["feature", "statistic"],
            labels={"feature": {name: i for i, name in enumerate(kept)},
                    "statistic": {"imor": 0, "mclu": 1, "muni": 2,
                                  "imst": 3, "pchisq": 4}},
            info={"missing_code": np.nan, "method": "vegan::dispindmorisita",
                  "crit": crit, "n_samples": len(samples),
                  "n_features": len(kept), "unique_rm": unique_rm,
                  "removed": removed, "skipped": skipped},
        )
        ctx[out_name] = out
        self._export_data = {"n_features": len(kept), "crit": crit}
        print(f"[{self.name}] features={len(kept)} samples={len(samples)}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
