"""Reverse-complement a DNA/RNA sequence-codes form."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import MISSING, param, port
from src.task.context import Context
from src.task.step.base import Step

from ._sequence_common import decode_sequences, reverse_complement


class ReverseComplementStep(Step):
    name = "reverse_complement"
    title = "Reverse complement"
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
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        seq_dim = ctx.step_params.get("sequence_dim", "sequence")
        pos_dim = ctx.step_params.get("position_dim", "position")
        out_name = ctx.step_params.get("output", self.name)
        alphabet = form.info.get("alphabet")
        if alphabet not in ("dna", "rna"):
            raise StepError(f"reverse_complement requires dna/rna, got {alphabet!r}")
        seqs = [reverse_complement(s, alphabet) for s in decode_sequences(form, seq_dim, pos_dim)]
        max_len = max((len(s) for s in seqs), default=0)
        data = np.full((len(seqs), max_len), np.nan, dtype=np.float32)
        amap = dict(form.info.get("alphabet_map", {}))
        unknown = int(form.info.get("unknown_code", 5))
        for i, seq in enumerate(seqs):
            for j, ch in enumerate(seq):
                data[i, j] = amap.get(ch, unknown)
        pos_labels = {str(i): i for i in range(max_len)}
        labels = {seq_dim: dict(form.labels[seq_dim]), pos_dim: pos_labels}
        info = dict(form.info)
        info.update(missing_code=np.nan, representation="sequence_codes", alphabet=alphabet)
        out = Form(data=data, dims=[seq_dim, pos_dim], labels=labels, info=info)
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_sequences": len(seqs), "alphabet": alphabet, "max_position": max_len}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
