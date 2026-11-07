"""VHH framework humanization score against human IGHV3-23/JH4 germline."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences
from src.task.step.steps.antibody_cdr_kabat import kabat_regions

_STATISTICS = ("n_positions", "n_mismatches", "mismatch_fraction", "identity")
_FRAMEWORKS = ("FR1", "FR2", "FR3", "FR4")

# IGHV3-23*01 germline protein (framework donor for most humanized VH) and the
# IGHJ4*01 J-region that supplies FR4.
HUMAN_IGHV3_23 = (
    "EVQLLESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISGSGGSTYYADSVKGRF"
    "TISRDNSKNTLYLQMNSLRAEDTAVYYCAK"
)
HUMAN_IGHJ4 = "WGQGTLVTVSS"


def _aligner() -> PairwiseAligner:
    from Bio.Align import PairwiseAligner, substitution_matrices

    aligner = PairwiseAligner()
    aligner.mode = "global"
    aligner.match_score = 1.0
    aligner.mismatch_score = -1.0
    aligner.open_gap_score = -2.0
    aligner.extend_gap_score = -0.5
    aligner.substitution_matrix = substitution_matrices.load("BLOSUM62")
    return aligner


def compare_regions(query: str, reference: str, *, operator: str) -> tuple[int, int]:
    """Return (n_positions, n_mismatches) for one framework alignment."""

    if not query or not reference:
        raise StepError(f"{operator}: an empty framework region cannot be compared")
    aligner = _aligner()
    alignment = aligner.align(query, reference)[0]
    query_chars = []
    reference_chars = []
    for (q_start, q_end), (r_start, r_end) in zip(alignment.aligned[0], alignment.aligned[1]):
        query_chars.append(query[q_start:q_end])
        reference_chars.append(reference[r_start:r_end])
    query_text = "".join(query_chars)
    reference_text = "".join(reference_chars)
    if len(query_text) != len(reference_text):
        raise StepError(
            f"{operator}: the framework alignment collapsed to different lengths"
        )
    compared = len(query_text)
    if compared == 0:
        raise StepError(f"{operator}: the framework alignment covered no position")
    mismatches = sum(
        1
        for query_residue, reference_residue in zip(query_text, reference_text)
        if query_residue != reference_residue
    )
    return compared, mismatches


REFERENCE_FRAMEWORKS = {
    # Kabat framework segments of human IGHV3-23*01 plus IGHJ4*01.
    "FR1": "EVQLLESGGGLVQPGGSLRLSCAASGFTFS",
    "FR2": "WVRQAPGKGLEWVS",
    "FR3": "RFTISRDNSKNTLYLQMNSLRAEDTAVYYC",
    "FR4": HUMAN_IGHJ4,
}


def humanization_rows(sequence: str, *, operator: str = "vhh_humanization_score") -> list[tuple]:
    sequence = str(sequence or "").strip().upper()
    if not sequence:
        raise StepError(f"{operator}: the input carries an empty sequence")
    query_regions = {name: residues for name, _start, _end, residues in kabat_regions(sequence)}
    reference_regions = REFERENCE_FRAMEWORKS

    rows: list[tuple] = []
    compared_total = 0
    mismatch_total = 0
    for name in ("FR1", "FR2", "FR3"):
        query = query_regions.get(name, "")
        reference = reference_regions.get(name, "")
        compared, mismatches = compare_regions(query, reference, operator=operator)
        rows.append((compared, mismatches, mismatches / compared, 1.0 - mismatches / compared))
        compared_total += compared
        mismatch_total += mismatches

    query_fr4 = query_regions.get("FR4", "")
    if not query_fr4:
        raise StepError(f"{operator}: the sequence has no Kabat FR4 region")
    compared, mismatches = compare_regions(query_fr4, HUMAN_IGHJ4, operator=operator)
    rows.append((compared, mismatches, mismatches / compared, 1.0 - mismatches / compared))
    compared_total += compared
    mismatch_total += mismatches

    overall = mismatch_total / compared_total if compared_total else float("nan")
    rows.append((compared_total, mismatch_total, overall, 1.0 - overall))
    return rows



def _jsonable(value):
    """Convert numpy values into JSON-serialisable Python objects."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _export_summary(form) -> dict:
    """Build the export payload for one result Form."""
    return {
        "dims": list(form.dims),
        "labels": _jsonable(form.labels),
        "info": _jsonable(
            {key: value for key, value in form.info.items() if key != "missing_code"}
        ),
    }

class VhhHumanizationScoreStep(Step):
    provider = "operon-core"
    parameters_file = "vhh_humanization_score.VhhHumanizationScoreStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "vhh_humanization_score",
        "version": "1.0.0",
        "kind": "operator",
        "title": "VHH humanization score",
        "category": "Antibody",
        "icon": "Dna",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                    "info": {
                        "representation": {"type": "string", "const": "sequence_codes"}
                    },
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                    "info": {"missing_code": {"type": ["number", "null"]}},
                },
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24", "biopython>=1.80"],
        "dependency_imports": ["Bio"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "description": (
            "Score VHH framework humanness by aligning the Kabat FR1-FR4 of each "
            "sequence to the human IGHV3-23*01 and IGHJ4*01 germline references "
            "and reporting per-framework mismatch fractions."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        out_name = params.get("output", self.name)
        sequences = decode_sequences(
            inputs[0],
            str(params.get("sequence_dim", "sequence")),
            str(params.get("position_dim", "position")),
        )
        if not sequences:
            raise StepError("vhh_humanization_score: the input carries no sequence")
        if len(sequences) > 1:
            raise StepError(
                "vhh_humanization_score: expected exactly one VHH sequence, got "
                f"{len(sequences)}"
            )
        rows = humanization_rows(sequences[0])
        data = np.asarray(rows, dtype=np.float32)
        labels = {name: index for index, name in enumerate(_FRAMEWORKS)}
        labels["overall"] = len(_FRAMEWORKS)
        result = Form(
            data=data,
            dims=["framework", "statistic"],
            labels={
                "framework": labels,
                "statistic": {
                    name: index for index, name in enumerate(_STATISTICS)
                },
            },
            info={
                "missing_code": np.nan,
                "overall_mismatch_fraction": float(rows[-1][2]),
                "overall_identity": float(rows[-1][3]),
                "n_positions": int(rows[-1][0]),
                "reference": {
                    "FR1-FR3": "IGHV3-23*01",
                    "FR4": "IGHJ4*01",
                },
                "sequence": sequences[0],
            },
        )
        self._export_data = _export_summary(result)
        ctx[out_name] = result

    def export(self, ctx: Context):
        return self._export_data
