"""Scan IUPAC motifs across any sequence-codes Form.

Input: any Form declaring info["representation"] == "sequence_codes"
with info["alphabet"] in {"dna","rna"}.

Motifs come in as {"name": "IUPAC-pattern"} and are matched on the
forward strand. Each window of the same length is compared using the
IUPAC convention:

    A C G T U -> single base
    R = A|G    Y = C|T    S = G|C    W = A|T
    K = G|T    M = A|C    B = C|G|T  D = A|G|T
    H = A|C|T  V = A|C|G  N = any

Output:
    data   2D float32, shape (n_motifs, n_sequences)
    dims   [motif, sequence]
    labels motif = user-supplied names, in insertion order
           sequence = input sequence labels

Counts include overlapping occurrences. Windows crossing N, unknown
codes or the NaN padding are skipped.

Params:
    sequence_dim : name of the sequence axis (default "sequence")
    position_dim : name of the position axis (default "position")
    motifs       : {"name": "IUPAC-string"} mapping (required)
    output       : context key for the result (default: step name)
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import MISSING, param, port
from src.core.forms.metadata import project_metadata
from src.task.context import Context
from src.task.step.base import Step


_IUPAC = {
    "A": "A", "C": "C", "G": "G", "T": "T", "U": "T",
    "R": "AG", "Y": "CT", "S": "GC", "W": "AT", "K": "GT", "M": "AC",
    "B": "CGT", "D": "AGT", "H": "ACT", "V": "ACG", "N": "ACGT",
}


class MotifScanStep(Step):
    """Count IUPAC motif occurrences per sequence."""
    title = 'motif_scan'
    description = 'Count IUPAC motif occurrences per sequence.'

    name = "motif_scan"
    category = "analysis"
    icon = "Funnel"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "sequence_dim": {"type": "string", "default": "sequence"},
            "position_dim": {"type": "string", "default": "position"},
            "motifs": {
                "type": "object",
                "minProperties": 1,
                "additionalProperties": {"type": "string", "minLength": 1},
            },
            "output": {"type": "string"},
        },
        "required": ["motifs"],
        "additionalProperties": False,
    }
    input_contracts = [port(
        ndim=2,
        dims=[param("sequence_dim", "sequence"),
              param("position_dim", "position")],
        info={
            "missing_code": MISSING,
            "representation": {"type": "string", "const": "sequence_codes"},
            "alphabet_map": {"type": "object"},
            "unknown_code": {"type": "integer"},
            "alphabet": {"type": "string", "enum": ["dna", "rna"]},
        },
    )]
    output_contract = {
        "mode": "declare",
        "schema": {
            "ndim": 2,
            "numeric": True,
            "info_open": True,
            "axis_info_open": True,
        },
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        seq_dim = ctx.step_params.get("sequence_dim", "sequence")
        pos_dim = ctx.step_params.get("position_dim", "position")
        motifs = ctx.step_params.get("motifs")
        out_name = ctx.step_params.get("output", self.name)

        if form.data.ndim != 2 or form.dims[0] != seq_dim or form.dims[1] != pos_dim:
            raise StepError(
                f"motif_scan: expected 2D [{seq_dim},{pos_dim}], got {form.dims}"
            )
        if not isinstance(motifs, dict) or not motifs:
            raise StepError("motif_scan: 'motifs' must be a non-empty mapping")

        alpha_map = form.info.get("alphabet_map")
        if not isinstance(alpha_map, dict):
            raise StepError(
                "motif_scan: input is not a sequence_codes Form "
                "(info.alphabet_map missing)"
            )
        alphabet = form.info.get("alphabet")
        if alphabet not in ("dna", "rna"):
            raise StepError(
                f"motif_scan: requires dna/rna, got alphabet={alphabet!r}"
            )

        code_to_base: dict[int, str] = {}
        for base, code in alpha_map.items():
            b = base.upper()
            if b == "U":
                b = "T"
            code_to_base.setdefault(int(code), b)

        motif_names = list(motifs.keys())
        motif_sets: list[list[set[str]]] = []
        for name in motif_names:
            pattern = motifs[name]
            if not isinstance(pattern, str) or not pattern:
                raise StepError(
                    f"motif_scan: motif '{name}' must be a non-empty string"
                )
            compiled: list[set[str]] = []
            for ch in pattern.upper():
                if ch in ("T", "U"):
                    compiled.append({"T"})
                elif ch in _IUPAC:
                    compiled.append(set(_IUPAC[ch]))
                else:
                    raise StepError(
                        f"motif_scan: motif '{name}' contains unknown IUPAC "
                        f"character {ch!r}"
                    )
            motif_sets.append(compiled)

        data = form.data
        n_seq = data.shape[0]
        out_data = np.zeros((len(motif_names), n_seq), dtype=np.float32)

        for s in range(n_seq):
            chain = self._decode_row(data[s], code_to_base)
            L = len(chain)
            if L == 0:
                continue
            for mi, compiled in enumerate(motif_sets):
                width = len(compiled)
                if width > L:
                    continue
                count = 0
                for i in range(L - width + 1):
                    ok = True
                    for j, allowed in enumerate(compiled):
                        if chain[i + j] not in allowed:
                            ok = False
                            break
                    if ok:
                        count += 1
                out_data[mi, s] = float(count)

        info, axis_info = project_metadata(
            form, keep_dims=[seq_dim], derived=True
        )
        info.pop("alphabet_map", None)
        info.pop("unknown_code", None)
        info["missing_code"] = np.nan
        info["representation"] = "motif_counts"
        info["alphabet"] = alphabet

        out_form = Form(
            data=out_data,
            dims=["motif", seq_dim],
            labels={
                "motif": {n: i for i, n in enumerate(motif_names)},
                seq_dim: dict(form.labels[seq_dim]),
            },
            info=info,
            axis_info=axis_info,
        )
        ctx[out_name] = out_form

        self._export_data = {
            "sequence_dim": seq_dim,
            "position_dim": pos_dim,
            "motifs": {n: motifs[n] for n in motif_names},
            "n_motifs": len(motif_names),
            "n_sequences": int(n_seq),
            "total_hits": float(out_data.sum()),
        }

        print(
            f"[motif_scan] {len(motif_names)} motifs x {n_seq} sequences, "
            f"total hits={int(out_data.sum())}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data

    @staticmethod
    def _decode_row(row, code_to_base):
        chars = []
        for v in row:
            if np.isnan(v):
                break
            base = code_to_base.get(int(round(float(v))))
            chars.append(base if base is not None else "N")
        return "".join(chars)
