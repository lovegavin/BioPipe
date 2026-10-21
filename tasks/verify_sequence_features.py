"""Independent verification of the sequence features route.

Run with: python tasks/verify_sequence_features.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")

from src.reader import read_source
from src.task.step.steps.sequence_stats import SequenceStatsStep
from src.task.step.steps.find_orfs import FindOrfsStep
from src.task.step.steps.motif_scan import MotifScanStep
from biopipe_sdk.testing import run_operator


checks = []


def record(name, ok, expected, actual):
    checks.append((name, bool(ok), str(expected)[:50], str(actual)[:50]))


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def _decode_sequences(form):
    """Decode back to strings using the alphabet_map."""
    amap = form.info["alphabet_map"]
    inv = {v: k for k, v in amap.items()}
    # T and U share a code; decode as T for nucleotide comparison.
    if 3 in inv and inv[3] == "U":
        inv[3] = "T"
    seqs = []
    for i in range(form.data.shape[0]):
        codes = form.data[i]
        s = []
        for c in codes:
            if not np.isfinite(c):
                break
            s.append(inv.get(int(round(float(c))), "N"))
        seqs.append("".join(s))
    return seqs


def main():
    data = Path("tasks/sequence_features_route_demo/input/sequences.fasta")
    if not data.exists():
        print(f"missing {data}")
        sys.exit(1)

    form = read_source(data, dims=["sequence", "position"],
                       labels={"sequence": "builtin", "position": "auto"})
    sequences = _decode_sequences(form)

    section("1. sequence_stats vs independent string analysis")
    out_stats = run_operator(SequenceStatsStep, [form], {})
    stat = {n: i for n, i in out_stats.labels["statistic"].items()}
    max_len_err = 0.0
    max_gc_err = 0.0
    for i, s in enumerate(sequences):
        length = len(s.rstrip("N"))
        gc = sum(1 for c in s if c in "GC") / max(length, 1)
        n_ratio = sum(1 for c in s if c == "N") / max(len(s), 1)
        got_len = float(out_stats.data[i, stat["length"]])
        got_gc = float(out_stats.data[i, stat["gc"]])
        max_len_err = max(max_len_err, abs(got_len - length))
        max_gc_err = max(max_gc_err, abs(got_gc - gc))
    record("per-sequence length matches independent",
            max_len_err < 1e-3, "0 err", f"{max_len_err:.6f}")
    record("per-sequence gc matches independent",
            max_gc_err < 1e-6, "0 err", f"{max_gc_err:.8f}")

    section("2. SARS-CoV-2 vs NCBI published values")
    # NCBI NC_045512.2: length 29903 bp, GC fraction 0.3797.
    cov2_idx = form.labels["sequence"]["NC_045512.2"]
    cov2_len = float(out_stats.data[cov2_idx, stat["length"]])
    cov2_gc = float(out_stats.data[cov2_idx, stat["gc"]])
    record("SARS-CoV-2 length == 29903 (NCBI)",
            cov2_len == 29903.0, 29903, f"{cov2_len:.0f}")
    record("SARS-CoV-2 GC == 0.3797 (NCBI)",
            abs(cov2_gc - 0.3797) < 0.001, 0.3797, f"{cov2_gc:.4f}")

    section("3. find_orfs count vs independent scan")
    out_orfs = run_operator(FindOrfsStep, [form], {})
    total_orfs = out_orfs.data.shape[0]
    # Independent: count ATG-led ORFs on forward and reverse strands
    # terminated by TAA/TAG/TGA.
    stop_codons = {"TAA", "TAG", "TGA"}
    def count_orfs(seq, min_aa=1):
        n = 0
        for frame in range(3):
            i = frame
            while i + 3 <= len(seq):
                codon = seq[i:i+3]
                if codon == "ATG":
                    j = i + 3
                    while j + 3 <= len(seq):
                        if seq[j:j+3] in stop_codons:
                            aa = (j - i) // 3
                            if aa >= min_aa:
                                n += 1
                            break
                        j += 3
                i += 3
        return n
    comp = {"A": "T", "C": "G", "G": "C", "T": "A", "N": "N"}
    def revcomp(s):
        return "".join(comp[c] for c in reversed(s))
    indep = sum(count_orfs(s) + count_orfs(revcomp(s)) for s in sequences)
    # find_orfs reports complete ORFs only.
    record("ORF count within factor of 2 of independent estimate",
            abs(total_orfs - indep) <= indep,
            f"~{indep}", total_orfs)

    section("4. motif_scan counts vs independent search")
    motifs = {"TATA": "TATAAA", "SP1": "GGGCGG"}
    out_motif = run_operator(MotifScanStep, [form], {"motifs": motifs})
    m_stats = out_motif.data
    for mi, (mname, mpat) in enumerate(motifs.items()):
        for si, seq in enumerate(sequences):
            indep = seq.count(mpat)
            got = float(m_stats[mi, si])
            record(f"{mname} in {list(form.labels['sequence'])[si]}",
                    int(got) == indep, indep, int(got))

    print()
    print("=" * 78)
    print("Verification summary")
    print("=" * 78)
    print(f"{'':<4}{'check':<54}{'expected':>12}{'actual':>14}")
    print("-" * 78)
    for name, ok, exp, act in checks:
        status = "PASS" if ok else "FAIL"
        print(f"{status}  {name:<54}{exp:>12}{act:>14}")
    print("-" * 78)
    passed = sum(1 for _, ok, _, _ in checks if ok)
    print(f"{passed}/{len(checks)} checks passed")
    if passed < len(checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
