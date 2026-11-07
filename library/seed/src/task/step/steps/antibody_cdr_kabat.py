"""Kabat-style CDR and framework boundaries for VH/VHH sequences."""
from __future__ import annotations

import re

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._sequence_common import decode_sequences

# Kabat-numbered reference VHH (PDB 1MEL, deposited chain, Kabat numbering
# positions 1-133).  It is used for a pairwise alignment that determines the
# CDR-H2 column span; CDR-H1 and CDR-H3 boundaries come from the conserved
# cysteine and WGQG anchors that flank them in every VH/VHH domain.
TEMPLATE = (
    "DVQLQASGGGSVQAGGSLRLSCAASGYTIGPYCMGWFRQAPGKEREGVAAINMGGGITYYA"
    "DSVKGRFTISQDNAKNTVYLLMNSLEPEDTAIYYCAADSTIYASYYECGHGLSTGGYGYDS"
    "WGQGTQVTVSS"
)
_CDR2_ANCHOR = "AINMGGGITYYADSVKG"
_CDR2_SPAN = (TEMPLATE.find(_CDR2_ANCHOR), TEMPLATE.find(_CDR2_ANCHOR) + len(_CDR2_ANCHOR))
_CDR1_OFFSET = 9  # Kabat 31 = cysteine 22 + 9 residues
_CDR3_OFFSET = 3  # Kabat 95 = cysteine 92 + 3 residues
_FR4_LENGTH = 11  # Kabat 103-113
_FR2_START = re.compile(r"W[YFVALI]RQ")
_FR3_START = re.compile(r"RFTIS")
_FR4_START = re.compile(r"WG[QK]GT")
_CYSTEINE_22 = re.compile(r"LSC[A-Z]{1,3}")
_CYSTEINE_92 = re.compile(r"(?:C[A-Z][A-Z])")
REGIONS = ("FR1", "CDR1", "FR2", "CDR2", "FR3", "CDR3", "FR4")
_STATISTICS = ("start", "end", "length")
MIN_TEMPLATE_IDENTITY = 0.55


def _aligner():
    from Bio import Align

    aligner = Align.PairwiseAligner()
    aligner.mode = "global"
    aligner.substitution_matrix = Align.substitution_matrices.load("BLOSUM62")
    aligner.open_gap_score = -10.0
    aligner.extend_gap_score = -0.5
    # Free end gaps. Biopython renamed these attributes over time and its
    # getter can raise when left and right end scores differ, so set blindly.
    try:
        aligner.end_gap_score = 0.0
    except (AttributeError, ValueError):
        pass
    return aligner


def _template_mapping(sequence: str) -> tuple[dict[int, int], float]:
    """Map reference template indices to query indices with a global alignment."""
    aligner = _aligner()
    try:
        alignment = aligner.align(TEMPLATE, sequence)[0]
    except Exception as error:  # noqa: BLE001 - Biopython alignment failure
        raise StepError(
            "antibody_cdr_kabat: sequence cannot be aligned to the reference "
            f"VH/VHH template ({error})"
        ) from error
    target_blocks, query_blocks = alignment.aligned
    mapping: dict[int, int] = {}
    identical = 0
    for block in range(target_blocks.shape[0]):
        t_start, t_end = int(target_blocks[block, 0]), int(target_blocks[block, 1])
        q_start = int(query_blocks[block, 0])
        for offset in range(min(t_end - t_start, len(sequence) - q_start)):
            template_index = t_start + offset
            query_index = q_start + offset
            mapping[template_index] = query_index
            if TEMPLATE[template_index] == sequence[query_index]:
                identical += 1
    identity = identical / max(len(mapping), 1)
    return mapping, identity


def kabat_regions(sequence: str) -> list[tuple[str, int, int, str]]:
    """Return ``(region, start, end, residues)`` with 1-based closed bounds."""
    cleaned = str(sequence or "").strip().upper()
    if not cleaned:
        raise StepError("antibody_cdr_kabat: sequence must not be empty")
    if len(cleaned) < 80:
        raise StepError(
            "antibody_cdr_kabat: sequence of length "
            f"{len(cleaned)} is too short for a VH/VHH domain"
        )
    cysteine = _CYSTEINE_22.search(cleaned)
    if cysteine is None:
        raise StepError(
            "antibody_cdr_kabat: the conserved 'LSC' framework-1 cysteine was "
            "not found; this does not look like a VH/VHH domain"
        )
    cys22 = cysteine.start() + 2
    cdr1_start = cys22 + _CDR1_OFFSET
    fr2_match = _FR2_START.search(cleaned, cdr1_start)
    if fr2_match is None:
        raise StepError(
            "antibody_cdr_kabat: the conserved 'W..RQ' framework-2 tryptophan "
            "was not found after the CDR-H1 start"
        )
    fr2_start = fr2_match.start()
    cdr1_end = fr2_start - 1

    mapping, identity = _template_mapping(cleaned)
    if identity < MIN_TEMPLATE_IDENTITY:
        raise StepError(
            "antibody_cdr_kabat: sequence does not align to the reference "
            f"VH/VHH framework (identity {identity:.0%}, minimum "
            f"{MIN_TEMPLATE_IDENTITY:.0%})"
        )
    cdr2_start, cdr2_end = _CDR2_SPAN
    cdr2_indices = sorted(
        mapping[index] for index in range(cdr2_start, cdr2_end) if index in mapping
    )
    if not cdr2_indices:
        raise StepError("antibody_cdr_kabat: the alignment does not cover CDR-H2")
    cdr2_start = cdr2_indices[0]
    cdr2_end = cdr2_indices[-1]
    fr3_match = _FR3_START.search(cleaned, cdr2_end)
    if fr3_match is not None and fr3_match.start() > cdr2_end:
        cdr2_end = fr3_match.start() - 1
    if fr3_match is not None:
        fr3_start = fr3_match.start()
    else:
        fr3_start = cdr2_end + 1

    fr4_match = _FR4_START.search(cleaned, fr3_start)
    if fr4_match is None:
        raise StepError(
            "antibody_cdr_kabat: the conserved 'WGQG'/'WGKG' framework-4 motif "
            "was not found"
        )
    fr4_start = fr4_match.start()
    cys92 = cleaned.find("C", fr3_start, fr4_start)
    if cys92 < 0:
        raise StepError(
            "antibody_cdr_kabat: the conserved CDR-H3 cysteine was not found "
            "between framework 3 and the WGQG motif"
        )
    cdr3_start = cys92 + _CDR3_OFFSET
    cdr3_end = fr4_start - 1
    if not (cdr2_end < fr3_start <= cdr3_start <= cdr3_end):
        raise StepError(
            "antibody_cdr_kabat: the conserved anchors imply inconsistent "
            "CDR-H2/CDR-H3 boundaries"
        )
    fr4_end = min(fr4_start + _FR4_LENGTH - 1, len(cleaned) - 1)

    bounds = {
        "FR1": (0, cdr1_start - 1),
        "CDR1": (cdr1_start, cdr1_end),
        "FR2": (fr2_start, cdr2_start - 1),
        "CDR2": (cdr2_start, cdr2_end),
        "FR3": (fr3_start, cdr3_start - 1),
        "CDR3": (cdr3_start, cdr3_end),
        "FR4": (fr4_start, fr4_end),
    }
    regions: list[tuple[str, int, int, str]] = []
    for region in REGIONS:
        start, end = bounds[region]
        if start > end or start < 0 or end >= len(cleaned):
            raise StepError(
                f"antibody_cdr_kabat: the anchors give an empty or out-of-range "
                f"{region} ({start}-{end})"
            )
        regions.append((region, start + 1, end + 1, cleaned[start : end + 1]))
    return regions


class AntibodyCdrKabatStep(Step):
    provider = 'operon-core'
    """Kabat CDR and framework boundaries for a VH/VHH sequence."""
    parameters_file = 'antibody_cdr_kabat.AntibodyCdrKabatStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'antibody_cdr_kabat',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Kabat CDR boundaries',
     'category': 'Machine Learning',
     'icon': 'Tag',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {'representation': {'type': 'string', 'const': 'sequence_codes'},
                                        'alphabet': {'type': 'string', 'const': 'protein'},
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
                                         'axis_info_open': True,
                                         'info': {'missing_code': {'type': ['number', 'null']}}}}},
     'resources': {'memory_modes': ['full'],
                   'supports_cuda': False,
                   'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.24', 'biopython>=1.80'],
     'dependency_imports': ['Bio'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Locate the Kabat CDR-H1/H2/H3 and framework boundaries of a VH or VHH domain from conserved framework anchors and a reference alignment.'}

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        region_dim = str(params.get("region_dim", "region"))
        include_frameworks = bool(params.get("include_frameworks", True))
        out_name = params.get("output", self.name)
        form = inputs[0]
        if len(form.dims) != 2 or list(form.dims) != [sequence_dim, position_dim]:
            raise StepError(
                "antibody_cdr_kabat: expected a ["
                f"{sequence_dim}, {position_dim}] sequence form, got "
                f"{list(form.dims)}"
            )
        sequences = decode_sequences(form, sequence_dim, position_dim)
        if len(sequences) != 1:
            raise StepError(
                "antibody_cdr_kabat: exactly one VH/VHH sequence is supported, "
                f"got {len(sequences)}"
            )
        region_rows = kabat_regions(sequences[0])
        selected = [
            row for row in region_rows
            if include_frameworks or row[0].startswith("CDR")
        ]
        labels = {region: index for index, (region, *_rest) in enumerate(selected)}
        data = np.asarray(
            [[float(start), float(end), float(end - start + 1)]
             for _region, start, end, _residues in selected],
            dtype=np.float32,
        )
        cdr_sequences = {
            region: residues
            for region, _start, _end, residues in region_rows
            if region.startswith("CDR")
        }
        out = Form(
            data=data,
            dims=[region_dim, "statistic"],
            labels={
                region_dim: labels,
                "statistic": {
                    name: position for position, name in enumerate(_STATISTICS)
                },
            },
            info={
                "missing_code": np.nan,
                "sequence": sequences[0],
                "region_sequences": {region: residues for region, _s, _e, residues in region_rows},
                "cdr_sequences": cdr_sequences,
                "numbering_scheme": "kabat",
                "template": "VHH PDB 1MEL",
                "regions": [region for region, *_rest in selected],
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "regions": [
                {"region": region, "start": start, "end": end, "sequence": residues}
                for region, start, end, residues in region_rows
            ],
            "cdr_sequences": cdr_sequences,
            "numbering_scheme": "kabat",
        }
        print(
            "[antibody_cdr_kabat] "
            + ", ".join(f"{region} {start}-{end}" for region, start, end, _r in region_rows)
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
