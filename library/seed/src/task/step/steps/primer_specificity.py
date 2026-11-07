"""In-silico PCR: locate primer-pair amplicons in a genome."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._annotation_utils import fasta_sequences
from ._primer_utils import clean_sequence, reverse_complement, scan_hits

_COLUMNS = (
    "record_index", "start", "end", "strand",
    "forward_mismatches", "reverse_mismatches", "product_size",
)


class PrimerSpecificityStep(Step):
    provider = "operon-core"
    parameters_file = "primer_specificity.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "primer_specificity",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Primer specificity (in-silico PCR)",
        "description": (
            "Search a genome for amplicons produced by a primer pair on both "
            "strands, allowing a bounded number of mismatches per primer, and "
            "report every product within the configured size window."
        ),
        "category": "Sequence",
        "icon": "MagnifyingGlass",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "primer_dim", "default": "sequence"},
                        {"param": "position_dim", "default": "position"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                    "info": {"representation": {"type": "string", "const": "sequence_codes"}},
                },
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
                },
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
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = int(getattr(inputs[1], "data", np.empty(0)).nbytes) if len(inputs) > 1 else 0
        return max(size * 6, 32 * 2**20), size

    def run(self, ctx: Context, inputs) -> None:
        if len(inputs) < 2:
            raise StepError("primer_specificity: primer and genome inputs are required")
        params = dict(ctx.step_params)
        primer_dim = str(params.get("primer_dim", "sequence"))
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        amplicon_dim = str(params.get("amplicon_dim", "amplicon"))
        statistic_dim = str(params.get("statistic_dim", "statistic"))
        out_name = str(params.get("output", self.name))

        primer_names, primers = fasta_sequences(inputs[0], primer_dim, position_dim, "primer_specificity")
        if len(primers) != 2:
            raise StepError(
                f"primer_specificity: exactly two primers are required, got {len(primers)}"
            )
        forward = clean_sequence(primers[0], "primer_specificity")
        reverse = clean_sequence(primers[1], "primer_specificity")
        if "N" in forward or "N" in reverse:
            raise StepError("primer_specificity: primers contain ambiguous bases")
        max_mismatches = int(params.get("max_mismatches", 0))
        min_product = int(params.get("min_product", 100))
        max_product = int(params.get("max_product", 1000))
        both_strands = bool(params.get("both_strands", True))
        max_hits = int(params.get("max_hits", 50))

        names, genomes = fasta_sequences(inputs[1], sequence_dim, position_dim, "primer_specificity")
        if not genomes:
            raise StepError("primer_specificity: the genome input is empty")

        rc_forward = reverse_complement(forward)
        rc_reverse = reverse_complement(reverse)
        amplicons = []
        for record_index, (name, raw) in enumerate(zip(names, genomes)):
            sequence = clean_sequence(raw, "primer_specificity")
            plus_f = scan_hits(forward, sequence, max_mismatches)
            plus_r = scan_hits(rc_reverse, sequence, max_mismatches)
            for f_start, f_mismatches in plus_f:
                for r_start, r_mismatches in plus_r:
                    product = r_start + len(reverse) - f_start
                    if product < min_product or product > max_product:
                        continue
                    amplicons.append({
                        "record": name,
                        "record_index": record_index,
                        "start": f_start + 1,
                        "end": r_start + len(reverse),
                        "strand": 1,
                        "forward_mismatches": f_mismatches,
                        "reverse_mismatches": r_mismatches,
                        "product_size": product,
                    })
            if both_strands:
                minus_f = scan_hits(rc_forward, sequence, max_mismatches)
                minus_r = scan_hits(reverse, sequence, max_mismatches)
                for f_start, f_mismatches in minus_f:
                    for r_start, r_mismatches in minus_r:
                        product = f_start + len(forward) - r_start
                        if product < min_product or product > max_product:
                            continue
                        amplicons.append({
                            "record": name,
                            "record_index": record_index,
                            "start": r_start + 1,
                            "end": f_start + len(forward),
                            "strand": -1,
                            "forward_mismatches": f_mismatches,
                            "reverse_mismatches": r_mismatches,
                            "product_size": product,
                        })
        amplicons.sort(key=lambda item: (item["record_index"], item["start"], item["strand"]))
        if len(amplicons) > max_hits:
            amplicons = amplicons[:max_hits]

        matrix = np.asarray(
            [
                [item["record_index"], item["start"], item["end"], item["strand"],
                 item["forward_mismatches"], item["reverse_mismatches"], item["product_size"]]
                for item in amplicons
            ],
            dtype=np.float64,
        ).reshape(-1, len(_COLUMNS))
        form = Form(
            matrix,
            dims=[amplicon_dim, statistic_dim],
            labels={
                amplicon_dim: {f"amplicon_{index + 1}": index for index in range(len(amplicons))},
                statistic_dim: {name: index for index, name in enumerate(_COLUMNS)},
            },
            info={
                "primers": list(primer_names),
                "forward": forward,
                "reverse": reverse,
                "max_mismatches": max_mismatches,
                "min_product": min_product,
                "max_product": max_product,
                "both_strands": both_strands,
                "n_amplicons": len(amplicons),
                "amplicons": [
                    {
                        "record": item["record"],
                        "start": int(item["start"]),
                        "end": int(item["end"]),
                        "strand": int(item["strand"]),
                        "product_size": int(item["product_size"]),
                    }
                    for item in amplicons
                ],
            },
        )
        ctx[out_name] = form
        self._export_data = {
            "n_amplicons": len(amplicons),
            "records_with_hits": len({item["record"] for item in amplicons}),
            "max_mismatches": max_mismatches,
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
