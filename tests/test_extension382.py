"""Tests for primer thermodynamics, design and in-silico PCR."""

from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps import _primer_utils as utils
from src.task.step.steps.primer_design import PrimerDesignStep
from src.task.step.steps.primer_specificity import PrimerSpecificityStep
from src.task.step.steps.primer_tm import PrimerTmStep

_TM35 = "AGATCGGAAGAGCACACGTCTGAACTCCAGTCAC"


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params

    def artifact_path(self, name):
        return f"tmp/{name}"


def _fasta(sequences, names=None):
    names = names or [f"seq{index}" for index in range(len(sequences))]
    width = max(len(sequence) for sequence in sequences)
    data = np.zeros((len(sequences), width), dtype=np.int16)
    return Form(
        data,
        dims=["sequence", "position"],
        labels={"sequence": {name: index for index, name in enumerate(names)}},
        info={
            "sequences": list(sequences),
            "representation": "sequence_codes",
            "alphabet_map": {"A": 0, "C": 1, "G": 2, "T": 3, "N": 4},
        },
    )


def test_tm_matches_biopython_reference_values():
    assert utils.tm_nn(_TM35)[0] == pytest.approx(65.37736143848792, rel=0, abs=1e-12)
    assert utils.tm_nn("ACGTACGTACGTACGTACGT")[0] == pytest.approx(53.09666582369118, abs=1e-12)
    assert utils.tm_nn("GCGCGCGCGCGCGCGCGCGC")[0] == pytest.approx(77.16435226224263, abs=1e-12)


def test_sequence_helpers():
    assert utils.gc_fraction("ACGT") == 0.5
    assert utils.reverse_complement("ACGTN") == "NACGT"
    with pytest.raises(StepError):
        utils.clean_sequence("ACGTX", "test")


def test_scan_hits_reports_positions_and_mismatches():
    genome = "TTTACGTACGTAAAACGTACGA"
    hits = utils.scan_hits("ACGTACGT", genome, 0)
    assert [start for start, _ in hits] == [3]
    tolerant = utils.scan_hits("ACGTACGT", genome, 1)
    assert any(start == 14 and mismatches == 1 for start, mismatches in tolerant)
    assert [start for start, mismatches in tolerant if mismatches == 0] == [3]


def test_primer_tm_operator_reports_tm_and_gc():
    step = PrimerTmStep()
    step.name = "primer_tm"
    ctx = Ctx({"output": "tm", "na_mm": 50.0, "dnac_nm": 25.0})
    step.run(ctx, [_fasta([_TM35, "ACGTACGTACGTACGTACGT"])])
    form = ctx["tm"]
    assert form.data.shape == (2, 5)
    assert form.data[0, 2] == pytest.approx(65.37736143848792, abs=1e-12)
    assert form.data[1, 1] == pytest.approx(0.5)
    assert form.info["n_sequences"] == 2


def test_primer_tm_rejects_ambiguous_bases():
    step = PrimerTmStep()
    step.name = "primer_tm"
    with pytest.raises(StepError):
        step.run(Ctx({"output": "tm"}), [_fasta(["ACGTNACGT"])])


def _design_params():
    return {
        "output": "pairs",
        "target_start": 300,
        "target_end": 340,
        "flank": 100,
        "min_length": 18,
        "max_length": 24,
        "opt_length": 20.0,
        "min_tm": 50.0,
        "opt_tm": 58.0,
        "max_tm": 66.0,
        "min_gc": 30.0,
        "max_gc": 70.0,
        "min_product": 80,
        "max_product": 320,
        "opt_product": 150.0,
        "na_mm": 50.0,
        "dnac_nm": 25.0,
        "tm_weight": 3.0,
        "length_weight": 1.0,
        "gc_weight": 0.5,
        "product_weight": 0.1,
        "max_pairs": 5,
    }


def _template(length=700):
    base = "ACGTTGCA" * (length // 8 + 1)
    return base[:length]


def test_primer_design_returns_flanking_pairs():
    template = _template()
    step = PrimerDesignStep()
    step.name = "primer_design"
    ctx = Ctx(_design_params())
    step.run(ctx, [_fasta([template])])
    form = ctx["pairs"]
    assert form.data.shape[0] >= 1
    for row in form.data:
        left_start, left_end, right_start, right_end = row[:4]
        assert left_end <= 299
        assert right_start >= 301
        assert 80 <= row[10] <= 320
        assert 50.0 <= row[6] <= 66.0
    assert len(form.info["pairs"]) == form.data.shape[0]


def test_primer_specificity_finds_single_amplicon():
    forward = "GATTACAGATTACAGATTAC"
    reverse = "CGGATCGGATCGGATCGGAT"
    template = list("A" * 800)
    template[100:120] = list(forward)
    template[300:320] = list(utils.reverse_complement(reverse))
    genome = "".join(template)
    step = PrimerSpecificityStep()
    step.name = "primer_specificity"
    ctx = Ctx({"output": "amplicons", "max_mismatches": 0, "min_product": 50,
               "max_product": 500, "both_strands": False})
    step.run(ctx, [_fasta([forward, reverse]), _fasta([genome], ["chr1"])])
    form = ctx["amplicons"]
    assert form.data.shape[0] == 1
    assert form.data[0, 1] == 101
    assert form.data[0, 2] == 320
    assert form.data[0, 6] == 220


def test_primer_specificity_allows_one_mismatch():
    forward = "GATTACAGATTACAGATTAC"
    reverse = "CGGATCGGATCGGATCGGAT"
    genome = "A" * 500
    mutated = "GATTACAGATTACAGATTAG"
    genome = genome[:100] + mutated + genome[120:]
    genome = genome[:300] + utils.reverse_complement(reverse) + genome[320:]
    step = PrimerSpecificityStep()
    step.name = "primer_specificity"
    ctx = Ctx({"output": "amplicons", "max_mismatches": 1, "min_product": 50,
               "max_product": 500, "both_strands": False})
    step.run(ctx, [_fasta([forward, reverse]), _fasta([genome], ["chr1"])])
    form = ctx["amplicons"]
    assert form.data.shape[0] == 1
    assert form.data[0, 4] == 1
