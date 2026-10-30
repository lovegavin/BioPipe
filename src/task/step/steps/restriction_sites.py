"""Count restriction-enzyme recognition sites in DNA sequences."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import MISSING, param, port
from src.task.context import Context
from src.task.step.base import Step

from ._sequence_common import count_motif, decode_sequences, reverse_complement

_DEFAULT_ENZYMES = {
    "EcoRI": "GAATTC", "BamHI": "GGATCC", "HindIII": "AAGCTT",
    "NotI": "GCGGCCGC", "XhoI": "CTCGAG", "PstI": "CTGCAG",
    "SalI": "GTCGAC", "KpnI": "GGTACC", "SacI": "GAGCTC",
    "SmaI": "CCCGGG", "TaqI": "TCGA", "AluI": "AGCT",
}


class RestrictionSitesStep(Step):
    name = "restriction_sites"
    title = "Restriction sites"
    category = "Sequence"
    builtin_package = "biopipe-core"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sequence_dim", "sequence"), param("position_dim", "position")],
                            info={"representation": {"type": "string", "const": "sequence_codes"},
                                  "alphabet": {"type": "string", "enum": ["dna"]},
                                  "missing_code": MISSING})]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
                                                     "info": {"missing_code": {"type": ["number", "null"]}}}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sequence_dim": {"type": "string", "default": "sequence"},
            "position_dim": {"type": "string", "default": "position"},
            "enzymes": {"type": "object", "additionalProperties": {"type": "string"}, "default": dict(_DEFAULT_ENZYMES)},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        seq_dim = ctx.step_params.get("sequence_dim", "sequence")
        pos_dim = ctx.step_params.get("position_dim", "position")
        out_name = ctx.step_params.get("output", self.name)
        enzymes = ctx.step_params.get("enzymes") or dict(_DEFAULT_ENZYMES)
        if not isinstance(enzymes, dict) or not enzymes:
            raise StepError("enzymes must be a non-empty mapping name -> motif")
        for name, motif in enzymes.items():
            if not isinstance(motif, str) or not motif or set(motif.upper()) - set("ACGTN"):
                raise StepError(f"invalid motif for {name!r}: {motif!r}")
        seqs = decode_sequences(form, seq_dim, pos_dim)
        names = list(enzymes)
        data = np.zeros((len(seqs), len(names)), dtype=np.float32)
        for i, seq in enumerate(seqs):
            for j, name in enumerate(names):
                motif = enzymes[name].upper()
                rev = reverse_complement(motif, "dna")
                count = count_motif(seq, motif)
                if rev != motif:
                    count += count_motif(seq, rev)
                data[i, j] = count
        out = Form(
            data=data,
            dims=[seq_dim, "enzyme"],
            labels={seq_dim: dict(form.labels[seq_dim]), "enzyme": {name: i for i, name in enumerate(names)}},
            info={"missing_code": np.nan},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_sequences": len(seqs), "enzymes": names, "counts": data.tolist()}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
