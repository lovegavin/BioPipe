"""Curated sequence liability scan for protein and antibody design.

ProteinMPNN and friends optimise folding, not manufacturing.  This operator
reports the chemical liabilities that most often fail developability: Asn
deamidation, Asp isomerisation, methionine/tryptophan oxidation, N-linked
glycosylation sequons and N-terminal pyroglutamate formation.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences

_STATISTICS = ("position", "severity_code", "motif_length")
_SEVERITY_CODES = {"high": 3.0, "medium": 2.0, "low": 1.0}
_DIAMIDE = (
    ("deamidation", "NG", "high"),
    ("deamidation", "NS", "medium"),
    ("deamidation", "NT", "medium"),
    ("isomerization", "DG", "high"),
    ("isomerization", "DP", "low"),
    ("isomerization", "DS", "low"),
)
_OXIDATION = (("oxidation", "M", "medium"), ("oxidation", "W", "low"))


def liability_rows(
    sequence: str, *, include_oxidation: bool = True, context: int = 3
) -> list[dict]:
    """Return every curated liability site in ``sequence``."""

    text = str(sequence or "").strip().upper()
    if not text:
        raise StepError("sequence_liability_scan: the sequence is empty")
    hits: list[tuple[int, str, str, str]] = []
    for kind, motif, severity in _DIAMIDE:
        start = 0
        while True:
            index = text.find(motif, start)
            if index < 0:
                break
            hits.append((index + 1, kind, severity, motif))
            start = index + 1
    for index in range(len(text) - 2):
        if text[index] == "N" and text[index + 1] != "P" and text[index + 2] in "ST":
            hits.append((index + 1, "n_glycosylation", "medium", "N[^P][ST]"))
    if text[0] in "QE":
        hits.append((1, "pyroglutamate", "low", text[0]))
    if include_oxidation:
        for index, residue in enumerate(text):
            for kind, letter, severity in _OXIDATION:
                if residue == letter:
                    hits.append((index + 1, kind, severity, letter))

    best: dict[tuple[int, str], tuple[int, str, str, str]] = {}
    for hit in hits:
        key = (hit[0], hit[1])
        current = best.get(key)
        if current is None or _SEVERITY_CODES[hit[2]] > _SEVERITY_CODES[current[2]]:
            best[key] = hit
    rows: list[dict] = []
    for position, kind, severity, motif in sorted(best.values()):
        lower = max(position - 1 - int(context), 0)
        upper = min(position - 1 + int(context) + 1, len(text))
        rows.append(
            {
                "position": int(position),
                "residue": text[position - 1],
                "kind": kind,
                "severity": severity,
                "severity_code": _SEVERITY_CODES[severity],
                "motif": motif,
                "context": text[lower:upper],
            }
        )
    return rows


class SequenceLiabilityScanStep(Step):
    """Report deamidation, isomerisation, oxidation and glycosylation sites."""

    provider = "operon-core"
    parameters_file = (
        "sequence_liability_scan.SequenceLiabilityScanStep.parameters.json"
    )

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_liability_scan",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Sequence liability scan",
        "description": (
            "Scan a protein sequence for curated developability liabilities "
            "(Asn deamidation, Asp isomerisation, Met/Trp oxidation, N-linked "
            "glycosylation sequons and N-terminal pyroglutamate) and report "
            "each site with its severity code."
        ),
        "category": "Sequence",
        "icon": "Funnel",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "info": {
                        "missing_code": {"type": ["number", "null"]},
                        "encoders": {"type": "object", "optional": True},
                        "representation": {"type": "string", "const": "sequence_codes"},
                    },
                    "dims": [
                        {"param": "sequence_dim", "default": "sequence"},
                        {"param": "position_dim", "default": "position"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence")).strip() or "sequence"
        position_dim = str(params.get("position_dim", "position")).strip() or "position"
        include_oxidation = bool(params.get("include_oxidation", True))
        context = int(params.get("context") or 3)
        out_name = str(params.get("output", "liabilities")) or "liabilities"

        if context < 0 or context > 20:
            raise StepError(
                "sequence_liability_scan: context must be between 0 and 20 residues"
            )

        sequences = decode_sequences(inputs[0], sequence_dim, position_dim)
        if not sequences:
            raise StepError("sequence_liability_scan: the sequence form is empty")
        if len(sequences) != 1:
            raise StepError(
                "sequence_liability_scan: expected exactly one sequence, "
                f"got {len(sequences)}"
            )
        sequence = str(sequences[0]).strip().upper()
        rows = liability_rows(
            sequence, include_oxidation=include_oxidation, context=context
        )

        labels = {
            f"{row['position']}:{row['kind']}": index for index, row in enumerate(rows)
        }
        if len(labels) != len(rows):
            raise StepError("sequence_liability_scan: duplicate liability sites")
        data = np.asarray(
            [
                [
                    float(row["position"]),
                    row["severity_code"],
                    float(len(row["motif"])),
                ]
                for row in rows
            ],
            dtype=np.float32,
        ).reshape(len(rows), 3)
        kinds: dict[str, int] = {}
        for row in rows:
            kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
        ctx[out_name] = Form(
            data=data,
            dims=["liability", "statistic"],
            labels={
                "liability": labels,
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "sequence": sequence,
                "n_liabilities": len(rows),
                "kinds": kinds,
                "include_oxidation": include_oxidation,
                "context": context,
                "sites": rows,
            },
        )
        self._export_data = {
            "n_liabilities": len(rows),
            "kinds": kinds,
            "include_oxidation": include_oxidation,
            "sites": [
                {"position": int(row["position"]), "kind": row["kind"], "residue": row["residue"],
                 "motif": row["motif"], "context": row["context"], "severity": row["severity"]}
                for row in rows
            ],
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
