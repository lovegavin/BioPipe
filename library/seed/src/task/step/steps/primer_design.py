"""Design primer pairs flanking a target interval on a template sequence."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._annotation_utils import fasta_sequences
from ._primer_utils import clean_sequence, gc_fraction, tm_nn

_COLUMNS = (
    "left_start", "left_end", "right_start", "right_end",
    "left_length", "right_length",
    "left_tm", "right_tm", "left_gc", "right_gc",
    "product_size", "penalty",
)


def _candidates(
    template: str,
    starts,
    params: dict,
):
    min_len = int(params["min_length"])
    max_len = int(params["max_length"])
    min_tm = float(params["min_tm"])
    max_tm = float(params["max_tm"])
    min_gc = float(params["min_gc"])
    max_gc = float(params["max_gc"])
    na_mm = float(params["na_mm"])
    dnac_nm = float(params["dnac_nm"])
    rows = []
    for start in starts:
        for length in range(min_len, max_len + 1):
            end = start + length
            if end > len(template):
                continue
            sequence = template[start:end]
            fraction = gc_fraction(sequence) * 100.0
            if fraction < min_gc or fraction > max_gc:
                continue
            tm, _, _ = tm_nn(sequence, na_mm=na_mm, dnac_nm=dnac_nm)
            if tm < min_tm or tm > max_tm:
                continue
            rows.append((start, end, length, sequence, tm, fraction))
    return rows


class PrimerDesignStep(Step):
    provider = "operon-core"
    parameters_file = "primer_design.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "primer_design",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Primer pair design",
        "description": (
            "Enumerate primer pairs flanking a target interval, filter by "
            "length, melting temperature and GC content, and rank pairs by a "
            "weighted penalty on Tm, length, GC and product size."
        ),
        "category": "Sequence",
        "icon": "Flask",
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
        return max(size * 2, 16 * 2**20), size

    def run(self, ctx: Context, inputs) -> None:
        if not inputs:
            raise StepError("primer_design: a template FASTA input is required")
        params = dict(ctx.step_params)
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        pair_dim = str(params.get("pair_dim", "pair"))
        statistic_dim = str(params.get("statistic_dim", "statistic"))
        out_name = str(params.get("output", self.name))

        names, sequences = fasta_sequences(inputs[0], sequence_dim, position_dim, "primer_design")
        if len(sequences) != 1:
            raise StepError(
                f"primer_design: exactly one template sequence is required, got {len(sequences)}"
            )
        template = clean_sequence(sequences[0], "primer_design")
        if "N" in template:
            raise StepError("primer_design: the template contains ambiguous bases")

        target_start = int(params.get("target_start", 1))
        target_end = int(params.get("target_end", len(template)))
        if not (1 <= target_start <= target_end <= len(template)):
            raise StepError("primer_design: target interval is outside the template")
        flank = int(params.get("flank", 200))
        min_product = int(params.get("min_product", 100))
        max_product = int(params.get("max_product", 300))
        max_pairs = int(params.get("max_pairs", 10))

        left_starts = range(max(0, target_start - 1 - flank - int(params["max_length"])),
                            target_start - 1)
        right_starts = range(target_end,
                             min(len(template) - int(params["min_length"]),
                                 target_end - 1 + flank) + 1)
        lefts = _candidates(template, left_starts, params)
        rights = _candidates(template, right_starts, params)
        if not lefts or not rights:
            raise StepError("primer_design: no candidate primer passed the filters")

        tm_weight = float(params.get("tm_weight", 3.0))
        length_weight = float(params.get("length_weight", 1.0))
        gc_weight = float(params.get("gc_weight", 0.5))
        product_weight = float(params.get("product_weight", 0.1))
        opt_len = float(params.get("opt_length", 20))
        opt_tm = float(params.get("opt_tm", 60.0))
        opt_product = float(params.get("opt_product", 150))

        scored = []
        for left in lefts:
            l_start, l_end, l_len, l_seq, l_tm, l_gc = left
            for right in rights:
                r_start, r_end, r_len, r_seq, r_tm, r_gc = right
                product = r_end - l_start
                if product < min_product or product > max_product:
                    continue
                penalty = (
                    tm_weight * (abs(l_tm - opt_tm) + abs(r_tm - opt_tm))
                    + length_weight * (abs(l_len - opt_len) + abs(r_len - opt_len))
                    + gc_weight * (abs(l_gc - 50.0) + abs(r_gc - 50.0))
                    + product_weight * abs(product - opt_product)
                )
                scored.append((
                    penalty, l_start, l_end, r_start, r_end, l_len, r_len,
                    l_tm, r_tm, l_gc, r_gc, product, l_seq, r_seq,
                ))
        if not scored:
            raise StepError("primer_design: no primer pair satisfies the product-size window")
        scored.sort(key=lambda item: (item[0], item[11], item[1]))
        chosen = scored[:max_pairs]

        matrix = np.asarray(
            [
                [l_start + 1, l_end, r_start + 1, r_end, l_len, r_len,
                 l_tm, r_tm, l_gc / 100.0, r_gc / 100.0, product, penalty]
                for penalty, l_start, l_end, r_start, r_end, l_len, r_len,
                    l_tm, r_tm, l_gc, r_gc, product, _l, _r in chosen
            ],
            dtype=np.float64,
        )
        form = Form(
            matrix,
            dims=[pair_dim, statistic_dim],
            labels={
                pair_dim: {f"pair_{index + 1}": index for index in range(len(chosen))},
                statistic_dim: {name: index for index, name in enumerate(_COLUMNS)},
            },
            info={
                "template": names[0],
                "template_length": len(template),
                "target_start": target_start,
                "target_end": target_end,
                "n_pairs": len(chosen),
                "pairs": [
                    {
                        "left_sequence": l_seq,
                        "right_sequence": r_seq,
                        "left_tm": round(l_tm, 6),
                        "right_tm": round(r_tm, 6),
                        "product_size": int(product),
                    }
                    for penalty, l_start, l_end, r_start, r_end, l_len, r_len,
                        l_tm, r_tm, l_gc, r_gc, product, l_seq, r_seq in chosen
                ],
            },
        )
        ctx[out_name] = form
        self._export_data = {
            "n_pairs": len(chosen),
            "best_product": int(chosen[0][11]),
            "best_penalty": float(chosen[0][0]),
            "best_left_tm": float(chosen[0][7]),
            "best_right_tm": float(chosen[0][8]),
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
