"""Nearest-neighbour melting temperature for primers and oligos."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._annotation_utils import fasta_sequences
from ._primer_utils import clean_sequence, gc_fraction, tm_nn

_STATISTICS = ("length", "gc_fraction", "tm", "delta_h", "delta_s")


class PrimerTmStep(Step):
    provider = "operon-core"
    parameters_file = "primer_tm.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "primer_tm",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Primer melting temperature",
        "description": (
            "Compute nearest-neighbour melting temperatures (SantaLucia 1998) "
            "with an entropy salt correction, plus GC fraction and the "
            "enthalpy/entropy terms for each input oligo."
        ),
        "category": "Sequence",
        "icon": "Thermometer",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "sequence_dim", "default": "sequence"},
                        {"param": "position_dim", "default": "position"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                    "info": {"representation": {"type": "string", "const": "sequence_codes"}},
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = int(getattr(inputs[0], "data", np.empty(0)).nbytes) if inputs else 0
        return max(size * 2, 8 * 2**20), size

    def run(self, ctx: Context, inputs) -> None:
        if not inputs:
            raise StepError("primer_tm: a FASTA input is required")
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        taxon_dim = str(params.get("sequence_label_dim", "sequence"))
        statistic_dim = str(params.get("statistic_dim", "statistic"))
        out_name = str(params.get("output", self.name))
        na_mm = float(params.get("na_mm", 50.0))
        dnac_nm = float(params.get("dnac_nm", 25.0))

        names, sequences = fasta_sequences(inputs[0], sequence_dim, position_dim, "primer_tm")
        if not sequences:
            raise StepError("primer_tm: the FASTA input is empty")
        rows = []
        for name, raw in zip(names, sequences):
            sequence = clean_sequence(raw, "primer_tm")
            if "N" in sequence:
                raise StepError(f"primer_tm: {name!r} contains ambiguous bases")
            tm, delta_h, delta_s = tm_nn(sequence, na_mm=na_mm, dnac_nm=dnac_nm)
            rows.append([len(sequence), gc_fraction(sequence), tm, delta_h, delta_s])
        matrix = np.asarray(rows, dtype=np.float64)
        form = Form(
            matrix,
            dims=[taxon_dim, statistic_dim],
            labels={
                taxon_dim: {name: index for index, name in enumerate(names)},
                statistic_dim: {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "method": "santalucia-1998",
                "salt_correction": "entropy",
                "na_mm": na_mm,
                "dnac_nm": dnac_nm,
                "n_sequences": len(names),
            },
        )
        ctx[out_name] = form
        self._export_data = {
            "n_sequences": len(names),
            "na_mm": na_mm,
            "dnac_nm": dnac_nm,
            "mean_tm": float(matrix[:, 2].mean()),
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
