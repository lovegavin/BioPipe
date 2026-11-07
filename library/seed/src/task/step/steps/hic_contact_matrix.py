"""Bin Hi-C pairs into a long-form contact table."""
from __future__ import annotations

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.step.base import Step

from . import _hic_utils as hic

_FIELDS = ["start1", "start2", "count"]


def _file_path(artifact, operator):
    if not isinstance(artifact, FileArtifact):
        raise StepError(f"{operator} expects a file artifact")
    artifact.validate()
    return next(iter(artifact.files.values()))


class HicContactMatrixStep(Step):
    provider = "operon-core"
    parameters_file = "hic_contact_matrix.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}},
                    {'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "hic_contact_matrix",
        "version": "1.0.0",
        "kind": "operator",
        "title": "hic_contact_matrix",
        "description": "Bin cis Hi-C pairs into a long-form contact table at a fixed resolution.",
        "category": "Genome",
        "icon": "Table",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "kind": "file", "numeric": False, "ndim": 0, "dims": [],
                 "info": {"representation": {"type": "string", "enum": ["pairs", "pairs.gz"]}}},
                {"version": 1, "kind": "file", "numeric": False, "ndim": 0, "dims": [],
                 "info": {"representation": {"type": "string", "enum": ["tsv", "txt", "tsv.gz", "txt.gz"]}}},
            ],
            "output": {"mode": "declare", "schema": {
                "kind": "form", "numeric": True, "ndim": 2,
                "dims": [{"param": "contact_dim", "default": "contact"}, {"param": "field_dim", "default": "field"}],
                "labels": {"contact": [], "field": ["start1", "start2", "count"]},
                "info_open": True,
            }},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = 0
        for item in inputs or []:
            try:
                size += int(item.get("size_bytes") or 0)
            except AttributeError:
                pass
        return max(size * 2, 64 * 1024 * 1024), 0

    def run(self, ctx, input_forms):
        params = ctx.step_params
        out_name = params.get("output", "contacts")
        pairs_path = _file_path(input_forms[0], "hic_contact_matrix")
        sizes_path = _file_path(input_forms[1], "hic_contact_matrix")
        sizes = hic.read_chrom_sizes(sizes_path)
        resolution = int(float(params.get("resolution", 1_000_000)))
        chromosome = str(params.get("chromosome", "") or "")
        include_trans = bool(params.get("include_trans", False))
        rows, used = hic.bin_contacts(pairs_path, sizes, resolution, chromosome=chromosome,
                                      include_trans=include_trans,
                                      max_pairs=int(params.get("max_pairs", 0)))
        if not rows:
            raise StepError("hic_contact_matrix: no contacts remained after filtering")
        data = np.asarray([[start1, start2, count] for _label, start1, start2, count in rows], dtype=np.float64)
        labels = {}
        chroms = []
        for label, start1, start2, _count in rows:
            key = f"{label}:{start1}-{start2}"
            if key in labels:
                key = f"{key}#{len(labels)}"
            labels[key] = len(labels)
            chroms.append(label)
        info = {
            "contact_dim": "contact",
            "field_dim": "field",
            "resolution": resolution,
            "chromosome": chromosome,
            "include_trans": include_trans,
            "n_contacts": len(rows),
            "pairs_used": used,
            "chrom": chroms,
        }
        form = Form(data, dims=["contact", "field"],
                    labels={"contact": labels, "field": {name: index for index, name in enumerate(_FIELDS)}},
                    info=info, axis_info={"contact": ["chrom"]})
        form.validate()
        ctx[out_name] = form
        self._export_data = {"n_contacts": len(rows), "pairs_used": used, "resolution": resolution,
                             "chromosome": chromosome}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
