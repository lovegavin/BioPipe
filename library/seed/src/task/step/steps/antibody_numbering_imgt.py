"""IMGT residue numbering for VH/VHH sequences."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.reader import read_source
from src.task.step.base import Step

from ._sequence_common import PROTEIN_MAP
from .antibody_cdr_kabat import _template_mapping


# IMGT codes for the 133 positions of the reference VH/VHH template, taken
# from ANARCI (abnumber 0.4.4, scheme="imgt").  The table is static so that
# numbering needs neither HMMER nor the numbering database at run time.
_IMGT_CODES = (
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
    "21",
    "22",
    "23",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "30",
    "35",
    "36",
    "37",
    "38",
    "39",
    "40",
    "41",
    "42",
    "43",
    "44",
    "45",
    "46",
    "47",
    "48",
    "49",
    "50",
    "51",
    "52",
    "53",
    "54",
    "55",
    "56",
    "57",
    "58",
    "59",
    "62",
    "63",
    "64",
    "65",
    "66",
    "67",
    "68",
    "69",
    "70",
    "71",
    "72",
    "74",
    "75",
    "76",
    "77",
    "78",
    "79",
    "80",
    "81",
    "82",
    "83",
    "84",
    "85",
    "86",
    "87",
    "88",
    "89",
    "90",
    "91",
    "92",
    "93",
    "94",
    "95",
    "96",
    "97",
    "98",
    "99",
    "100",
    "101",
    "102",
    "103",
    "104",
    "105",
    "106",
    "107",
    "108",
    "109",
    "110",
    "111",
    "111A",
    "111B",
    "111C",
    "111D",
    "111E",
    "111F",
    "112G",
    "112F",
    "112E",
    "112D",
    "112C",
    "112B",
    "112A",
    "112",
    "113",
    "114",
    "115",
    "116",
    "117",
    "118",
    "119",
    "120",
    "121",
    "122",
    "123",
    "124",
    "125",
    "126",
    "127",
    "128",
)

REGIONS = ("FR1", "CDR1", "FR2", "CDR2", "FR3", "CDR3", "FR4")
# IMGT definitions use residue ranges on the IMGT numbering itself.
IMGT_REGIONS = (
    ("FR1", 1, 26),
    ("CDR1", 27, 38),
    ("FR2", 39, 55),
    ("CDR2", 56, 65),
    ("FR3", 66, 104),
    ("CDR3", 105, 117),
    ("FR4", 118, 128),
)


def _region_of(number: int) -> int:
    for index, (_name, start, end) in enumerate(IMGT_REGIONS, start=1):
        if start <= number <= end:
            return index
    return 0


def imgt_rows(sequence: str) -> list[dict]:
    """Return one record per residue with its IMGT number and region."""

    cleaned = str(sequence or "").strip().upper()
    if not cleaned:
        raise StepError("antibody_numbering_imgt: sequence must not be empty")
    mapping, _identity = _template_mapping(cleaned)
    if not mapping:
        raise StepError(
            "antibody_numbering_imgt: the sequence does not align to the "
            "reference VH/VHH template"
        )
    inverse = {query: template for template, query in mapping.items()}
    rows: list[dict] = []
    previous = -1
    insertion = 0
    for query in range(len(cleaned)):
        template = inverse.get(query)
        if template is None:
            insertion += 1
            number = max(previous + 1, 1)
            code = f"{number}{chr(ord('A') + insertion - 1)}"
            suffix = insertion - 1
        else:
            insertion = 0
            previous = template
            code = _IMGT_CODES[template]
            digits = "".join(char for char in code if char.isdigit())
            number = int(digits)
            suffix = len(code) - len(digits)
        region = _region_of(number)
        rows.append(
            {
                "position": query + 1,
                "residue": cleaned[query],
                "imgt_number": number,
                "insertion_index": suffix,
                "imgt_code": code,
                "region_index": region,
                "region": REGIONS[region - 1] if region else "unassigned",
                "is_cdr": 1 if region and "CDR" in REGIONS[region - 1] else 0,
            }
        )
    if not rows:
        raise StepError("antibody_numbering_imgt: no residue could be numbered")
    return rows


class AntibodyNumberingImgtStep(Step):
    """Number a VH/VHH sequence with the IMGT scheme."""

    provider = "operon-core"
    parameters_file = "antibody_numbering_imgt.AntibodyNumberingImgtStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "antibody_numbering_imgt",
        "version": "1.0.0",
        "kind": "operator",
        "title": "IMGT numbering",
        "description": (
            "Align a VH/VHH sequence to the reference template and return one row "
            "per residue with its IMGT number, insertion suffix and "
            "FR/CDR region assignment."
        ),
        "category": "Machine Learning",
        "icon": "GridNine",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "info": {
                        "representation": {"type": "string", "const": "sequence_codes"},
                        "alphabet_map": {"type": "object"},
                        "unknown_code": {"type": "integer"},
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
        sequence_dim = str(params.get("sequence_dim", "sequence")) or "sequence"
        position_dim = str(params.get("position_dim", "position")) or "position"
        out_name = str(params.get("output", "numbering")) or "numbering"

        sequences = _decode(inputs[0], sequence_dim, position_dim)
        if len(sequences) != 1:
            raise StepError(
                f"antibody_numbering_imgt: expected exactly one sequence, got {len(sequences)}"
            )

        rows = imgt_rows(sequences[0])
        labels = {
            "position": {f"pos{row['position']}": index for index, row in enumerate(rows)},
            "statistic": {
                name: index
                for index, name in enumerate(
                    ("imgt_number", "insertion_index", "region_index", "is_cdr")
                )
            },
        }
        data = np.zeros((len(rows), 4), dtype=np.float32)
        for index, row in enumerate(rows):
            data[index] = (
                row["imgt_number"],
                row["insertion_index"],
                row["region_index"],
                row["is_cdr"],
            )
        ctx[out_name] = Form(
            data=data,
            dims=["position", "statistic"],
            labels=labels,
            info={"missing_code": np.nan},
        )
        self._export_data = {
            "n_residues": len(rows),
            "codes": [row["imgt_code"] for row in rows],
            "regions": [row["region"] for row in rows],
            "sequence": sequences[0],
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


def _decode(form: Form, sequence_dim: str, position_dim: str) -> list[str]:
    from ._sequence_common import decode_sequences

    return decode_sequences(form, sequence_dim, position_dim)
