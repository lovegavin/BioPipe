"""External-baseline verification of the GFF3/GTF annotation operators.

Runs on the real Ensembl S. cerevisiae R64-1-1 release 110 GTF and
GFF3 files downloaded by tasks/gtf_annotation_demo/download.sh.

External references:
  - SGD chromosome lengths for S. cerevisiae R64-1-1
  - Ensembl release 110 annotation statistics
  - Cross-format comparison against the same Ensembl release.

Known Ensembl differences between the GTF and GFF3 dumps of the
same annotation:

  * gene rows: GTF collapses ncRNA and pseudogene records into
    type "gene", GFF3 keeps them as distinct feature types. GTF has
    7127 gene rows, GFF3 has 6600.
  * exon rows: identical interval sets (7485 unique intervals).
  * CDS rows: Ensembl GTF excludes the stop codon from the CDS
    interval, GFF3 includes it. The two CDS interval sets differ by
    3 bp per coding transcript.

Known BioPipe limitation exercised by this dataset:

  * gene_structure attributes exons and CDS by span containment.
    Nested genes (one gene fully contained inside another on the
    same sequence) are therefore mis-attributed. S. cerevisiae has
    one such case (YPL250W-A contains YPL249C-A). Those genes are
    excluded from the cross-format cds_total comparison.

Run with: python tasks/verify_gtf_annotation.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")

from src.core import StepError
from src.reader import read_source
from src.task.step.steps.gff_feature_stats import GffFeatureStatsStep
from src.task.step.steps.gene_structure import GeneStructureStep
from src.task.step.steps.annotation_gaps import AnnotationGapsStep
from biopipe_sdk.testing import run_operator


checks = []


def record(name, ok, expected, actual):
    checks.append((name, bool(ok), str(expected)[:60], str(actual)[:60]))


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


# SGD chromosome lengths for S. cerevisiae R64-1-1 (bp).
SGD_CHR_LENGTHS = {
    "I": 230218, "II": 813184, "III": 316620, "IV": 1531933,
    "V": 576874, "VI": 270161, "VII": 1090946, "VIII": 562643,
    "IX": 439888, "X": 745751, "XI": 666816, "XII": 1078177,
    "XIII": 924431, "XIV": 784333, "XV": 1091291, "XVI": 948066,
    "Mito": 85779,
}


def _read(path):
    return read_source(
        Path(path),
        dims=["record", "field"],
        labels={"record": "auto", "field": "builtin"},
    )


def _feat_count(out, feature):
    if feature not in out.labels["feature_type"]:
        return 0
    i = out.labels["feature_type"][feature]
    j = out.labels["statistic"]["count"]
    return int(round(float(out.data[i, j])))


def _nested_gene_ids(form):
    """Return the set of gene IDs whose span is inside another gene."""
    labels = form.labels["field"]
    encs = form.info["encoders"]["field"]
    seqid_col = "seqname" if "seqname" in labels else "seqid"
    type_col = "feature" if "feature" in labels else "type"
    attr_col = "attribute" if "attribute" in labels else "attributes"
    from src.task.step.steps._annotation_columns import parse_gene_id

    te = encs[type_col]; ae = encs[attr_col]; se = encs[seqid_col]
    genes = []
    for i in range(form.data.shape[0]):
        if te.inverse[int(round(float(form.data[i, labels[type_col]])))] != "gene":
            continue
        raw = ae.inverse[int(round(float(form.data[i, labels[attr_col]])))]
        gid = parse_gene_id(str(raw))
        if gid is None:
            continue
        sid = se.inverse[int(round(float(form.data[i, labels[seqid_col]])))]
        s = float(form.data[i, labels["start"]])
        e = float(form.data[i, labels["end"]])
        genes.append((gid, sid, s, e))

    nested = set()
    for gid, sid, s, e in genes:
        for gid2, sid2, s2, e2 in genes:
            if gid == gid2 or sid != sid2:
                continue
            if s2 <= s and e <= e2 and (s2, e2) != (s, e):
                nested.add(gid)
                break
    return nested


def main():
    gtf_path = Path("tasks/gtf_annotation_demo/input/saccharomyces_cerevisiae.gtf.gz")
    gff3_path = Path("tasks/gtf_annotation_demo/input/saccharomyces_cerevisiae.gff3.gz")

    if not gtf_path.exists():
        print(f"missing {gtf_path}. Run tasks/gtf_annotation_demo/download.sh first.")
        sys.exit(1)
    if not gff3_path.exists():
        print(f"missing {gff3_path}. Run tasks/gtf_annotation_demo/download.sh first.")
        sys.exit(1)

    section("1. GTF reader - chromosome set matches SGD R64-1-1")
    gtf = _read(gtf_path)
    seqid_col = "seqname" if "seqname" in gtf.labels["field"] else "seqid"
    enc = gtf.info["encoders"]["field"][seqid_col]
    chroms = sorted({enc.inverse[int(round(float(c)))]
                     for c in gtf.data[:, gtf.labels["field"][seqid_col]]})
    record("chromosome count == 17 (SGD)", len(chroms) == 17, 17, len(chroms))
    record("chr I present", "I" in chroms, "I in set", "I" in chroms)
    record("chr XVI present", "XVI" in chroms, "XVI in set", "XVI" in chroms)
    record("Mito present", "Mito" in chroms, "Mito in set", "Mito" in chroms)

    section("2. gene_structure - chromosome coordinates within SGD lengths")
    gs = run_operator(GeneStructureStep, [gtf], {})

    type_col = "feature" if "feature" in gtf.labels["field"] else "type"
    type_enc = gtf.info["encoders"]["field"][type_col]
    type_codes = gtf.data[:, gtf.labels["field"][type_col]]
    starts = gtf.data[:, gtf.labels["field"]["start"]]
    ends = gtf.data[:, gtf.labels["field"]["end"]]
    seq_codes = gtf.data[:, gtf.labels["field"][seqid_col]]

    max_end_by_chr = {}
    for i in range(gtf.data.shape[0]):
        if type_enc.inverse[int(round(float(type_codes[i])))] != "gene":
            continue
        sid = enc.inverse[int(round(float(seq_codes[i])))]
        max_end_by_chr[sid] = max(max_end_by_chr.get(sid, 0.0), float(ends[i]))

    ok_all = True
    for sid, mx in max_end_by_chr.items():
        limit = SGD_CHR_LENGTHS.get(sid)
        if limit is not None and mx > limit:
            ok_all = False
    record("all gene ends <= SGD chromosome length", ok_all, True, ok_all)

    section("3. gff_feature_stats - Ensembl release 110 known counts")
    fs_gtf = run_operator(GffFeatureStatsStep, [gtf], {})
    n_genes = _feat_count(fs_gtf, "gene")
    n_exons = _feat_count(fs_gtf, "exon")
    record("GTF gene count in [6500, 7300] (SGD/Ensembl)",
            6500 <= n_genes <= 7300, "6500..7300", n_genes)
    record("exon count > gene count", n_exons > n_genes, ">n_genes", n_exons)
    record("CDS count > 0", _feat_count(fs_gtf, "CDS") > 0,
            ">0", _feat_count(fs_gtf, "CDS"))

    section("4. Cross-format comparison GTF vs GFF3 (same Ensembl release)")
    gff3 = _read(gff3_path)
    fs_gff3 = run_operator(GffFeatureStatsStep, [gff3], {})
    gs_gff3 = run_operator(GeneStructureStep, [gff3], {})

    for feat in ("exon", "CDS"):
        a = _feat_count(fs_gtf, feat)
        b = _feat_count(fs_gff3, feat)
        record(f"{feat} row count equal across formats", a == b, a, b)

    n_genes_gff3 = _feat_count(fs_gff3, "gene")
    record("GFF3 gene count in [6500, 7300]",
            6500 <= n_genes_gff3 <= 7300, "6500..7300", n_genes_gff3)
    record("GTF gene count >= GFF3 gene count (GTF collapses ncRNA)",
            n_genes >= n_genes_gff3, f">={n_genes_gff3}", n_genes)

    # Detect nested genes. gene_structure attributes CDS by span
    # containment, so a nested gene's CDS rows land inside the
    # outer gene as well. Exclude these genes from the cross-format
    # cds_total comparison.
    nested_gtf = _nested_gene_ids(gtf)
    nested_gff3 = _nested_gene_ids(gff3)
    nested = nested_gtf | nested_gff3
    print(f"  [info] nested genes (excluded from cds_total check): "
          f"{sorted(nested)}")

    gtf_genes = gs.labels["gene"]
    gff3_genes = gs_gff3.labels["gene"]
    common = sorted(set(gtf_genes) & set(gff3_genes))
    same_span = 0
    exon_mismatches = 0
    cds_bad = 0
    cds_exact = 0
    cds_multiples_of_3 = 0
    skipped_nested = 0
    max_cds_delta = 0.0
    for g in common:
        i = gtf_genes[g]
        j = gff3_genes[g]
        if float(gs.data[i, gs.labels["statistic"]["gene_length"]]) != \
           float(gs_gff3.data[j, gs_gff3.labels["statistic"]["gene_length"]]):
            continue
        same_span += 1
        ne_a = float(gs.data[i, gs.labels["statistic"]["n_exons"]])
        ne_b = float(gs_gff3.data[j, gs_gff3.labels["statistic"]["n_exons"]])
        if ne_a != ne_b:
            exon_mismatches += 1
        if g in nested:
            skipped_nested += 1
            continue
        cd_a = float(gs.data[i, gs.labels["statistic"]["cds_total"]])
        cd_b = float(gs_gff3.data[j, gs_gff3.labels["statistic"]["cds_total"]])
        delta = abs(cd_a - cd_b)
        if delta == 0:
            cds_exact += 1
        elif delta % 3 == 0:
            cds_multiples_of_3 += 1
            max_cds_delta = max(max_cds_delta, delta)
        else:
            cds_bad += 1

    record("common genes with same span: n_exons match exactly",
            exon_mismatches == 0 and same_span > 5000,
            "0 mismatches, >5000 genes",
            f"{exon_mismatches} mismatches, {same_span} genes")
    record("non-nested common genes: cds_total equal or differs by 3n",
            cds_bad == 0 and (cds_exact + cds_multiples_of_3) > 5000,
            "0 non-3-multiples",
            f"{cds_bad} bad, {cds_exact} exact, "
            f"{cds_multiples_of_3} /3, {skipped_nested} nested skipped")
    print(f"  [info] max CDS delta between formats: {max_cds_delta:.0f} bp "
          f"(Ensembl stop-codon convention)")

    ag_gtf = run_operator(AnnotationGapsStep, [gtf], {"min_gap": 500})
    ag_gff3 = run_operator(AnnotationGapsStep, [gff3], {"min_gap": 500})
    record("GTF gaps: all gap_length >= 500",
            ag_gtf.data.shape[0] > 0 and
            bool((ag_gtf.data[:, 0] >= 500).all()),
            "all >=500", f"n={ag_gtf.data.shape[0]}")
    record("GFF3 gaps: all gap_length >= 500",
            ag_gff3.data.shape[0] > 0 and
            bool((ag_gff3.data[:, 0] >= 500).all()),
            "all >=500", f"n={ag_gff3.data.shape[0]}")

    section("5. Negative cases")
    import copy
    bad = copy.deepcopy(gtf)
    encs = dict(bad.info["encoders"]["field"])
    encs.pop(type_col)
    bad.info["encoders"]["field"] = encs
    try:
        run_operator(GffFeatureStatsStep, [bad], {})
        record("missing feature encoder raises StepError", False, "StepError", "no error")
    except StepError:
        record("missing feature encoder raises StepError", True, "StepError", "StepError")
    except Exception as exc:
        record("missing feature encoder raises StepError", False, "StepError", type(exc).__name__)

    ag_huge = run_operator(AnnotationGapsStep, [gtf], {"min_gap": 10**9})
    record("min_gap 1e9 yields empty gaps", ag_huge.data.shape[0] == 0,
            0, ag_huge.data.shape[0])

    print()
    print("=" * 78)
    print("Verification summary")
    print("=" * 78)
    print(f"{'':<4}{'check':<56}{'expected':>12}{'actual':>14}")
    print("-" * 78)
    for name, ok, expected, actual in checks:
        status = "PASS" if ok else "FAIL"
        print(f"{status}  {name:<56}{expected:>12}{actual:>14}")
    print("-" * 78)
    passed = sum(1 for _, ok, _, _ in checks if ok)
    print(f"{passed}/{len(checks)} checks passed")
    if passed < len(checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
