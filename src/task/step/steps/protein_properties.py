"""Physicochemical properties of protein sequences."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.contracts import MISSING, param, port
from src.task.context import Context
from src.task.step.base import Step

from ._sequence_common import decode_sequences

_MW = {
    "A": 89.09, "R": 174.20, "N": 132.12, "D": 133.10, "C": 121.16,
    "E": 147.13, "Q": 146.15, "G": 75.07, "H": 155.16, "I": 131.17,
    "L": 131.17, "K": 146.19, "M": 149.21, "F": 165.19, "P": 115.13,
    "S": 105.09, "T": 119.12, "W": 204.23, "Y": 181.19, "V": 117.15,
}
_GRAVY = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5, "E": -3.5,
    "Q": -3.5, "G": -0.4, "H": -3.2, "I": 4.5, "L": 3.8, "K": -3.9,
    "M": 1.9, "F": 2.8, "P": -1.6, "S": -0.8, "T": -0.7, "W": -0.9,
    "Y": -1.3, "V": 4.2,
}
_PKA = {"C": 8.18, "D": 3.65, "E": 4.25, "H": 6.0, "K": 10.53, "R": 12.5, "Y": 10.07}
_NTERM = 9.69
_CTERM = 2.34


def _charge(seq: str, ph: float) -> float:
    charge = 0.0
    for aa in seq:
        if aa == "D":
            charge -= 1.0 / (1.0 + 10 ** (_PKA["D"] - ph))
        elif aa == "E":
            charge -= 1.0 / (1.0 + 10 ** (_PKA["E"] - ph))
        elif aa == "C":
            charge -= 1.0 / (1.0 + 10 ** (_PKA["C"] - ph))
        elif aa == "Y":
            charge -= 1.0 / (1.0 + 10 ** (_PKA["Y"] - ph))
        elif aa == "H":
            charge += 1.0 / (1.0 + 10 ** (ph - _PKA["H"]))
        elif aa == "K":
            charge += 1.0 / (1.0 + 10 ** (ph - _PKA["K"]))
        elif aa == "R":
            charge += 1.0 / (1.0 + 10 ** (ph - _PKA["R"]))
    charge += 1.0 / (1.0 + 10 ** (ph - _NTERM))
    charge -= 1.0 / (1.0 + 10 ** (_CTERM - ph))
    return charge


def _isoelectric(seq: str) -> float:
    lo, hi = 0.0, 14.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if _charge(seq, mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


class ProteinPropertiesStep(Step):
    name = "protein_properties"
    title = "Protein properties"
    category = "Sequence"
    builtin_package = "biopipe-core"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sequence_dim", "sequence"), param("position_dim", "position")],
                            info={"representation": {"type": "string", "const": "sequence_codes"},
                                  "alphabet": {"type": "string", "const": "protein"},
                                  "missing_code": MISSING})]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
                                                     "info": {"missing_code": {"type": ["number", "null"]}}}}
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
        seqs = decode_sequences(form, seq_dim, pos_dim)
        rows = []
        for seq in seqs:
            clean = "".join(aa for aa in seq if aa in _MW)
            n = len(clean)
            mw = sum(_MW[aa] for aa in clean) + (18.01524 if n else 0.0)
            gravy = (sum(_GRAVY[aa] for aa in clean) / n) if n else float("nan")
            aromatic = (sum(1 for aa in clean if aa in "FWY") / n) if n else float("nan")
            rows.append([float(n), float(mw), float(_isoelectric(clean) if clean else 7.0), float(gravy), float(aromatic)])
        data = np.asarray(rows, dtype=np.float32)
        out = Form(
            data=data,
            dims=[seq_dim, "statistic"],
            labels={seq_dim: dict(form.labels[seq_dim]),
                    "statistic": {"length": 0, "molecular_weight": 1, "isoelectric_point": 2,
                                  "gravy": 3, "aromaticity": 4}},
            info={"missing_code": np.nan},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_sequences": len(seqs), "statistics": ["length", "molecular_weight",
                                                                     "isoelectric_point", "gravy", "aromaticity"]}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
