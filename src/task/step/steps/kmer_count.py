# src/task/step/steps/kmer_count.py
"""k-mer counts per sequence for any sequence-codes Form.

Input: any Form declaring info["representation"] == "sequence_codes"
with info["alphabet"] in {"dna","rna"}. The character-to-code mapping
comes from info["alphabet_map"], so the operator works with any reader
declaring the same convention.

Output:
    data   2D float32, shape (n_kmers, n_sequences)
    dims   [kmer, sequence]
    labels kmer = every A/C/G/T word of length k, in lexicographic order
           sequence = the input's sequence labels

Only fully A/C/G/T windows are counted. Windows containing N or any
other code are skipped. Different sequence lengths are handled by the
input's NaN padding; windows that would extend past the last defined
position are skipped.

Params:
    sequence_dim : name of the sequence axis (default "sequence")
    position_dim : name of the position axis (default "position")
    k            : word length, 1..6 (default 3)
    output       : context key for the result (default: step name)
"""
from __future__ import annotations

from itertools import product

import numpy as np

from src.core import Form, StepError
from src.core.contracts import MISSING, param, port
from src.core.forms.metadata import project_metadata
from src.task.context import Context
from src.task.step.base import Step


_BASES = ("A", "C", "G", "T")


class KmerCountStep(Step):
    """Count k-mers per sequence for any sequence-codes Form."""
    title = 'kmer_count'
    description = 'Count k-mers per sequence for any sequence-codes Form.'

    name = "kmer_count"
    category = "analysis"
    icon = "Function"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "sequence_dim": {"type": "string", "default": "sequence"},
            "position_dim": {"type": "string", "default": "position"},
            "k": {"type": "integer", "minimum": 1, "maximum": 6, "default": 3},
            "output": {"type": "string"},
        },
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
        k = int(ctx.step_params.get("k", 3))
        out_name = ctx.step_params.get("output", self.name)

        if form.data.ndim != 2 or form.dims[0] != seq_dim or form.dims[1] != pos_dim:
            raise StepError(
                f"kmer_count: expected 2D [{seq_dim},{pos_dim}], got {form.dims}"
            )
        if k < 1 or k > 6:
            raise StepError(f"kmer_count: k must be in 1..6, got {k}")

        alpha_map = form.info.get("alphabet_map")
        if not isinstance(alpha_map, dict):
            raise StepError(
                "kmer_count: input is not a sequence_codes Form "
                "(info.alphabet_map missing)"
            )
        alphabet = form.info.get("alphabet")
        if alphabet not in ("dna", "rna"):
            raise StepError(
                f"kmer_count: requires dna/rna, got alphabet={alphabet!r}"
            )

        base_codes: dict[str, int] = {}
        for ch in _BASES:
            if ch not in alpha_map:
                raise StepError(
                    f"kmer_count: alphabet_map missing code for '{ch}'"
                )
            base_codes[ch] = int(alpha_map[ch])
        code_to_base = {v: ch for ch, v in base_codes.items()}

        kmers = ["".join(p) for p in product(_BASES, repeat=k)]
        kmer_index = {km: i for i, km in enumerate(kmers)}

        data = form.data
        n_seq, max_len = data.shape
        out_data = np.zeros((len(kmers), n_seq), dtype=np.float32)

        for s in range(n_seq):
            row = data[s]
            valid = ~np.isnan(row)
            if not valid.any():
                continue
            last = int(np.where(valid)[0].max())
            seq = row[: last + 1]
            n_windows = len(seq) - k + 1
            if n_windows <= 0:
                continue
            for i in range(n_windows):
                window = seq[i : i + k]
                chars = []
                ok = True
                for value in window:
                    code = int(round(float(value)))
                    ch = code_to_base.get(code)
                    if ch is None:
                        ok = False
                        break
                    chars.append(ch)
                if ok:
                    kmer = "".join(chars)
                    out_data[kmer_index[kmer], s] += 1.0

        info, axis_info = project_metadata(
            form, keep_dims=[seq_dim], derived=True
        )
        info.pop("alphabet_map", None)
        info.pop("unknown_code", None)
        info["missing_code"] = np.nan
        info["representation"] = "kmer_counts"
        info["k"] = k

        out_form = Form(
            data=out_data,
            dims=["kmer", seq_dim],
            labels={
                "kmer": {km: i for i, km in enumerate(kmers)},
                seq_dim: dict(form.labels[seq_dim]),
            },
            info=info,
            axis_info=axis_info,
        )
        ctx[out_name] = out_form

        total = float(out_data.sum())
        self._export_data = {
            "sequence_dim": seq_dim,
            "position_dim": pos_dim,
            "k": k,
            "n_kmers": len(kmers),
            "n_sequences": int(n_seq),
            "total_windows_counted": total,
        }

        print(
            f"[kmer_count] k={k}, {len(kmers)} kmers x {n_seq} sequences, "
            f"total counted={int(total)}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data