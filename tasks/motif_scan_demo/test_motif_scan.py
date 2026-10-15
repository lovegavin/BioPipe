import numpy as np

from src.core import Form, StepError
from src.task.step.steps.motif_scan import MotifScanStep
from biopipe_sdk.testing import run_operator
import pytest


_ALPHA_MAP = {"A": 0, "C": 1, "G": 2, "T": 3, "U": 3, "N": 4}


def _form(seqs, alphabet="dna"):
    max_len = max(len(s) for s in seqs)
    data = np.full((len(seqs), max_len), np.nan, dtype=np.float32)
    for i, s in enumerate(seqs):
        data[i, : len(s)] = [_ALPHA_MAP[c] for c in s]
    names = tuple(f"seq{i}" for i in range(len(seqs)))
    return Form(
        data=data,
        dims=["sequence", "position"],
        labels={
            "sequence": {names[i]: i for i in range(len(seqs))},
            "position": {str(i): i for i in range(max_len)},
        },
        info={
            "missing_code": np.nan,
            "representation": "sequence_codes",
            "alphabet_map": _ALPHA_MAP,
            "unknown_code": 5,
            "alphabet": alphabet,
        },
    )


def test_known_counts_acgtacgt():
    # chain: A C G T A C G T   (len 8)
    # ACGT : positions 0, 4          -> 2
    # CGTA : position 1              -> 1
    # NNNN : windows 0..4 all match  -> 5
    # R    : A|G at 0,2,4,6          -> 4
    # Y    : C|T at 1,3,5,7          -> 4
    out = run_operator(
        MotifScanStep,
        [_form(["ACGTACGT"])],
        {"motifs": {
            "acgt": "ACGT",
            "cgta": "CGTA",
            "any4": "NNNN",
            "purine": "R",
            "pyrimidine": "Y",
        }},
    )
    assert out.dims == ["motif", "sequence"]
    assert out.labels["motif"] == {
        "acgt": 0, "cgta": 1, "any4": 2, "purine": 3, "pyrimidine": 4,
    }
    col = out.data[:, 0]
    assert col[0] == 2.0
    assert col[1] == 1.0
    assert col[2] == 5.0
    assert col[3] == 4.0
    assert col[4] == 4.0
    assert out.info["representation"] == "motif_counts"


def test_overlapping_matches_counted():
    # "AAAAA" motif "AAA": windows at 0, 1, 2 -> 3
    out = run_operator(
        MotifScanStep,
        [_form(["AAAAA"])],
        {"motifs": {"a3": "AAA"}},
    )
    assert out.data[0, 0] == 3.0


def test_multiple_sequences_per_motif_counts():
    # seq0 "ACGTACGT" -> AA=0, TT=0
    # seq1 "AATTAA"   -> AA=2 (0-1, 4-5), TT=1 (2-3)
    out = run_operator(
        MotifScanStep,
        [_form(["ACGTACGT", "AATTAA"])],
        {"motifs": {"aa": "AA", "tt": "TT"}},
    )
    assert out.data.shape == (2, 2)
    assert out.data[0, 0] == 0.0
    assert out.data[0, 1] == 2.0
    assert out.data[1, 0] == 0.0
    assert out.data[1, 1] == 1.0


def test_n_in_chain_blocks_window():
    # "AANAA": AA matches at 0-1 and 3-4 -> 2. Windows 1-2 and 2-3
    # cross N and must not contribute.
    out = run_operator(
        MotifScanStep,
        [_form(["AANAA"])],
        {"motifs": {"aa": "AA"}},
    )
    assert out.data[0, 0] == 2.0


def test_motif_longer_than_chain():
    out = run_operator(
        MotifScanStep,
        [_form(["ACG"])],
        {"motifs": {"long": "ACGTAC"}},
    )
    assert out.data[0, 0] == 0.0


def test_unknown_iupac_rejected():
    with pytest.raises(StepError, match="unknown IUPAC"):
        run_operator(
            MotifScanStep,
            [_form(["ACGT"])],
            {"motifs": {"bad": "ACXGT"}},
        )


def test_missing_motifs_rejected_by_schema():
    with pytest.raises(ValueError, match="motifs"):
        run_operator(MotifScanStep, [_form(["ACGT"])], {})


def test_protein_alphabet_rejected():
    with pytest.raises(StepError, match="info.alphabet"):
        run_operator(
            MotifScanStep,
            [_form(["ACGT"], alphabet="protein")],
            {"motifs": {"x": "ACGT"}},
        )
