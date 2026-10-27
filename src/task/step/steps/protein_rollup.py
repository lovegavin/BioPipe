# src/task/step/steps/protein_rollup.py
"""Roll up peptide intensities to protein-level profiles.

Inputs
------
peptides : [peptide, sample] peptide intensity matrix
mapping  : [peptide, protein] binary peptide-to-protein membership

A peptide may map to more than one protein; its values contribute to
every mapped protein. The aggregation rule is explicit (sum/mean).
Peptides absent from the mapping are excluded and counted. This is the
standard rollup ambiguity, not a silent one-to-one assumption.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import axis_labels, labels_in_order, make_form, reorder, require_dims


class ProteinRollupStep(Step):
    name = "protein_rollup"
    title = "Peptide to protein rollup"
    category = "Proteomics"
    builtin_package = "biopipe-core"
    inputs_arity = 2
    outputs = []
    input_contracts = [
        port(ndim=2, dims=[param("peptide_dim", "peptide"), param("sample_dim", "sample")]),
        port(ndim=2, dims=[param("peptide_dim", "peptide"), param("protein_dim", "protein")]),
    ]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
        "info": {"missing_code": {"type": ["number", "null"]}}}}
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "peptide_dim": {"type": "string", "default": "peptide"},
            "sample_dim": {"type": "string", "default": "sample"},
            "protein_dim": {"type": "string", "default": "protein"},
            "method": {"type": "string", "enum": ["sum", "mean"], "default": "sum"},
            "min_peptides": {"type": "integer", "minimum": 1, "default": 1},
            "output": {"type": "string"},
        },
    }

    def run(self, ctx: Context, inputs) -> None:
        peptides, mapping = inputs
        peptide_dim = ctx.step_params.get("peptide_dim", "peptide")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        protein_dim = ctx.step_params.get("protein_dim", "protein")
        method = ctx.step_params.get("method", "sum")
        min_peptides = int(ctx.step_params.get("min_peptides", 1))
        out_name = ctx.step_params.get("output", self.name)
        require_dims(peptides, peptide_dim, sample_dim, label="peptides")
        require_dims(mapping, peptide_dim, protein_dim, label="mapping")
        if method not in ("sum", "mean"):
            raise StepError("protein_rollup: method must be 'sum' or 'mean'")
        if min_peptides < 1:
            raise StepError("protein_rollup: min_peptides must be >= 1")
        peptide_names = labels_in_order(peptides, peptide_dim)
        mapping_names = labels_in_order(mapping, peptide_dim)
        mapping_pos = {name: i for i, name in enumerate(mapping_names)}
        mapping_data = reorder(mapping, peptide_dim, protein_dim)
        peptide_data = reorder(peptides, peptide_dim, sample_dim)
        proteins = labels_in_order(mapping, protein_dim)
        rows = []
        kept = []
        missing = 0
        for i, peptide in enumerate(peptide_names):
            pos = mapping_pos.get(peptide)
            if pos is None:
                missing += 1
                continue
            rows.append(i)
            kept.append(pos)
        if not rows:
            raise StepError("protein_rollup: no peptide is present in the mapping")
        out = np.zeros((len(proteins), peptide_data.shape[1]), dtype=np.float64)
        counts = np.zeros(len(proteins), dtype=np.int64)
        for row, map_row in zip(rows, kept):
            targets = np.nonzero(mapping_data[map_row] > 0)[0]
            for target in targets:
                out[target] += peptide_data[row]
                counts[target] += 1
        if method == "mean":
            out = np.divide(out, counts[:, None], out=np.zeros_like(out), where=counts[:, None] > 0)
        keep = counts >= min_peptides
        if not keep.any():
            raise StepError(f"protein_rollup: no protein has at least {min_peptides} peptides")
        protein_names = [name for name, present in zip(proteins, keep) if present]
        out = out[keep]
        form = make_form(
            out, [protein_dim, sample_dim],
            {protein_dim: axis_labels(protein_names, protein_dim),
             sample_dim: dict(peptides.labels[sample_dim])},
        )
        ctx[out_name] = form
        self._export_data = {
            "proteins": len(protein_names), "peptides_used": len(rows),
            "peptides_missing_mapping": missing, "method": method,
            "min_peptides": min_peptides,
            "peptides_per_protein": {name: int(counts[i]) for i, name in enumerate(proteins) if keep[i]},
        }
        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "proteins": len(protein_names), "peptides_used": len(rows), "method": method,
        }

    def export(self, ctx: Context) -> dict:
        return self._export_data
