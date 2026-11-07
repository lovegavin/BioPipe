"""rna_structure_consensus: ensemble consensus from RNAsubopt."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._rna_structure_utils import (
    clean_rna,
    consensus_structure,
    fold_structures,
    hamming_distance,
    pair_frequencies,
    subopt_structures,
)
from src.task.step.steps._sequence_common import decode_sequences


class RnaStructureConsensusStep(Step):
    provider = "operon-core"
    parameters_file = "rna_structure_consensus.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rna_structure_consensus",
        "version": "1.0.0",
        "kind": "operator",
        "title": "RNA 结构共识 (RNAsubopt 集合)",
        "description": (
            "Enumerate suboptimal structures with ViennaRNA RNAsubopt within an energy "
            "window, derive per-base-pair frequencies and a non-crossing consensus "
            "structure, and compare it with the minimum free energy structure."
        ),
        "category": "Sequence",
        "icon": "Repeat",
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
        return max(size * 4, 8 * 1024 * 1024), 1024 * 1024

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        if not isinstance(form, Form) or form.data.size == 0:
            raise StepError("rna_structure_consensus: the input form is empty")
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        sequences = [
            clean_rna(sequence, "rna_structure_consensus")
            for sequence in decode_sequences(form, sequence_dim, position_dim)
        ]
        binary = str(params.get("rnasubopt_path", "RNAsubopt"))
        temperature = float(params.get("temperature", 37.0))
        energy_window = float(params.get("energy_window", 3.0))
        max_structures = int(params.get("max_structures", 20))
        threshold = float(params.get("threshold", 0.5))
        if not 0.0 < threshold <= 1.0:
            raise StepError("rna_structure_consensus: threshold must be within (0, 1]")
        ensembles = subopt_structures(
            sequences,
            binary=binary,
            temperature=temperature,
            energy_window=energy_window,
            max_structures=max_structures,
            timeout=int(params.get("timeout_seconds", 600)),
        )
        mfe_structures = fold_structures(
            sequences,
            binary=str(params.get("rnafold_path", "RNAfold")),
            temperature=temperature,
            timeout=int(params.get("timeout_seconds", 600)),
        )
        names = self._names(form, sequence_dim)
        statistics = (
            "n_structures",
            "n_consensus_pairs",
            "mean_pair_probability",
            "coverage",
            "hamming_to_mfe",
        )
        rows = []
        consensus_texts = []
        for sequence, structures, mfe in zip(sequences, ensembles, mfe_structures):
            frequencies = pair_frequencies(structures, "rna_structure_consensus")
            consensus, pairs = consensus_structure(
                frequencies, len(sequence), threshold, "rna_structure_consensus"
            )
            probability = float(np.mean([frequencies[pair] for pair in pairs])) if pairs else 0.0
            coverage = 2.0 * len(pairs) / max(len(sequence), 1)
            hamming = hamming_distance(consensus, mfe, "rna_structure_consensus")
            rows.append((len(structures), len(pairs), probability, coverage, hamming))
            consensus_texts.append(consensus)
        values = np.asarray(rows, dtype=np.float32)
        out_dim = str(params.get("sequence_output_dim", "sequence"))
        out_name = str(params.get("output", "consensus"))
        ctx[out_name] = Form(
            data=values,
            dims=[out_dim, "statistic"],
            labels={
                out_dim: {name: index for index, name in enumerate(names)},
                "statistic": {stat: index for index, stat in enumerate(statistics)},
            },
            info={
                "missing_code": np.nan,
                "n_sequences": len(sequences),
                "energy_window": energy_window,
                "max_structures": max_structures,
                "threshold": threshold,
                "consensus": consensus_texts,
                "mfe_structures": mfe_structures,
                "mean_consensus_pairs": float(values[:, 1].mean()),
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
