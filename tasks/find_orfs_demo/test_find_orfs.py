# tasks/find_orfs_demo/test_find_orfs.py
import numpy as np

from src.core import Form, StepError
from src.task.step.steps.find_orfs import FindOrfsStep
from biopipe_sdk.testing import run_operator
import pytest


_ALPHA_MAP = {"A": 0, "C": 1, "G": 2, "T": 3, "U": 3, "N": 4}
_STAT = ("strand", "frame", "start", "end", "length_nt", "length_aa")


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


def _row(out, i):
    return {name: float(out.data[i, j]) for j, name in enumerate(_STAT)}


def test_single_orf_forward_frame_0():
    # "TTT ATG AAA CCC GGG TAA AA"  (20 nt)
    # Forward frame 0:
    #   ATG at nt 3, in-frame stop TAA at nt 15.
    #   start=3, end=17, length_nt=15, length_aa=4, strand=+1, frame=0
    out = run_operator(
        FindOrfsStep,
        [_form(["TTTATGAAACCCGGGTAAAA"])],
        {},
    )
    assert out.dims == ["orf", "statistic"]
    assert out.data.shape == (1, 6)
    assert _row(out, 0) == {
        "strand": 1.0, "frame": 0.0,
        "start": 3.0, "end": 17.0,
        "length_nt": 15.0, "length_aa": 4.0,
    }
    assert out.info["sequence"] == ["seq0"]


def test_two_orfs_same_frame_forward():
    # "ATG AAA TAG TTT ATG CCC TAA"  (21 nt)
    # Forward frame 0 has two non-overlapping ORFs:
    #   ATG at 0 -> TAG at 6 : start=0, end=8, len_nt=9, len_aa=2
    #   ATG at 12 -> TAA at 18: start=12, end=20, len_nt=9, len_aa=2
    out = run_operator(
        FindOrfsStep,
        [_form(["ATGAAATAGTTTATGCCCTAA"])],
        {},
    )
    assert out.data.shape == (2, 6)
    assert _row(out, 0) == {
        "strand": 1.0, "frame": 0.0,
        "start": 0.0, "end": 8.0,
        "length_nt": 9.0, "length_aa": 2.0,
    }
    assert _row(out, 1) == {
        "strand": 1.0, "frame": 0.0,
        "start": 12.0, "end": 20.0,
        "length_nt": 9.0, "length_aa": 2.0,
    }


def test_reverse_strand_orf():
    # "TTATTTCAT"
    # Forward chain has no ATG.
    # Reverse complement = "ATGAAATAA":
    #   ATG at RC 0, in-frame stop TAA at RC 6.
    #   start=0, end=8 on RC, len_nt=9, len_aa=2, strand=-1, frame=0
    out = run_operator(FindOrfsStep, [_form(["TTATTTCAT"])], {})
    assert out.data.shape == (1, 6)
    assert _row(out, 0) == {
        "strand": -1.0, "frame": 0.0,
        "start": 0.0, "end": 8.0,
        "length_nt": 9.0, "length_aa": 2.0,
    }


def test_min_aa_filter_drops_short_orfs():
    # Both ORFs have length_aa == 2; min_aa=3 removes all of them.
    out = run_operator(
        FindOrfsStep,
        [_form(["ATGAAATAGTTTATGCCCTAA"])],
        {"min_aa": 3},
    )
    assert out.data.shape == (0, 6)
    assert out.info["sequence"] == []


def test_multiple_sequences():
    # seq0 "TTTATGAAACCCGGGTAAAA"  -> 1 ORF (fwd, frame 0, start=3)
    # seq1 "ATGAAATAGTTTATGCCCTAA" -> 2 ORFs (fwd, frame 0, start=0 and 12)
    out = run_operator(
        FindOrfsStep,
        [_form(["TTTATGAAACCCGGGTAAAA", "ATGAAATAGTTTATGCCCTAA"])],
        {},
    )
    assert out.data.shape == (3, 6)
    assert out.info["sequence"] == ["seq0", "seq1", "seq1"]
    r0 = _row(out, 0)
    r1 = _row(out, 1)
    r2 = _row(out, 2)
    assert r0["strand"] == 1.0 and r0["start"] == 3.0 and r0["end"] == 17.0
    assert r1["strand"] == 1.0 and r1["start"] == 0.0 and r1["end"] == 8.0
    assert r2["strand"] == 1.0 and r2["start"] == 12.0 and r2["end"] == 20.0


def test_protein_alphabet_rejected():
    with pytest.raises(StepError, match="info.alphabet"):
        run_operator(
            FindOrfsStep,
            [_form(["ATGAAATAA"], alphabet="protein")],
            {},
        )


def test_missing_alphabet_map_rejected():
    form = _form(["ATGAAATAA"])
    form.info.pop("alphabet_map")
    with pytest.raises(StepError, match="alphabet_map"):
        run_operator(FindOrfsStep, [form], {})