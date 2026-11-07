"""Global and local pairwise sequence alignment with affine gaps.

The scoring convention follows Biopython's ``PairwiseAligner``: a gap of
length ``k`` costs ``gap_open + (k - 1) * gap_extend``. Global alignment
maximises the score over the full sequences; local alignment finds the
best-scoring sub-alignment and reports it.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._sequence_common import decode_sequences
from ._stats20_common import scalar_form

_NEG = float("-inf")


def _best(*values: float) -> float:
    return max(values)


def _align(target: str, query: str, match: float, mismatch: float,
           gap_open: float, gap_extend: float, mode: str) -> dict:
    n, m = len(target), len(query)
    negative = _NEG
    rows, cols = n + 1, m + 1
    match_matrix = np.full((rows, cols), negative, dtype=np.float64)
    delete_matrix = np.full((rows, cols), negative, dtype=np.float64)
    insert_matrix = np.full((rows, cols), negative, dtype=np.float64)
    match_matrix[0, 0] = 0.0
    for i in range(1, rows):
        delete_matrix[i, 0] = gap_open + (i - 1) * gap_extend
    for j in range(1, cols):
        insert_matrix[0, j] = gap_open + (j - 1) * gap_extend
    if mode == "local":
        delete_matrix[:, 0] = 0.0
        insert_matrix[0, :] = 0.0
    best_score = 0.0 if mode == "local" else negative
    best_cell = (0, 0, "M")

    for i in range(1, rows):
        for j in range(1, cols):
            pair = match if target[i - 1] == query[j - 1] else mismatch
            previous = _best(
                match_matrix[i - 1, j - 1],
                delete_matrix[i - 1, j - 1],
                insert_matrix[i - 1, j - 1],
            )
            match_matrix[i, j] = previous + pair
            delete_matrix[i, j] = _best(
                match_matrix[i - 1, j] + gap_open,
                delete_matrix[i - 1, j] + gap_extend,
            )
            insert_matrix[i, j] = _best(
                match_matrix[i, j - 1] + gap_open,
                insert_matrix[i, j - 1] + gap_extend,
            )
            if mode == "local":
                if match_matrix[i, j] < 0.0:
                    match_matrix[i, j] = 0.0
                if delete_matrix[i, j] < 0.0:
                    delete_matrix[i, j] = 0.0
                if insert_matrix[i, j] < 0.0:
                    insert_matrix[i, j] = 0.0
                for state, value in (("M", match_matrix[i, j]),
                                     ("X", delete_matrix[i, j]),
                                     ("Y", insert_matrix[i, j])):
                    if value > best_score:
                        best_score = value
                        best_cell = (i, j, state)

    if mode == "global":
        final = _best(
            match_matrix[n, m], delete_matrix[n, m], insert_matrix[n, m]
        )
        best_score = final
        if match_matrix[n, m] >= final:
            best_cell = (n, m, "M")
        elif delete_matrix[n, m] >= final:
            best_cell = (n, m, "X")
        else:
            best_cell = (n, m, "Y")

    i, j, state = best_cell
    aligned_target: list[str] = []
    aligned_query: list[str] = []
    while i > 0 or j > 0:
        if i == 0:
            state = "Y"
        elif j == 0:
            state = "X"
        if mode == "local":
            value = (
                match_matrix[i, j]
                if state == "M"
                else (delete_matrix[i, j] if state == "X" else insert_matrix[i, j])
            )
            if value <= 0.0:
                break
        if state == "M":
            aligned_target.append(target[i - 1])
            aligned_query.append(query[j - 1])
            candidates = (
                match_matrix[i - 1, j - 1],
                delete_matrix[i - 1, j - 1],
                insert_matrix[i - 1, j - 1],
            )
            pick = int(np.argmax(candidates))
            state = "M" if pick == 0 else ("X" if pick == 1 else "Y")
            i -= 1
            j -= 1
        elif state == "X":
            aligned_target.append(target[i - 1])
            aligned_query.append("-")
            if delete_matrix[i, j] == match_matrix[i - 1, j] + gap_open:
                state = "M"
            i -= 1
        else:
            aligned_target.append("-")
            aligned_query.append(query[j - 1])
            if insert_matrix[i, j] == match_matrix[i, j - 1] + gap_open:
                state = "M"
            j -= 1

    aligned_target.reverse()
    aligned_query.reverse()
    aligned_t = "".join(aligned_target)
    aligned_q = "".join(aligned_query)

    matches = 0
    mismatches = 0
    gap_opens = 0
    gap_bases = 0
    previous = "M"
    for a, b in zip(aligned_t, aligned_q):
        if a == "-" or b == "-":
            gap_bases += 1
            if previous != "gap":
                gap_opens += 1
            previous = "gap"
        else:
            previous = "pair"
            if a == b:
                matches += 1
            else:
                mismatches += 1
    aligned_length = len(aligned_t)
    identity = matches / aligned_length if aligned_length else float("nan")
    return {
        "score": float(best_score),
        "aligned_target": aligned_t,
        "aligned_query": aligned_q,
        "identity": float(identity),
        "matches": float(matches),
        "mismatches": float(mismatches),
        "gap_opens": float(gap_opens),
        "gap_bases": float(gap_bases),
        "aligned_length": float(aligned_length),
        "target_length": float(n),
        "query_length": float(m),
    }


class PairwiseAlignmentStep(Step):
    """Align exactly two sequences and report score and alignment counts."""

    provider = 'operon-core'
    parameters_file = 'pairwise_alignment.PairwiseAlignmentStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'pairwise_alignment',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Pairwise alignment',
     'category': 'Omics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {'representation': {'type': 'string', 'const': 'sequence_codes'},
                                        'alphabet': {'type': 'string', 'enum': ['dna', 'rna']},
                                        'missing_code': {'type': ['number', 'null']}},
                               'dims': [{'param': 'sequence_dim', 'default': 'sequence'},
                                        {'param': 'position_dim', 'default': 'position'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2},
                              {'version': 1,
                               'numeric': True,
                               'info': {'representation': {'type': 'string', 'const': 'sequence_codes'},
                                        'alphabet': {'type': 'string', 'enum': ['dna', 'rna']},
                                        'missing_code': {'type': ['number', 'null']}},
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
     'dependencies': ['numpy>=1.26'],
     'dependency_imports': ['numpy'],
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Align two sequences with affine gaps and report the alignment counts.'}

    def run(self, ctx: Context, inputs) -> None:
        first, second = inputs
        sequence_dim = ctx.step_params.get("sequence_dim", "sequence")
        position_dim = ctx.step_params.get("position_dim", "position")
        match = float(ctx.step_params.get("match", 2.0))
        mismatch = float(ctx.step_params.get("mismatch", -1.0))
        gap_open = float(ctx.step_params.get("gap_open", -2.0))
        gap_extend = float(ctx.step_params.get("gap_extend", -1.0))
        mode = ctx.step_params.get("mode", "global")
        max_cells = int(ctx.step_params.get("max_cells", 4_000_000))
        if mode not in {"global", "local"}:
            raise StepError("pairwise_alignment: mode must be 'global' or 'local'")
        if mismatch > 0.0:
            raise StepError("pairwise_alignment: mismatch score must not be positive")
        if gap_open > 0.0 or gap_extend > 0.0:
            raise StepError("pairwise_alignment: gap penalties must not be positive")

        sequences = decode_sequences(first, sequence_dim, position_dim)
        others = decode_sequences(second, sequence_dim, position_dim)
        if len(sequences) != 1 or len(others) != 1:
            raise StepError(
                "pairwise_alignment: exactly two sequences are required, "
                f"got {len(sequences)} and {len(others)}"
            )
        target, query = sequences[0], others[0]
        if (len(target) + 1) * (len(query) + 1) > max_cells:
            raise StepError(
                "pairwise_alignment: alignment matrix is too large "
                f"({(len(target) + 1) * (len(query) + 1)} cells > {max_cells})"
            )

        result = _align(target, query, match, mismatch, gap_open, gap_extend, mode)
        names = ["score", "identity", "matches", "mismatches", "gap_opens",
                 "gap_bases", "aligned_length", "target_length", "query_length"]
        out = scalar_form([result[name] for name in names], names, "pairwise_alignment")
        out.info.update({
            "aligned_target": result["aligned_target"],
            "aligned_query": result["aligned_query"],
            "target": target,
            "query": query,
            "mode": mode,
            "scoring": {
                "match": match,
                "mismatch": mismatch,
                "gap_open": gap_open,
                "gap_extend": gap_extend,
            },
        })
        out.validate()
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export = {
            "score": result["score"],
            "identity": result["identity"],
            "aligned_target": result["aligned_target"],
            "aligned_query": result["aligned_query"],
            "mode": mode,
            "target_length": int(result["target_length"]),
            "query_length": int(result["query_length"]),
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export", {})
