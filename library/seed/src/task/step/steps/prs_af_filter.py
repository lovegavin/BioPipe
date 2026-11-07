"""Filter harmonised PRS weights by genotype MAF and missingness."""
from __future__ import annotations

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps import _prs_utils as prs_utils


def _file_path(artifact, operator, formats):
    if not isinstance(artifact, FileArtifact):
        raise StepError(f"{operator} expects a file artifact")
    artifact.validate()
    fmt = str(getattr(artifact, "format", ""))
    if formats and fmt not in formats:
        raise StepError(f"{operator} expects format {'/'.join(sorted(formats))}, got {fmt!r}")
    return next(iter(artifact.files.values()))


def _weight_rows(form, variant_dim, stat_dim, weight_label, operator):
    data = np.asarray(form.data, dtype=float)
    if data.ndim != 2:
        raise StepError(f"{operator}: weights must be a two-dimensional form")
    variant_labels = form.labels.get(variant_dim) or {}
    stat_labels = form.labels.get(stat_dim) or {}
    if weight_label not in stat_labels:
        raise StepError(f"{operator}: weight column {weight_label!r} is missing")
    column = int(stat_labels[weight_label])
    names = [name for name, _ in sorted(variant_labels.items(), key=lambda item: int(item[1]))]
    return names, data[:, column]


class PrsAfFilterStep(Step):
    provider = "operon-core"
    parameters_file = "prs_af_filter.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "prs_af_filter",
        "version": "1.0.0",
        "kind": "operator",
        "title": "prs_af_filter",
        "description": "Drop PRS weights whose variants are monomorphic, missing or too rare.",
        "category": "Omics",
        "icon": "Filter",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "kind": "file", "numeric": False, "ndim": 0, "dims": [],
                 "info": {"representation": {"type": "string", "enum": ["vcf", "vcf.gz"]}}},
                {"version": 1, "kind": "form", "numeric": True, "ndim": 2,
                 "dims": [{"param": "variant_dim", "default": "variant"},
                          {"param": "statistic_dim", "default": "statistic"}],
                 "info_open": True},
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "version": 1,
                    "kind": "form",
                    "numeric": True,
                    "ndim": 2,
                    "dims": [{"param": "variant_dim", "default": "variant"},
                             {"param": "statistic_dim", "default": "statistic"}],
                    "info_open": True,
                },
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return 256 * 1024 * 1024, 8 * 1024 * 1024

    def run(self, ctx: Context, inputs) -> None:
        genotypes, weights = inputs
        params = ctx.step_params
        variant_dim = params.get("variant_dim", "variant") or "variant"
        stat_dim = params.get("statistic_dim", "statistic") or "statistic"
        weight_label = params.get("weight_label", "weight") or "weight"
        min_maf = float(params.get("min_maf", 0.0) or 0.0)
        max_missing = float(params.get("max_missing_rate", 1.0) or 0.0)
        out_name = params.get("output", "filtered") or "filtered"

        vcf_path = _file_path(genotypes, "prs_af_filter", {"vcf", "vcf.gz"})
        names, betas = _weight_rows(weights, variant_dim, stat_dim, weight_label, "prs_af_filter")
        _, records = prs_utils.vcf_variants(vcf_path)
        by_label = {prs_utils.variant_label(record): record for record in records}
        if len(by_label) != len(records):
            # Drops duplicated labels (the typed reader would rename them instead).
            pass

        kept_names = []
        kept_betas = []
        n_missing = 0
        n_rare = 0
        for name, beta in zip(names, betas):
            record = by_label.get(name)
            if record is None:
                n_missing += 1
                continue
            values = prs_utils.dosages(record)
            finite = np.isfinite(values)
            if finite.size == 0 or finite.mean() < 1.0 - max_missing:
                n_missing += 1
                continue
            freq = float(values[finite].mean() / 2.0)
            maf = min(freq, 1.0 - freq)
            if maf < min_maf:
                n_rare += 1
                continue
            kept_names.append(name)
            kept_betas.append(float(beta))

        if not kept_names:
            raise StepError("prs_af_filter: no weight passed the frequency/missingness filters")
        data = np.asarray(kept_betas, dtype=float).reshape(-1, 1)
        form = Form(
            data,
            dims=[variant_dim, stat_dim],
            labels={variant_dim: {name: index for index, name in enumerate(kept_names)},
                    stat_dim: {weight_label: 0}},
            info={"n_input": len(names), "n_kept": len(kept_names),
                  "n_dropped_missing": n_missing, "n_dropped_rare": n_rare,
                  "min_maf": min_maf, "max_missing_rate": max_missing},
        )
        form.validate()
        ctx[out_name] = form
        self._export_data = {
            "n_input": len(names),
            "n_kept": len(kept_names),
            "n_dropped_missing": n_missing,
            "n_dropped_rare": n_rare,
            "min_maf": min_maf,
            "max_missing_rate": max_missing,
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
