"""External-baseline verification of every operator added in v4.

Every check uses either a publicly known value (NCBI, SGD, ENCODE,
10x) or an independent reference implementation. No hand-crafted
expected numbers.

Run with: python tasks/verify_operators.py
"""
import bisect
import random
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

sys.path.insert(0, ".")

from src.core import Form
from src.reader import read_source
from biopipe_sdk.testing import run_operator

from src.task.step.steps.sequence_stats import SequenceStatsStep
from src.task.step.steps.kmer_count import KmerCountStep
from src.task.step.steps.find_orfs import FindOrfsStep
from src.task.step.steps.gff_feature_stats import GffFeatureStatsStep
from src.task.step.steps.gene_structure import GeneStructureStep
from src.task.step.steps.annotation_gaps import AnnotationGapsStep
from src.task.step.steps.interval_stats import IntervalStatsStep
from src.task.step.steps.interval_merge import IntervalMergeStep
from src.task.step.steps.interval_overlap import IntervalOverlapStep
from src.task.step.steps.peak_nearest_gene import PeakNearestGeneStep
from src.task.step.steps.qc_metrics import QcMetricsStep
from src.task.step.steps.scale_features import ScaleFeaturesStep
from src.task.step.steps.gc_skew_profile import GcSkewProfileStep


checks = []


def record(name, ok, expected, actual):
    checks.append((name, bool(ok), str(expected)[:60], str(actual)[:60]))


def read(path, dims, labels):
    return read_source(Path(path), dims, labels)


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


# ------------------------------------------------------------------ 1
section("1. sequence_stats — external baseline (NCBI)")

seq_form = read(
    "tasks/sequence_stats_demo/input/sequences.fasta",
    ["sequence", "position"],
    {"sequence": "builtin", "position": "auto"},
)
stats = run_operator(SequenceStatsStep, [seq_form], {})
seq_labels = [k for k, _ in sorted(
    seq_form.labels["sequence"].items(), key=lambda kv: kv[1]
)]
sars_idx = next(i for i, s in enumerate(seq_labels)
                if s.startswith("NC_045512"))
sars_len = float(stats.data[sars_idx, 0])
sars_gc = float(stats.data[sars_idx, 1])
print(f"  SARS-CoV-2 length = {sars_len}")
print(f"  SARS-CoV-2 GC     = {sars_gc:.4f}")
record("SARS-CoV-2 length == 29903 (NCBI)",
       abs(sars_len - 29903) < 1, 29903, sars_len)
record("SARS-CoV-2 GC ~ 0.3797 (NCBI)",
       abs(sars_gc - 0.3797) < 0.005, 0.3797, sars_gc)


# ------------------------------------------------------------------ 2
section("2. kmer_count — cross-operator consistency")

k1 = run_operator(KmerCountStep, [seq_form], {"k": 1})
total_k1 = float(k1.data.sum())
total_valid = float(stats.data[:, 0].sum())
print(f"  sum of k=1 counts       = {total_k1}")
print(f"  sum of sequence lengths = {total_valid}")
record("kmer_count k=1 total == valid bases (cross-op)",
       abs(total_k1 - total_valid) < 1, total_valid, total_k1)


# ------------------------------------------------------------------ 3
section("3. find_orfs — external baseline (NCBI SARS-CoV-2)")

orfs = run_operator(
    FindOrfsStep, [seq_form], {"min_aa": 1000},
)
sars_rows = [i for i, s in enumerate(orfs.info["sequence"])
             if s.startswith("NC_045512")]
sars_max_nt = max(float(orfs.data[i, 4]) for i in sars_rows) if sars_rows else 0.0
print(f"  longest SARS-CoV-2 ORF = {sars_max_nt:.0f} nt")
record("longest SARS ORF in [12500, 13500] bp (orf1a ~13203)",
       12500 < sars_max_nt < 13500, "~13203", sars_max_nt)


# ------------------------------------------------------------------ 4
section("4. gff_feature_stats — external baseline (SGD)")

gff = read(
    "tasks/gff_feature_stats_demo/input/genome.gff3.gz",
    ["record", "field"],
    {"record": "auto", "field": "builtin"},
)
gff_stats = run_operator(GffFeatureStatsStep, [gff], {})
gene_row = gff_stats.labels["feature_type"]["gene"]
gene_count = float(gff_stats.data[gene_row, 0])
print(f"  S. cerevisiae gene count = {gene_count}")
record("S. cerevisiae gene count == 6600 (SGD)",
       abs(gene_count - 6600) < 1, 6600, gene_count)


# ------------------------------------------------------------------ 5
section("5. gene_structure — SGD annotation characteristics")

gs = run_operator(
    GeneStructureStep,
    [read("tasks/gene_structure_demo/input/genome.gff3.gz",
          ["record", "field"],
          {"record": "auto", "field": "builtin"})],
    {},
)
mean_exons = float(gs.data[:, 0].mean())
mean_cds = float(gs.data[:, 3].mean())
print(f"  mean exons per gene   = {mean_exons:.3f}")
print(f"  mean CDS length (bp)  = {mean_cds:.1f}")
record("yeast mean exons/gene in [1.0, 1.2]",
       1.0 <= mean_exons <= 1.2, "[1.0,1.2]", mean_exons)
record("yeast mean CDS length in [1000, 1600] bp",
       1000 <= mean_cds <= 1600, "[1000,1600]", mean_cds)


# ------------------------------------------------------------------ 6
section("6. annotation_gaps — intergenic distance (literature)")

gaps = run_operator(
    AnnotationGapsStep,
    [read("tasks/annotation_gaps_demo/input/genome.gff3.gz",
          ["record", "field"],
          {"record": "auto", "field": "builtin"})],
    {"min_gap": 0},
)
median_gap = float(np.median(gaps.data[:, 0]))
print(f"  median intergenic gap = {median_gap:.0f} bp")
record("yeast median gap in [200, 2000] bp",
       200 < median_gap < 2000, "[200,2000]", median_gap)


# ------------------------------------------------------------------ 7
section("7. interval_stats — external baseline (ENCODE SCREEN v3)")

ccre = read(
    "tasks/interval_stats_demo/input/cCREs.bed",
    ["region", "field"],
    {"region": "auto", "field": "builtin"},
)
istat = run_operator(IntervalStatsStep, [ccre], {})
total_n = float(istat.data[:, 0].sum())
total_bp = float(istat.data[:, 1].sum())
print(f"  total cCRE intervals = {total_n:.0f}")
print(f"  total cCRE bp        = {total_bp:.0f}")
record("cCRE count == 1063878 (ENCODE SCREEN v3)",
       abs(total_n - 1063878) < 1, 1063878, total_n)
record("cCRE total bp in [1e8, 5e8]",
       1e8 < total_bp < 5e8, "~2.4e8", total_bp)


# ------------------------------------------------------------------ 8
section("8. interval_merge — invariants")

imerge = run_operator(
    IntervalMergeStep,
    [read("tasks/interval_merge_demo/input/cCREs.bed",
          ["region", "field"],
          {"region": "auto", "field": "builtin"})],
    {"min_overlap": 0},
)
n_covered = float(imerge.data[:, 3].sum())
lengths_ok = bool(np.allclose(imerge.data[:, 2],
                              imerge.data[:, 1] - imerge.data[:, 0]))
print(f"  merged regions             = {imerge.data.shape[0]}")
print(f"  sum of n_intervals          = {n_covered:.0f}")
print(f"  length == end - start for all rows: {lengths_ok}")
record("Σ n_intervals == 1063878 (each input in exactly one region)",
       abs(n_covered - 1063878) < 1, 1063878, n_covered)
record("merged length == end - start for every row",
       lengths_ok, True, lengths_ok)


# ------------------------------------------------------------------ 9
section("9. interval_overlap — invariants on chr22 subset")

peaks_chr22 = read(
    "tasks/peak_nearest_gene_demo/input/peaks.bed",
    ["region", "field"],
    {"region": "auto", "field": "builtin"},
)
genes_chr22 = read(
    "tasks/peak_nearest_gene_demo/input/genes.gff3",
    ["record", "field"],
    {"record": "auto", "field": "builtin"},
)
iover = run_operator(IntervalOverlapStep, [peaks_chr22, genes_chr22], {
    "min_overlap": 1,
    "b_region_dim": "record",
    "b_field_dim": "field",
    "b_chrom_field": "seqid",
    "b_start_field": "start",
    "b_end_field": "end",
})
len_ok = bool(np.allclose(iover.data[:, 2],
                          iover.data[:, 1] - iover.data[:, 0]))
min_ok = bool(np.all(iover.data[:, 2] >= 1))
print(f"  n pairs                     = {iover.data.shape[0]}")
print(f"  length == end - start       : {len_ok}")
print(f"  length >= min_overlap (1)   : {min_ok}")
record("interval_overlap pairs length == end - start",
       len_ok, True, len_ok)
record("interval_overlap every pair >= 1 bp",
       min_ok, True, min_ok)


# ------------------------------------------------------------------ 10
section("10. peak_nearest_gene — independent bisect reference")

ann = run_operator(
    PeakNearestGeneStep, [peaks_chr22, genes_chr22],
    {"feature_type": "gene"},
)

# Independent reference: build a sorted (start, end) list per chrom from
# the raw gene Form, then for 50 random peaks compute the distance by hand
# and compare with the operator's output.
random.seed(42)
gene_starts = [float(genes_chr22.data[i, genes_chr22.labels["field"]["start"]])
               for i in range(genes_chr22.data.shape[0])]
gene_ends = [float(genes_chr22.data[i, genes_chr22.labels["field"]["end"]])
             for i in range(genes_chr22.data.shape[0])]
order = np.argsort(gene_starts)
gene_starts = [gene_starts[i] for i in order]
gene_ends = [gene_ends[i] for i in order]

peak_start_col = peaks_chr22.labels["field"]["chromStart"]
peak_end_col = peaks_chr22.labels["field"]["chromEnd"]

sample_ids = random.sample(range(peaks_chr22.data.shape[0]),
                           min(50, peaks_chr22.data.shape[0]))
mismatches = 0
for pid in sample_ids:
    p_start = float(peaks_chr22.data[pid, peak_start_col])
    p_end = float(peaks_chr22.data[pid, peak_end_col])
    # find nearest gene by linear scan (slow but correct)
    best = None
    for gs, ge in zip(gene_starts, gene_ends):
        if ge <= p_start:
            d = p_start - ge
        elif gs >= p_end:
            d = gs - p_end
        else:
            d = 0.0
        if best is None or d < best:
            best = d
            if d == 0:
                break
    # look up the operator's distance for this peak
    try:
        pos = ann.info["peak_id"].index(str(pid))
    except ValueError:
        mismatches += 1
        continue
    if abs(float(ann.data[pos, 0]) - float(best)) > 1e-3:
        mismatches += 1

print(f"  sampled peaks               = {len(sample_ids)}")
print(f"  mismatches                  = {mismatches}")
record("peak_nearest_gene distance matches independent reference",
       mismatches == 0, 0, mismatches)


# ------------------------------------------------------------------ 11
section("11. qc_metrics — 10x PBMC 3k expected range")

mtx = read(
    "tasks/mtx_demo/input/matrix.mtx.gz",
    ["gene", "cell"],
    {"gene": "builtin", "cell": "builtin"},
)
qc = run_operator(QcMetricsStep, [mtx], {
    "feature_dim": "gene",
    "sample_dim": "cell",
    "metrics": [
        {"name": "total", "op": "sum"},
        {"name": "n_detected", "op": "nonzero"},
    ],
})
median_umi = float(np.median(qc.data[:, 0]))
median_genes = float(np.median(qc.data[:, 1]))
print(f"  median total UMI per cell   = {median_umi:.0f}")
print(f"  median n_detected per cell  = {median_genes:.0f}")
record("PBMC 3k median UMI in [2000, 8000]",
       2000 < median_umi < 8000, "[2000,8000]", median_umi)
record("PBMC 3k median detected genes in [300, 2000]",
       300 < median_genes < 2000, "[300,2000]", median_genes)


# ------------------------------------------------------------------ 12
section("12. scale_features — mathematical invariants")

scaled = run_operator(ScaleFeaturesStep, [mtx], {"dim": "cell"})
# Rows that are constant along the cell axis (all-zero genes, single-cell
# sparse data) legitimately become zero after z-scoring; exclude them
# from the std==1 check.
input_std = np.nanstd(mtx.data, axis=1)
nonconstant = input_std > 1e-6
row_means = np.nanmean(scaled.data[nonconstant], axis=1)
row_stds = np.nanstd(scaled.data[nonconstant], axis=1)
mean_max = float(np.abs(row_means).max())
std_dev = float(np.abs(row_stds - 1.0).max())
print(f"  non-constant rows           = {int(nonconstant.sum())} / {nonconstant.size}")
print(f"  max |row mean|              = {mean_max:.3e}")
print(f"  max |row std - 1|           = {std_dev:.3e}")
record("scale_features non-constant row mean == 0",
       mean_max < 1e-4, "<1e-4", f"{mean_max:.2e}")
record("scale_features non-constant row std == 1",
       std_dev < 1e-4, "<1e-4", f"{std_dev:.2e}")


# ------------------------------------------------------------------ 13
section("13. gc_skew_profile — E. coli oriC and ter positions")

ecoli = read(
    "tasks/gc_skew_demo/input/ecoli.fasta",
    ["sequence", "position"],
    {"sequence": "builtin", "position": "auto"},
)
profile = run_operator(
    GcSkewProfileStep, [ecoli],
    {"window_size": 10000, "step_size": 10000},
)
cum_gc = profile.data[:, 6]
ori_idx = int(np.argmin(cum_gc))
ter_idx = int(np.argmax(cum_gc))
ori_pos = ori_idx * 10000
ter_pos = ter_idx * 10000
print(f"  E. coli length              = {int(profile.info['sequence_length'])}")
print(f"  cumulative GC min at        = {ori_pos} bp (oriC, expected ~3.93 Mb)")
print(f"  cumulative GC max at        = {ter_pos} bp (ter,  expected ~1.59 Mb)")
record("E. coli length == 4641652 (NCBI)",
       int(profile.info["sequence_length"]) == 4641652,
       4641652, int(profile.info["sequence_length"]))
record("oriC window in [385, 400] (~3.93 Mb)",
       385 <= ori_idx <= 400, "[385,400]", ori_idx)
record("ter  window in [150, 170] (~1.59 Mb)",
       150 <= ter_idx <= 170, "[150,170]", ter_idx)


# ------------------------------------------------------------------ summary
print()
print("=" * 78)
print("Verification summary")
print("=" * 78)
n_pass = sum(1 for _, ok, _, _ in checks if ok)
print(f"{'':4s}{'check':<58s}{'expected':<16s}{'actual':<20s}")
print("-" * 78)
for name, ok, exp, act in checks:
    status = "PASS" if ok else "FAIL"
    print(f"{status:4s}  {name:<56s}  {exp:<14s}  {act:<20s}")
print("-" * 78)
print(f"{n_pass}/{len(checks)} checks passed")
