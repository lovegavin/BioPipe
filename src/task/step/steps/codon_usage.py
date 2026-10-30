"""Codon counts and frequencies from CDS sequences."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.contracts import MISSING, param, port
from src.task.context import Context
from src.task.step.base import Step

from ._sequence_common import CODON_TABLE, decode_sequences


class CodonUsageStep(Step):
    name = "codon_usage"
    title = "Codon usage"
    category = "Sequence"
    builtin_package = "biopipe-core"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sequence_dim", "sequence"), param("position_dim", "position")],
                            info={"representation": {"type": "string", "const": "sequence_codes"},
                                  "alphabet": {"type": "string", "enum": ["dna", "rna"]},
                                  "missing_code": MISSING})]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
                                                     "info": {"missing_code": {"type": ["number", "null"]}}}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sequence_dim": {"type": "string", "default": "sequence"},
            "position_dim": {"type": "string", "default": "position"},
            "frame": {"type": "integer", "enum": [0, 1, 2], "default": 0},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        seq_dim = ctx.step_params.get("sequence_dim", "sequence")
        pos_dim = ctx.step_params.get("position_dim", "position")
        frame = int(ctx.step_params.get("frame", 0))
        out_name = ctx.step_params.get("output", self.name)
        codons = sorted(CODON_TABLE)
        counts = {c: 0 for c in codons}
        for seq in decode_sequences(form, seq_dim, pos_dim):
            seq = seq.upper().replace("U", "T")
            for i in range(frame, len(seq) - 2, 3):
                codon = seq[i:i + 3]
                if codon in counts:
                    counts[codon] += 1
        total = sum(counts.values())
        data = np.array([[counts[c], (counts[c] / total if total else 0.0)] for c in codons], dtype=np.float32)
        out = Form(
            data=data,
            dims=["codon", "statistic"],
            labels={"codon": {c: i for i, c in enumerate(codons)},
                    "statistic": {"count": 0, "frequency": 1}},
            info={"missing_code": np.nan},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_codons": total, "frame": frame, "n_codons_types": len(codons)}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
