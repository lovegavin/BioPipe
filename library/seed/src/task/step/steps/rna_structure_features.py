"""rna_structure_features: secondary-structure motif counts."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._rna_structure_utils import (
    clean_rna,
    fold_structures,
    structure_features,
)
from src.task.step.steps._sequence_common import decode_sequences

_STATISTICS = (
    "n_pairs",
    "n_stems",
    "max_stem_length",
    "n_hairpins",
    "n_bulges",
    "n_internal_loops",
    "n_multiloops",
    "n_stacked_pairs",
    "n_unpaired",
)


class RnaStructureFeaturesStep(Step):
    provider = "operon-core"
    parameters_file = "rna_structure_features.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rna_structure_features",
        "version": "1.0.0",
        "kind": "operator",
        "title": "RNA 二级结构特征 (环与茎)",
        "description": (
            "Fold each RNA with ViennaRNA RNAfold and count base pairs, stems, the "
            "longest stem, hairpins, bulges, internal loops, multiloops, stacked pairs "
            "and unpaired positions."
        ),
        "category": "Sequence",
        "icon": "Grid3x3",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {
            "memory_modes": ["full"],
            "estimate": "estimate_memory",
            "external_tools": ["viennarna"],
        },
        "dependencies": [],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, "data", np.empty(0)).nbytes) for item in inputs)
        return max(size * 3, 8 * 1024 * 1024), 1024 * 1024

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        if not isinstance(form, Form) or form.data.size == 0:
            raise StepError("rna_structure_features: the input form is empty")
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        sequences = [
            clean_rna(sequence, "rna_structure_features")
            for sequence in decode_sequences(form, sequence_dim, position_dim)
        ]
        structures = fold_structures(
            sequences,
            binary=str(params.get("rnafold_path", "RNAfold")),
            temperature=float(params.get("temperature", 37.0)),
            dangles=int(params.get("dangles", 2)),
            timeout=int(params.get("timeout_seconds", 600)),
        )
        names = self._names(form, sequence_dim)
        rows = []
        for structure in structures:
            features = structure_features(structure, "rna_structure_features")
            rows.append([features[stat] for stat in _STATISTICS])
        values = np.asarray(rows, dtype=np.float32)
        out_dim = str(params.get("sequence_output_dim", "structure"))
        out_name = str(params.get("output", "features"))
        ctx[out_name] = Form(
            data=values,
            dims=[out_dim, "statistic"],
            labels={
                out_dim: {name: index for index, name in enumerate(names)},
                "statistic": {stat: index for index, stat in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "n_structures": len(structures),
                "structures": structures,
                "consensus": [structure_features(item, "rna_structure_features")["n_pairs"] for item in structures],
            },
        )
        self._export_rows = rows

    @staticmethod
    def _names(form: Form, dim: str) -> list[str]:
        labels = form.labels.get(dim, {})
        if isinstance(labels, dict) and labels:
            return [str(key) for key, _ in sorted(labels.items(), key=lambda item: item[1])]
        return [f"seq{index + 1}" for index in range(form.data.shape[0])]

    def export(self, ctx):
        return {"n_structures": len(getattr(self, "_export_rows", [])), "statistics": list(_STATISTICS)}
