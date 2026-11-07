"""LD-clump harmonised PRS weights by greedy r-squared pruning."""
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


class PrsLdClumpStep(Step):
    provider = "operon-core"
    parameters_file = "prs_ld_clump.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "prs_ld_clump",
        "version": "1.0.0",
        "kind": "operator",
        "title": "prs_ld_clump",
        "description": "Keep the strongest weights per LD window using genotype r-squared.",
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
        threshold = float(params.get("r2_threshold", 0.2) or 0.2)
        window = int(params.get("window_bp", 100000) or 0)
        max_variants = int(params.get("max_variants", 0) or 0)
        out_name = params.get("output", "clumped") or "clumped"

        vcf_path = _file_path(genotypes, "prs_ld_clump", {"vcf", "vcf.gz"})
        names, betas = _weight_rows(weights, variant_dim, stat_dim, weight_label, "prs_ld_clump")
        if names and max_variants:
            order = np.argsort(-np.abs(betas))[:max_variants]
            names = [names[index] for index in order]
            betas = betas[order]

        _, records = prs_utils.vcf_variants(vcf_path)
        by_label = {prs_utils.variant_label(record): record for record in records}
        dosages = {}
        for name in names:
            record = by_label.get(name)
            if record is not None:
                dosages[name] = prs_utils.dosages(record)
        candidates = [(name, float(beta)) for name, beta in zip(names, betas) if name in dosages]
        candidates.sort(key=lambda item: -abs(item[1]))

        kept = []
        pruned = 0
        for name, beta in candidates:
            record = by_label[name]
            redundant = False
            for other, _ in kept:
                other_record = by_label[other]
                if abs(other_record["pos"] - record["pos"]) > window:
                    continue
                if prs_utils.r2_between(dosages[other], dosages[name]) > threshold:
                    redundant = True
                    break
            if redundant:
                pruned += 1
                continue
            kept.append((name, beta))
        if not kept:
            raise StepError("prs_ld_clump: no weight survived clumping")
        kept.sort(key=lambda item: item[0])
        data = np.asarray([beta for _, beta in kept], dtype=float).reshape(-1, 1)
        names_out = [name for name, _ in kept]
        form = Form(
            data,
            dims=[variant_dim, stat_dim],
            labels={variant_dim: {name: index for index, name in enumerate(names_out)},
                    stat_dim: {weight_label: 0}},
            info={"n_input": len(names), "n_kept": len(names_out), "n_pruned": pruned,
                  "r2_threshold": threshold, "window_bp": window},
        )
        form.validate()
        ctx[out_name] = form
        self._export_data = {
            "n_input": len(names),
            "n_kept": len(names_out),
            "n_pruned": pruned,
            "r2_threshold": threshold,
            "window_bp": window,
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
