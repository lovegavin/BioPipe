# tasks/kmer_count_demo/test_kmer_count.py
import numpy as np

from src.core import Form, StepError
from src.task.step.steps.kmer_count import KmerCountStep
from biopipe_sdk.testing import run_operator
import pytest


_ALPHA_MAP = {"A": 0, "C": 1, "G": 2, "T": 3, "U": 3, "N": 4}
_BASES = ("A", "C", "G", "T")


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


def _all_kmers(k):
    from itertools import product
    return ["".join(p) for p in product(_BASES, repeat=k)]


def _index_of(kmer, k):
    return {km: i for i, km in enumerate(_all_kmers(k))}[kmer]


def test_k2_hand_counted():
    # seqA "ACGT"         -> AC CG GT
    # seqB "ACGTACGTACGT" -> AC x3, CG x3, GT x3, TA x2
    # seqC "ACNGT"        -> AC, GT   (window crossing N is skipped)
    out = run_operator(
        KmerCountStep,
        [_form(["ACGT", "ACGTACGTACGT", "ACNGT"])],
        {"k": 2},
    )
    assert out.dims == ["kmer", "sequence"]
    assert set(out.labels["kmer"]) == set(_all_kmers(2))

    col_a = out.data[:, 0]
    col_b = out.data[:, 1]
    col_c = out.data[:, 2]

    assert col_a[_index_of("AC", 2)] == 1.0
    assert col_a[_index_of("CG", 2)] == 1.0
    assert col_a[_index_of("GT", 2)] == 1.0
    assert col_a.sum() == 3.0

    assert col_b[_index_of("AC", 2)] == 3.0
    assert col_b[_index_of("CG", 2)] == 3.0
    assert col_b[_index_of("GT", 2)] == 3.0
    assert col_b[_index_of("TA", 2)] == 2.0
    assert col_b.sum() == 11.0

    assert col_c[_index_of("AC", 2)] == 1.0
    assert col_c[_index_of("GT", 2)] == 1.0
    assert col_c.sum() == 2.0

    assert out.info["k"] == 2
    assert out.info["representation"] == "kmer_counts"


def test_k1_counts():
    out = run_operator(
        KmerCountStep,
        [_form(["ACGT", "AAAC"])],
        {"k": 1},
    )
    assert out.labels["kmer"] == {"A": 0, "C": 1, "G": 2, "T": 3}
    np.testing.assert_array_equal(out.data[:, 0], [1, 1, 1, 1])
    np.testing.assert_array_equal(out.data[:, 1], [3, 1, 0, 0])


def test_short_sequence_below_k():
    out = run_operator(
        KmerCountStep,
        [_form(["A", "ACGT"])],
        {"k": 3},
    )
    assert out.data[:, 0].sum() == 0.0
    assert out.data[:, 1].sum() == 2.0


def test_protein_rejected():
    with pytest.raises(StepError, match="info.alphabet"):
        run_operator(
            KmerCountStep,
            [_form(["ACGT"], alphabet="protein")],
            {"k": 2},
        )


def test_k_out_of_range_rejected_by_schema():
    with pytest.raises(ValueError, match="k: 7 is greater than the maximum of 6"):
        run_operator(KmerCountStep, [_form(["ACGT"])], {"k": 7})