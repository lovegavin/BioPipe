"""Independent verification of the interval analysis route.

Run with: python tasks/verify_interval_analysis.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")

from src.reader import read_source
from src.task.step.steps.interval_stats import IntervalStatsStep
from src.task.step.steps.interval_merge import IntervalMergeStep
from src.task.step.steps.interval_overlap import IntervalOverlapStep
from biopipe_sdk.testing import run_operator


checks = []


def record(name, ok, expected, actual):
    checks.append((name, bool(ok), str(expected)[:50], str(actual)[:50]))


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def _load_bed(path):
    return read_source(
        path, dims=["region", "field"],
        labels={"region": "auto", "field": "builtin"},
    )


def _decode_intervals(form, chrom_field="chrom",
                      start_field="chromStart", end_field="chromEnd"):
    labels = form.labels["field"]
    encs = form.info.get("encoders", {}).get("field", {})
    chrom_enc = encs.get(chrom_field)
    codes = form.data[:, labels[chrom_field]]
    starts = form.data[:, labels[start_field]]
    ends = form.data[:, labels[end_field]]
    if chrom_enc is not None:
        chroms = [chrom_enc.inverse[int(round(float(c)))] for c in codes]
    else:
        chroms = [str(int(c)) for c in codes]
    return list(zip(chroms, starts.tolist(), ends.tolist()))


def _independent_merge(intervals):
    by_chrom = {}
    for c, s, e in intervals:
        by_chrom.setdefault(c, []).append((float(s), float(e)))
    out = []
    for c in sorted(by_chrom):
        recs = sorted(by_chrom[c])
        cur_s, cur_e = recs[0]
        for s, e in recs[1:]:
            if s <= cur_e:
                cur_e = max(cur_e, e)
            else:
                out.append((c, cur_s, cur_e))
                cur_s, cur_e = s, e
        out.append((c, cur_s, cur_e))
    return out


def main():
    ccre_path = Path("tasks/interval_route_demo/input/cCREs.bed")
    reg_path = Path("tasks/interval_route_demo/input/ensembl_regulatory.bed")
    if not ccre_path.exists() or not reg_path.exists():
        print("missing demo data")
        sys.exit(1)

    section("1. Reader: ENCODE SCREEN V3 cCRE total")
    ccre = _load_bed(ccre_path)
    record("cCRE row count == 1063878",
            ccre.data.shape[0] == 1063878, 1063878, ccre.data.shape[0])
    reg = _load_bed(reg_path)
    record("Ensembl regulatory row count == 580745",
            reg.data.shape[0] == 580745, 580745, reg.data.shape[0])

    section("2. interval_stats vs independent NumPy")
    out_stats = run_operator(IntervalStatsStep, [ccre], {})
    stat_names = list(out_stats.labels["statistic"].keys())
    stats_by_chrom = {}
    for lbl, pos in out_stats.labels["chrom"].items():
        stats_by_chrom[lbl] = {
            name: float(out_stats.data[pos, stat_names.index(name)])
            for name in stat_names
        }
    intervals = _decode_intervals(ccre)
    by_chrom = {}
    for c, s, e in intervals:
        by_chrom.setdefault(c, []).append((float(s), float(e)))
    n_err = 0
    len_err = 0
    for c, recs in by_chrom.items():
        lengths = [e - s for s, e in recs]
        got = stats_by_chrom.get(c)
        if got is None:
            n_err += 1
            continue
        if abs(got["n_intervals"] - len(recs)) > 1e-3:
            n_err += 1
        if abs(got["total_bp"] - sum(lengths)) > 1.0:
            len_err += 1
    record("per-chromosome n_intervals matches independent",
            n_err == 0, "0 mismatches", n_err)
    record("per-chromosome total_bp matches independent",
            len_err == 0, "0 mismatches", len_err)

    section("3. interval_merge vs independent merge")
    out_merged = run_operator(IntervalMergeStep, [ccre], {"min_overlap": 0})
    merged_stats = out_merged.labels["statistic"]
    ours = sorted(
        (int(round(float(out_merged.data[i, merged_stats["start"]]))),
         int(round(float(out_merged.data[i, merged_stats["end"]]))))
        for i in range(out_merged.data.shape[0])
    )
    independent = _independent_merge(intervals)
    ref = sorted((int(round(s)), int(round(e))) for _, s, e in independent)
    record("merge: region count matches independent",
            len(ours) == len(ref), len(ref), len(ours))
    record("merge: per-region start/end match independent",
            ours == ref, "exact match", "match" if ours == ref else "mismatch")

    section("4. interval_overlap vs independent overlap (chr22 subset)")
    ccre_chr22 = [r for r in intervals if r[0] == "chr22"]
    reg_chr22 = [r for r in _decode_intervals(reg) if r[0] == "chr22"]
    out_pairs = run_operator(
        IntervalOverlapStep, [ccre, reg],
        {"min_overlap": 1, "max_output": 5_000_000},
    )
    pair_stats = out_pairs.labels["statistic"]
    chrom_col = out_pairs.info.get("chrom", [])
    n_chr22 = 0
    total_ov = 0.0
    for i in range(out_pairs.data.shape[0]):
        if i < len(chrom_col) and chrom_col[i] == "chr22":
            n_chr22 += 1
            total_ov += float(out_pairs.data[i, pair_stats["overlap_length"]])
    by_b = {}
    for c, s, e in reg_chr22:
        by_b.setdefault(c, []).append((float(s), float(e)))
    n_indep = 0
    total_indep = 0.0
    for c, s, e in ccre_chr22:
        for sb, eb in by_b.get(c, []):
            lo = max(float(s), sb)
            hi = min(float(e), eb)
            if hi - lo >= 1:
                n_indep += 1
                total_indep += hi - lo
    record("overlap chr22 pair count matches independent",
            n_chr22 == n_indep, n_indep, n_chr22)
    record("overlap chr22 total length matches independent",
            abs(total_ov - total_indep) < 1.0,
            f"{total_indep:.0f}", f"{total_ov:.0f}")

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
