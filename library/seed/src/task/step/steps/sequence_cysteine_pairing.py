"""Cysteine pairing hypotheses from a sequence."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


from src.task.step.steps._sequence_common import decode_sequences

_CYS_PATTERN = "C"


def cysteine_positions(sequence: str) -> list[int]:
    """Return 1-based positions of every cysteine."""

    return [index + 1 for index, residue in enumerate(str(sequence).upper()) if residue == "C"]


def pairing_rows(positions: list[int], *, scheme: str = "adjacent") -> list[dict]:
    """Pair cysteines either adjacently (C1-C2, C3-C4) or all-against-all."""

    if len(positions) < 2:
        raise StepError("sequence_cysteine_pairing: at least two cysteines are required")
    if len(positions) % 2 and scheme == "adjacent":
        raise StepError("sequence_cysteine_pairing: an odd number of cysteines cannot be paired adjacently")
    if scheme == "adjacent":
        pairs = list(zip(positions[0::2], positions[1::2]))
    elif scheme == "outer":
        ordered = positions
        pairs = [(ordered[i], ordered[-1 - i]) for i in range(len(ordered) // 2)]
    else:
        raise StepError(f"sequence_cysteine_pairing: unknown scheme '{scheme}'")
    rows = []
    for index, (first, second) in enumerate(pairs, start=1):
        rows.append({"pair": index, "first": first, "second": second, "separation": second - first - 1})
    return rows


class SequenceCysteinePairingStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_cysteine_pairing.SequenceCysteinePairingStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_cysteine_pairing",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Cysteine pairing",
        "category": "Sequence",
        "icon": "ShareNetwork",
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}], "labels": [], "parallel": [], "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
            "outputs": [],
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        sequences = decode_sequences(inputs[0], params["sequence_dim"], params["position_dim"])
        if len(sequences) != 1:
            raise StepError(f"sequence_cysteine_pairing: expected exactly one sequence, got {len(sequences)}")
        sequence = sequences[0]
        positions = cysteine_positions(sequence)
        if not positions:
            raise StepError("sequence_cysteine_pairing: the sequence carries no cysteine")
        rows = pairing_rows(positions, scheme=str(params.get("scheme", "adjacent")))
        data = np.array([[r["first"], r["second"], r["separation"]] for r in rows], dtype=np.float32)
        ctx[params.get("output", "pairs")] = Form(
            data=data,
            dims=["pair", "statistic"],
            labels={"pair": {f"pair{r['pair']}": i for i, r in enumerate(rows)}, "statistic": {"first": 0, "second": 1, "separation": 2}},
            info={"missing_code": np.nan, "n_cysteines": len(positions), "n_pairs": len(rows), "scheme": str(params.get("scheme", "adjacent")), "positions": positions},
        )
        self._export_data = {"n_cysteines": len(positions), "n_pairs": len(rows)}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
