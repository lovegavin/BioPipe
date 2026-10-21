"""Standalone verification of the sequence features route.

Run with: python tasks/sequence_features_route_demo/test_sequence_route.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core import Form, StepError
from src.reader import read_source
from src.reader.readers._encoder import get_encoder
from src.task.step.steps.sequence_stats import SequenceStatsStep
from src.task.step.steps.find_orfs import FindOrfsStep
from src.task.step.steps.motif_scan import MotifScanStep
from biopipe_sdk.testing import run_operator


DATA = Path(__file__).parent / "input" / "sequences.fasta"


def _encode_seq(seq, alphabet_map):
    return np.array([[alphabet_map[c] for c in seq]], dtype=np.float32)


def _make_form(sequence):
    alphabet_map = {'A': 0, 'C': 1, 'G': 2, 'T': 3, 'N': 4}
    data = _encode_seq(sequence, alphabet_map)
    return Form(
        data=data,
        dims=["sequence", "position"],
        labels={
            "sequence": {"seq1": 0},
            "position": {str(i): i for i in range(data.shape[1])},
        },
        info={
            "missing_code": np.nan,
            "alphabet": "dna",
            "alphabet_map": alphabet_map,
            "representation": "sequence_codes",
            "unknown_code": 4,
        },
    )


def _load_real():
    if not DATA.exists():
        raise SystemExit(f"missing {DATA}")
    return read_source(DATA, dims=["sequence", "position"],
                       labels={"sequence": "builtin", "position": "auto"})


def test_sequence_stats_hand_counted():
    # 20 nt: A(5), C(4), G(5), T(5), N(1). GC = 9/20 = 0.45.
    # n_ratio = 1/20 = 0.05. N is in alphabet_map, so valid_ratio = 1.
    seq = "ACGTAGCTAGCTAGTACGTN"
    form = _make_form(seq)
    out = run_operator(SequenceStatsStep, [form], {})
    stats = {n: float(out.data[0, j])
             for j, n in enumerate(out.labels["statistic"])}
    assert stats["length"] == 20.0
    assert abs(stats["gc"] - 0.45) < 1e-6, stats["gc"]
    assert abs(stats["n_ratio"] - 0.05) < 1e-6, stats["n_ratio"]
    assert abs(stats["valid_ratio"] - 1.0) < 1e-6, stats["valid_ratio"]
    print("  sequence_stats hand-counted          ok")


def test_motif_scan_hand_counted():
    # 'GGTATAAAC' contains 'TATA' starting at position 2.
    seq = "GGTATAAAC"
    form = _make_form(seq)
    out = run_operator(MotifScanStep, [form], {"motifs": {"TATA": "TATA"}})
    assert out.data.shape == (1, 1)
    assert float(out.data[0, 0]) == 1.0
    # 'GCGCGC' has no TATA.
    form2 = _make_form("GCGCGC")
    out2 = run_operator(MotifScanStep, [form2], {"motifs": {"TATA": "TATA"}})
    assert float(out2.data[0, 0]) == 0.0
    print("  motif_scan hand-counted              ok")


def test_find_orfs_hand_counted():
    # ATG AAA TAA (6 nt? no, length must be multiple of 3).
    # ATG + GCT + TAA = 9 nt, one complete ORF on the forward strand.
    seq = "ATGGCTTAA"
    form = _make_form(seq)
    out = run_operator(FindOrfsStep, [form], {})
    stat = out.labels["statistic"]
    strand_col = stat["strand"]
    start_col = stat["start"]
    end_col = stat["end"]
    aa_col = stat["length_aa"]
    n_orf = out.data.shape[0]
    assert n_orf >= 1, n_orf
    strands = out.data[:, strand_col].tolist()
    aas = out.data[:, aa_col].tolist()
    assert 1.0 in strands
    assert 2.0 in aas
    print(f"  find_orfs found {n_orf} ORFs             ok")


def test_real_sars_cov_2_length_and_gc():
    if not DATA.exists():
        print("  SARS-CoV-2 length/GC (data missing)  skip")
        return
    form = _load_real()
    out = run_operator(SequenceStatsStep, [form], {})
    stats = {n: i for n, i in out.labels["statistic"].items()}
    # NCBI NC_045512.2: 29903 bp; GC = 0.3797.
    cov2 = out.labels["sequence"]["NC_045512.2"]
    length = float(out.data[cov2, stats["length"]])
    gc = float(out.data[cov2, stats["gc"]])
    assert length == 29903.0, length
    assert abs(gc - 0.3797) < 0.001, gc
    print(f"  SARS-CoV-2 length=29903 GC~0.3797   ok")


def main():
    print("sequence features route verification")
    test_sequence_stats_hand_counted()
    test_motif_scan_hand_counted()
    test_find_orfs_hand_counted()
    test_real_sars_cov_2_length_and_gc()
    print()
    print("all checks passed")


if __name__ == "__main__":
    main()
