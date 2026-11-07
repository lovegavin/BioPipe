"""rna_structure_distance: compare RNA folds at two temperatures."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._rna_structure_utils import (
    base_pair_distance,
    clean_rna,
    fold_structures,
    hamming_distance,
    pairs_of,
)
from src.task.step.steps._sequence_common import decode_sequences


class RnaStructureDistanceStep(Step):
    provider = "operon-core"
    parameters_file = "rna_structure_distance.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rna_structure_distance",
        "version": "1.0.0",
        "kind": "operator",
        "title": "RNA 二级结构距离 (RNAfold 双温度)",
        "description": (
            "Fold each RNA with ViennaRNA RNAfold at two temperatures and report the "
            "base-pair distance, shared and union pairs, Hamming distance and the "
            "normalised base-pair distance between the two structures."
        ),
        "category": "Sequence",
        "icon": "GitCompare",
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
            raise StepError("rna_structure_distance: the input form is empty")
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        sequences = [
            clean_rna(sequence, "rna_structure_distance")
            for sequence in decode_sequences(form, sequence_dim, position_dim)
        ]
        temperature_a = float(params.get("temperature_a", 37.0))
        temperature_b = float(params.get("temperature_b", 50.0))
        if temperature_a == temperature_b:
            raise StepError("rna_structure_distance: temperature_a and temperature_b must differ")
        binary = str(params.get("rnafold_path", "RNAfold"))
        dangles = int(params.get("dangles", 2))
        timeout = int(params.get("timeout_seconds", 600))
        structures_a = fold_structures(
            sequences, binary=binary, temperature=temperature_a, dangles=dangles, timeout=timeout
        )
        structures_b = fold_structures(
            sequences, binary=binary, temperature=temperature_b, dangles=dangles, timeout=timeout
        )
        statistics = (
            "bp_distance",
            "shared_pairs",
            "union_pairs",
            "hamming_distance",
            "normalized_bp_distance",
        )
        rows = []
        for name, left, right in zip(self._names(form, sequence_dim), structures_a, structures_b):
            pairs_left = set(pairs_of(left, "rna_structure_distance"))
            pairs_right = set(pairs_of(right, "rna_structure_distance"))
            shared = len(pairs_left & pairs_right)
            union = len(pairs_left | pairs_right)
            distance = base_pair_distance(left, right, "rna_structure_distance")
            hamming = hamming_distance(left, right, "rna_structure_distance")
            normalised = distance / union if union else 0.0
            rows.append((distance, shared, union, hamming, normalised))
        values = np.asarray(rows, dtype=np.float32)
        out_dim = str(params.get("sequence_output_dim", "pair"))
        out_name = str(params.get("output", "distances"))
        ctx[out_name] = Form(
            data=values,
            dims=[out_dim, "statistic"],
            labels={
                out_dim: {name: index for index, name in enumerate(self._names(form, sequence_dim))},
                "statistic": {stat: index for index, stat in enumerate(statistics)},
            },
            info={
                "missing_code": np.nan,
                "n_sequences": len(sequences),
                "temperature_a": temperature_a,
                "temperature_b": temperature_b,
                "structures_a": structures_a,
                "structures_b": structures_b,
                "mean_bp_distance": float(values[:, 0].mean()),
                "mean_hamming_distance": float(values[:, 3].mean()),
            },
        )
        self._export_rows = rows
        self._export_statistics = statistics

    @staticmethod
    def _names(form: Form, dim: str) -> list[str]:
        labels = form.labels.get(dim, {})
        if isinstance(labels, dict) and labels:
            return [str(key) for key, _ in sorted(labels.items(), key=lambda item: item[1])]
        return [f"seq{index + 1}" for index in range(form.data.shape[0])]

    def export(self, ctx):
        return {
            "n_sequences": len(getattr(self, "_export_rows", [])),
            "statistics": list(getattr(self, "_export_statistics", ())),
        }
