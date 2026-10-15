# src/task/step/steps/find_orfs.py
"""Find complete ORFs (ATG..stop) in any sequence-codes Form.

Input: any Form declaring info["representation"] == "sequence_codes"
with info["alphabet"] in {"dna","rna"}.

Output:
    data   2D float32, shape (n_orfs, 6)
    dims   [orf, statistic]
    statistic = [strand, frame, start, end, length_nt, length_aa]
    info["sequence"] is axis-parallel to "orf", naming each ORF's
        source sequence label.

Both strands are scanned. Forward strand uses strand=+1; the reverse
complement uses strand=-1. For each chain, frames 0,1,2 start the
codon grid at that offset. From every ATG, the first in-frame stop
(TAA/TAG/TGA) closes an ORF. start and end are 0-based positions on
the chain that strand refers to; end is the last base of the stop
codon, so length_nt == end - start + 1 and length_aa == length_nt/3 - 1.

Params:
    sequence_dim : name of the sequence axis (default "sequence")
    position_dim : name of the position axis (default "position")
    min_aa       : minimum amino-acid count (default 1)
    output       : context key for the result (default: step name)
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import MISSING, param, port
from src.core.forms.metadata import project_metadata
from src.task.context import Context
from src.task.step.base import Step


_STAT_LABELS = ("strand", "frame", "start", "end", "length_nt", "length_aa")
_STOPS = ("TAA", "TAG", "TGA")


def _revcomp(seq: str) -> str:
    out = []
    for ch in reversed(seq):
        if ch == "A":
            out.append("T")
        elif ch == "C":
            out.append("G")
        elif ch == "G":
            out.append("C")
        elif ch in ("T", "U"):
            out.append("A")
        else:
            out.append("N")
    return "".join(out)


class FindOrfsStep(Step):
    """Locate complete ATG..stop ORFs on both strands."""

    name = "find_orfs"
    category = "analysis"
    icon = "Intersect"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "sequence_dim": {"type": "string", "default": "sequence"},
            "position_dim": {"type": "string", "default": "position"},
            "min_aa": {"type": "integer", "minimum": 1, "default": 1},
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
        min_aa = int(ctx.step_params.get("min_aa", 1))
        out_name = ctx.step_params.get("output", self.name)

        if form.data.ndim != 2 or form.dims[0] != seq_dim or form.dims[1] != pos_dim:
            raise StepError(
                f"find_orfs: expected 2D [{seq_dim},{pos_dim}], got {form.dims}"
            )
        if min_aa < 1:
            raise StepError(f"find_orfs: min_aa must be >= 1, got {min_aa}")

        alpha_map = form.info.get("alphabet_map")
        if not isinstance(alpha_map, dict):
            raise StepError(
                "find_orfs: input is not a sequence_codes Form "
                "(info.alphabet_map missing)"
            )
        alphabet = form.info.get("alphabet")
        if alphabet not in ("dna", "rna"):
            raise StepError(
                f"find_orfs: requires dna/rna, got alphabet={alphabet!r}"
            )

        code_to_base: dict[int, str] = {}
        for base, code in alpha_map.items():
            base_up = base.upper()
            if base_up == "U":
                base_up = "T"
            code_to_base.setdefault(int(code), base_up)

        data = form.data
        n_seq = data.shape[0]

        seq_labels_in_order = sorted(
            form.labels[seq_dim].items(), key=lambda kv: kv[1]
        )

        rows: list[tuple[float, ...]] = []
        orf_sequences: list[str] = []

        for s in range(n_seq):
            chain_fwd = self._decode_row(data[s], code_to_base)
            chain_rev = _revcomp(chain_fwd)

            for strand, chain in ((+1, chain_fwd), (-1, chain_rev)):
                for frame in range(3):
                    for start, end, length_nt, length_aa in self._scan(chain, frame):
                        if length_aa < min_aa:
                            continue
                        rows.append((
                            float(strand),
                            float(frame),
                            float(start),
                            float(end),
                            float(length_nt),
                            float(length_aa),
                        ))
                        orf_sequences.append(seq_labels_in_order[s][0])

        if rows:
            out_data = np.asarray(rows, dtype=np.float32)
        else:
            out_data = np.zeros((0, len(_STAT_LABELS)), dtype=np.float32)

        info, axis_info = project_metadata(form, keep_dims=[], derived=True)
        info.pop("alphabet_map", None)
        info.pop("unknown_code", None)
        info["missing_code"] = np.nan
        info["representation"] = "orfs"
        info["alphabet"] = alphabet
        info["sequence"] = list(orf_sequences)

        axis_info = dict(axis_info)
        axis_info["orf"] = ["sequence"]

        out_form = Form(
            data=out_data,
            dims=["orf", "statistic"],
            labels={
                "orf": {str(i): i for i in range(len(rows))},
                "statistic": {n: i for i, n in enumerate(_STAT_LABELS)},
            },
            info=info,
            axis_info=axis_info,
        )
        ctx[out_name] = out_form

        self._export_data = {
            "sequence_dim": seq_dim,
            "position_dim": pos_dim,
            "min_aa": min_aa,
            "alphabet": alphabet,
            "n_sequences": int(n_seq),
            "n_orfs": len(rows),
        }

        print(
            f"[find_orfs] {n_seq} sequences, {len(rows)} complete ORFs "
            f"(min_aa={min_aa})"
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

    @staticmethod
    def _scan(chain, frame):
        L = len(chain)
        i = frame
        while i + 3 <= L:
            codon = chain[i : i + 3]
            if codon == "ATG":
                j = i + 3
                stop_at = None
                while j + 3 <= L:
                    if chain[j : j + 3] in _STOPS:
                        stop_at = j
                        break
                    j += 3
                if stop_at is not None:
                    length_nt = stop_at + 3 - i
                    length_aa = length_nt // 3 - 1
                    yield i, stop_at + 2, length_nt, length_aa
                    i = stop_at + 3
                    continue
            i += 3