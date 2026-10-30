"""Translate DNA/RNA sequences to protein sequence codes."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.contracts import MISSING, param, port
from src.task.context import Context
from src.task.step.base import Step

from ._sequence_common import PROTEIN_MAP, decode_sequences, translate_sequence


class TranslateStep(Step):
    name = "translate"
    title = "Translate sequences"
    category = "Sequence"
    builtin_package = "biopipe-core"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sequence_dim", "sequence"), param("position_dim", "position")],
                            info={"representation": {"type": "string", "const": "sequence_codes"},
                                  "alphabet": {"type": "string", "enum": ["dna", "rna"]},
                                  "missing_code": MISSING})]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sequence_dim": {"type": "string", "default": "sequence"},
            "position_dim": {"type": "string", "default": "position"},
            "frame": {"type": "integer", "enum": [0, 1, 2], "default": 0},
            "to_stop": {"type": "boolean", "default": True},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        seq_dim = ctx.step_params.get("sequence_dim", "sequence")
        pos_dim = ctx.step_params.get("position_dim", "position")
        frame = int(ctx.step_params.get("frame", 0))
        to_stop = bool(ctx.step_params.get("to_stop", True))
        out_name = ctx.step_params.get("output", self.name)
        proteins = [translate_sequence(s, frame, to_stop) for s in decode_sequences(form, seq_dim, pos_dim)]
        max_len = max((len(p) for p in proteins), default=0)
        data = np.full((len(proteins), max_len), np.nan, dtype=np.float32)
        for i, protein in enumerate(proteins):
            for j, aa in enumerate(protein):
                data[i, j] = PROTEIN_MAP.get(aa, len(PROTEIN_MAP))
        labels = {
            seq_dim: dict(form.labels[seq_dim]),
            pos_dim: {str(i): i for i in range(max_len)},
        }
        info = {
            "missing_code": np.nan,
            "representation": "sequence_codes",
            "alphabet": "protein",
            "alphabet_map": dict(PROTEIN_MAP),
            "unknown_code": len(PROTEIN_MAP),
            "translation_frame": frame,
            "translated_to_stop": to_stop,
        }
        out = Form(data=data, dims=[seq_dim, pos_dim], labels=labels, info=info)
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_sequences": len(proteins), "frame": frame, "to_stop": to_stop,
                             "max_protein_length": max_len, "alphabet": "protein"}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
