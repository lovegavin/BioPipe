# src/task/step/steps/sequence_stats.py
"""Per-sequence summary statistics for sequence-codes forms.

Input: any Form declaring info["representation"] == "sequence_codes".
The character-to-code mapping is read from info["alphabet_map"], so
the operator works with any reader that declares the same convention
(FASTA today; FASTQ, 2bit, GenBank, ... later).

Output: [sequence, statistic] float32 with
    length       number of non-padding positions
    gc           (C + G) / length
    n_ratio      N / length
    valid_ratio  length / max_position

Only DNA/RNA alphabets (info["alphabet"] in {"dna","rna"}) are accepted;
GC content is undefined for protein.

Params:
    sequence_dim : name of the sequence axis (default "sequence")
    position_dim : name of the position axis (default "position")
    output       : context key for the result (default: step name)
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.forms.metadata import project_metadata
from src.task.context import Context
from src.task.step.base import Step


_STAT_LABELS = ("length", "gc", "n_ratio", "valid_ratio")


class SequenceStatsStep(Step):
    """Per-sequence length, GC and N content for any sequence-codes Form."""
    provider = 'biopipe-core'
    parameters_file = 'sequence_stats.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'sequence_stats',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'sequence_stats',
     'description': 'Per-sequence length, GC and N content for any sequence-codes Form.',
     'category': 'analysis',
     'icon': 'Ruler',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {'missing_code': {'type': ['number', 'null']},
                                        'representation': {'type': 'string', 'const': 'sequence_codes'},
                                        'alphabet_map': {'type': 'object'},
                                        'unknown_code': {'type': 'integer'},
                                        'alphabet': {'type': 'string', 'enum': ['dna', 'rna']}},
                               'dims': [{'param': 'sequence_dim', 'default': 'sequence'},
                                        {'param': 'position_dim', 'default': 'position'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output'}



    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        seq_dim = ctx.step_params.get("sequence_dim", "sequence")
        pos_dim = ctx.step_params.get("position_dim", "position")
        out_name = ctx.step_params.get("output", self.name)

        if form.data.ndim != 2 or form.dims[0] != seq_dim or form.dims[1] != pos_dim:
            raise StepError(
                f"sequence_stats: expected 2D [{seq_dim},{pos_dim}], "
                f"got {form.dims}"
            )

        alpha_map = form.info.get("alphabet_map")
        if not isinstance(alpha_map, dict):
            raise StepError(
                "sequence_stats: input is not a sequence_codes Form "
                "(info.alphabet_map missing)"
            )
        codes = {}
        for ch in ("G", "C", "N"):
            if ch not in alpha_map:
                raise StepError(
                    f"sequence_stats: alphabet_map missing code for '{ch}'"
                )
            codes[ch] = int(alpha_map[ch])

        alphabet = form.info.get("alphabet")
        if alphabet not in ("dna", "rna"):
            raise StepError(
                f"sequence_stats: GC requires dna/rna, got alphabet={alphabet!r}"
            )

        data = form.data
        n_seq, max_len = data.shape

        valid = ~np.isnan(data)
        lengths = valid.sum(axis=1).astype(np.float64)

        gc_mask = valid & ((data == codes["C"]) | (data == codes["G"]))
        n_mask = valid & (data == codes["N"])
        gc_counts = gc_mask.sum(axis=1).astype(np.float64)
        n_counts = n_mask.sum(axis=1).astype(np.float64)

        safe = np.where(lengths > 0, lengths, 1.0)
        gc_ratio = gc_counts / safe
        n_ratio = n_counts / safe
        valid_ratio = (
            lengths / float(max_len) if max_len > 0
            else np.zeros_like(lengths)
        )

        out_data = np.stack(
            [lengths, gc_ratio, n_ratio, valid_ratio], axis=1
        ).astype(np.float32)

        info, axis_info = project_metadata(form, derived=True)
        info["missing_code"] = np.nan
        info["representation"] = "sequence_stats"
        info["alphabet"] = alphabet

        out_form = Form(
            data=out_data,
            dims=[seq_dim, "statistic"],
            labels={
                seq_dim: dict(form.labels[seq_dim]),
                "statistic": {n: i for i, n in enumerate(_STAT_LABELS)},
            },
            info=info,
            axis_info=axis_info,
        )
        ctx[out_name] = out_form

        self._export_data = {
            "sequence_dim": seq_dim,
            "position_dim": pos_dim,
            "n_sequences": int(n_seq),
            "max_position": int(max_len),
            "alphabet": alphabet,
            "statistics": list(_STAT_LABELS),
            "total_length": float(lengths.sum()),
            "mean_length": float(lengths.mean()),
            "min_length": float(lengths.min()),
            "max_length": float(lengths.max()),
            "mean_gc": float(gc_ratio.mean()),
        }

        print(
            f"[sequence_stats] {n_seq} sequences, max_len={max_len}, "
            f"alphabet={alphabet}, mean_gc={gc_ratio.mean():.4f}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data