"""Kabat residue numbering for VH/VHH sequences."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._sequence_common import decode_sequences
from .antibody_cdr_kabat import _template_mapping, kabat_regions

# Kabat codes for the 133 positions of the reference VH/VHH template, taken
# from ANARCI (abnumber 0.4.4, scheme='kabat').  The table is static so that
# numbering needs neither HMMER nor the ANARCI database at run time.
_TEMPLATE_KABAT_CODES = (
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
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
    "31",
    "32",
    "33",
    "34",
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
    "52A",
    "53",
    "54",
    "55",
    "56",
    "57",
    "58",
    "59",
    "60",
    "61",
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
    "73",
    "74",
    "75",
    "76",
    "77",
    "78",
    "79",
    "80",
    "81",
    "82",
    "82A",
    "82B",
    "82C",
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
    "100A",
    "100B",
    "100C",
    "100D",
    "100E",
    "100F",
    "100G",
    "100H",
    "100I",
    "100J",
    "100K",
    "100L",
    "100M",
    "100N",
    "100O",
    "100P",
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
    "112",
    "113",
)

_STATISTICS = ("kabat_number", "insertion_index", "region_index", "is_cdr")
REGIONS = ("FR1", "CDR1", "FR2", "CDR2", "FR3", "CDR3", "FR4")


def _region_lookup(sequence: str) -> tuple[dict[int, int], dict[str, tuple[int, int]]]:
    """Map each 1-based query position to its region index and back to spans."""

    spans: dict[str, tuple[int, int]] = {}
    lookup: dict[int, int] = {}
    for index, (name, start, end, _residues) in enumerate(kabat_regions(sequence), start=1):
        spans[name] = (start, end)
        for position in range(start, end + 1):
            lookup[position] = index
    return lookup, spans


def numbering_rows(
    sequence: str,
) -> tuple[list[dict], dict[str, tuple[int, int]]]:
    """Return one record per residue with its Kabat number and region."""

    cleaned = str(sequence or "").strip().upper()
    if not cleaned:
        raise StepError("antibody_numbering_kabat: sequence must not be empty")
    mapping, identity = _template_mapping(cleaned)
    if not mapping:
        raise StepError(
            "antibody_numbering_kabat: the sequence does not align to the "
            "reference VH/VHH template"
        )
    lookup, spans = _region_lookup(cleaned)
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
            code = _TEMPLATE_KABAT_CODES[template]
            digits = "".join(char for char in code if char.isdigit())
            number = int(digits)
            suffix = len(code) - len(digits)
        region = lookup.get(query + 1)
        rows.append(
            {
                "position": query + 1,
                "residue": cleaned[query],
                "kabat_number": number,
                "insertion_index": suffix,
                "kabat_code": code,
                "region_index": int(region or 0),
                "region": REGIONS[region - 1] if region else "unassigned",
                "is_cdr": 1 if region and "CDR" in REGIONS[region - 1] else 0,
            }
        )
    if not rows:
        raise StepError("antibody_numbering_kabat: no residue could be numbered")
    return rows, spans


class AntibodyNumberingKabatStep(Step):
    """Number a VH/VHH sequence with the Kabat scheme."""

    provider = "operon-core"
    parameters_file = "antibody_numbering_kabat.AntibodyNumberingKabatStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "antibody_numbering_kabat",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Kabat numbering",
        "description": (
            "Align a VH/VHH sequence to the Kabat reference template and return "
            "one row per residue with its Kabat number, insertion suffix and "
            "framework/CDR region assignment."
        ),
        "category": "Machine Learning",
        "icon": "Dna",
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
        "dependencies": ["numpy>=1.24", "biopython>=1.80"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence")).strip() or "sequence"
        position_dim = str(params.get("position_dim", "position")).strip() or "position"
        out_name = params.get("output", self.name)

        sequences = decode_sequences(inputs[0], sequence_dim, position_dim)
        if not sequences:
            raise StepError("antibody_numbering_kabat: the input form has no sequences")
        if len(sequences) > 1:
            raise StepError(
                "antibody_numbering_kabat: expected exactly one VH/VHH sequence, "
                f"got {len(sequences)}"
            )
        rows, spans = numbering_rows(sequences[0])
        sequence_label = list(
            dict(sorted(inputs[0].labels[sequence_dim].items(), key=lambda item: item[1]))
        )[0]
        data = np.asarray(
            [
                (
                    float(row["kabat_number"]),
                    float(row["insertion_index"]),
                    float(row["region_index"]),
                    float(row["is_cdr"]),
                )
                for row in rows
            ],
            dtype=np.float32,
        )
        form_out = Form(
            data=data,
            dims=["position", "statistic"],
            labels={
                "position": {
                    f"{sequence_label}:{row['kabat_code']}": index
                    for index, row in enumerate(rows)
                },
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "sequence": sequences[0],
                "n_residues": len(rows),
                "kabat_codes": [row["kabat_code"] for row in rows],
                "residues": [row["residue"] for row in rows],
                "regions": [row["region"] for row in rows],
                "region_spans": {name: list(span) for name, span in spans.items()},
                "n_cdr": sum(int(row["is_cdr"]) for row in rows),
            },
        )
        ctx[out_name] = form_out
        self._export_data = {
            "n_residues": len(rows),
            "n_cdr": int(sum(row["is_cdr"] for row in rows)),
            "cdr1": list(spans.get("CDR1", (0, 0))),
            "cdr3": list(spans.get("CDR3", (0, 0))),
        }
        print(f"[{self.name}] numbered {len(rows)} residue(s)")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
