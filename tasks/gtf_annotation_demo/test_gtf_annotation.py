"""Standalone verification of GFF3/GTF annotation operators."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core import Form, StepError
from src.reader import read_source
from src.task.step.steps.gff_feature_stats import GffFeatureStatsStep
from src.task.step.steps.gene_structure import GeneStructureStep
from src.task.step.steps.annotation_gaps import AnnotationGapsStep
from biopipe_sdk.testing import run_operator


GTF_BODY = (
    'chrI\tensembl\tgene\t1\t500\t.\t+\t.\tgene_id "GENE1"; transcript_id "GENE1_mRNA";\n'
    'chrI\tensembl\tmRNA\t1\t500\t.\t+\t.\tgene_id "GENE1"; transcript_id "GENE1_mRNA";\n'
    'chrI\tensembl\texon\t1\t200\t.\t+\t.\tgene_id "GENE1"; transcript_id "GENE1_mRNA";\n'
    'chrI\tensembl\texon\t300\t500\t.\t+\t.\tgene_id "GENE1"; transcript_id "GENE1_mRNA";\n'
    'chrI\tensembl\tCDS\t50\t200\t.\t+\t0\tgene_id "GENE1"; transcript_id "GENE1_mRNA";\n'
    'chrI\tensembl\tCDS\t300\t500\t.\t+\t0\tgene_id "GENE1"; transcript_id "GENE1_mRNA";\n'
    'chrI\tensembl\tgene\t1000\t1500\t.\t-\t.\tgene_id "GENE2"; transcript_id "GENE2_mRNA";\n'
    'chrI\tensembl\tmRNA\t1000\t1500\t.\t-\t.\tgene_id "GENE2"; transcript_id "GENE2_mRNA";\n'
    'chrI\tensembl\texon\t1000\t1500\t.\t-\t.\tgene_id "GENE2"; transcript_id "GENE2_mRNA";\n'
)

GFF3_BODY = (
    '##gff-version 3\n'
    'chrI\tensembl\tgene\t1\t500\t.\t+\t.\tID=gene:GENE1;biotype=protein_coding\n'
    'chrI\tensembl\tmRNA\t1\t500\t.\t+\t.\tID=GENE1_mRNA;Parent=gene:GENE1\n'
    'chrI\tensembl\texon\t1\t200\t.\t+\t.\tID=GENE1_exon1;Parent=GENE1_mRNA\n'
    'chrI\tensembl\texon\t300\t500\t.\t+\t.\tID=GENE1_exon2;Parent=GENE1_mRNA\n'
    'chrI\tensembl\tCDS\t50\t200\t.\t+\t0\tID=GENE1_CDS1;Parent=GENE1_mRNA\n'
    'chrI\tensembl\tCDS\t300\t500\t.\t+\t0\tID=GENE1_CDS2;Parent=GENE1_mRNA\n'
    'chrI\tensembl\tgene\t1000\t1500\t.\t-\t.\tID=gene:GENE2;biotype=protein_coding\n'
    'chrI\tensembl\tmRNA\t1000\t1500\t.\t-\t.\tID=GENE2_mRNA;Parent=gene:GENE2\n'
    'chrI\tensembl\texon\t1000\t1500\t.\t-\t.\tID=GENE2_exon1;Parent=GENE2_mRNA\n'
)


def _write_gtf(tmpdir, body, name="test.gtf", newline="\n"):
    path = Path(tmpdir) / name
    path.write_text(body.replace("\n", newline), encoding="utf-8")
    return path


def _read_gtf(tmpdir, body, newline="\n"):
    path = _write_gtf(tmpdir, body, newline=newline)
    return read_source(
        path,
        dims=["record", "field"],
        labels={"record": "auto", "field": "builtin"},
    )


def _read_gff3(tmpdir, body):
    path = Path(tmpdir) / "test.gff3"
    path.write_text(body, encoding="utf-8")
    return read_source(
        path,
        dims=["record", "field"],
        labels={"record": "auto", "field": "builtin"},
    )


def _forms_equal(a, b):
    if a.dims != b.dims:
        return False
    if a.labels != b.labels:
        return False
    if a.data.shape != b.data.shape:
        return False
    if not np.allclose(a.data, b.data, equal_nan=True):
        return False
    return True


def _stat(out, feature, stat):
    i = out.labels["feature_type"][feature]
    j = out.labels["statistic"][stat]
    return float(out.data[i, j])


def test_gtf_reader_lf_crlf_consistent():
    with TemporaryDirectory() as d:
        lf = _read_gtf(d, GTF_BODY, newline="\n")
        crlf = _read_gtf(d, GTF_BODY, newline="\r\n")
        assert _forms_equal(lf, crlf), "LF and CRLF GTF must produce identical Forms"
    print("  gtf reader LF/CRLF consistent          ok")


def test_gff_feature_stats_hand_counted_gtf():
    with TemporaryDirectory() as d:
        form = _read_gtf(d, GTF_BODY)
    out = run_operator(GffFeatureStatsStep, [form], {})

    assert out.dims == ["feature_type", "statistic"]
    assert _stat(out, "gene", "count") == 2.0
    assert _stat(out, "gene", "total_length") == 1001.0
    assert np.isclose(_stat(out, "gene", "mean_length"), 500.5)
    assert _stat(out, "gene", "min_length") == 500.0
    assert _stat(out, "gene", "max_length") == 501.0
    assert _stat(out, "gene", "mean_exons_per_gene") == 1.5

    assert _stat(out, "exon", "count") == 3.0
    assert _stat(out, "exon", "total_length") == 902.0
    assert np.isclose(_stat(out, "exon", "mean_length"), 902.0 / 3.0)
    assert _stat(out, "exon", "min_length") == 200.0
    assert _stat(out, "exon", "max_length") == 501.0

    assert _stat(out, "CDS", "count") == 2.0
    assert _stat(out, "CDS", "total_length") == 352.0
    assert np.isclose(_stat(out, "CDS", "mean_length"), 176.0)
    print("  gff_feature_stats on GTF hand-counted  ok")


def test_gene_structure_hand_counted_gtf():
    with TemporaryDirectory() as d:
        form = _read_gtf(d, GTF_BODY)
    out = run_operator(GeneStructureStep, [form], {})

    assert out.dims == ["gene", "statistic"]
    assert set(out.labels["gene"]) == {"GENE1", "GENE2"}

    i = out.labels["gene"]["GENE1"]
    assert float(out.data[i, out.labels["statistic"]["n_exons"]]) == 2.0
    assert float(out.data[i, out.labels["statistic"]["n_introns"]]) == 1.0
    assert float(out.data[i, out.labels["statistic"]["gene_length"]]) == 500.0
    assert float(out.data[i, out.labels["statistic"]["cds_total"]]) == 352.0
    assert float(out.data[i, out.labels["statistic"]["strand"]]) == 1.0

    j = out.labels["gene"]["GENE2"]
    assert float(out.data[j, out.labels["statistic"]["n_exons"]]) == 1.0
    assert float(out.data[j, out.labels["statistic"]["n_introns"]]) == 0.0
    assert float(out.data[j, out.labels["statistic"]["gene_length"]]) == 501.0
    assert float(out.data[j, out.labels["statistic"]["cds_total"]]) == 0.0
    assert float(out.data[j, out.labels["statistic"]["strand"]]) == -1.0
    print("  gene_structure on GTF hand-counted     ok")


def test_annotation_gaps_hand_counted_gtf():
    with TemporaryDirectory() as d:
        form = _read_gtf(d, GTF_BODY)
    out = run_operator(AnnotationGapsStep, [form], {})

    assert out.dims == ["gap", "statistic"]
    assert out.data.shape == (1, 5)
    assert float(out.data[0, out.labels["statistic"]["gap_length"]]) == 499.0
    assert float(out.data[0, out.labels["statistic"]["left_start"]]) == 1.0
    assert float(out.data[0, out.labels["statistic"]["left_end"]]) == 500.0
    assert float(out.data[0, out.labels["statistic"]["right_start"]]) == 1000.0
    assert float(out.data[0, out.labels["statistic"]["right_end"]]) == 1500.0
    assert out.info["seqid"] == ["chrI"]
    assert out.info["left_gene"] == ["chrI:1-500"]
    assert out.info["right_gene"] == ["chrI:1000-1500"]
    print("  annotation_gaps on GTF hand-counted    ok")


def test_gtf_gff3_equivalent_outputs():
    with TemporaryDirectory() as d:
        gtf_form = _read_gtf(d, GTF_BODY)
        gff3_form = _read_gff3(d, GFF3_BODY)

    fs_gtf = run_operator(GffFeatureStatsStep, [gtf_form], {})
    fs_gff3 = run_operator(GffFeatureStatsStep, [gff3_form], {})
    assert set(fs_gtf.labels["feature_type"]) == set(fs_gff3.labels["feature_type"])
    for t in fs_gtf.labels["feature_type"]:
        for s in fs_gtf.labels["statistic"]:
            a = _stat(fs_gtf, t, s)
            b = _stat(fs_gff3, t, s)
            assert np.isclose(a, b), f"gff_feature_stats mismatch {t}/{s}: {a} vs {b}"

    gs_gtf = run_operator(GeneStructureStep, [gtf_form], {})
    gs_gff3 = run_operator(GeneStructureStep, [gff3_form], {})
    assert set(gs_gtf.labels["gene"]) == set(gs_gff3.labels["gene"])
    for g in gs_gtf.labels["gene"]:
        i = gs_gtf.labels["gene"][g]
        j = gs_gff3.labels["gene"][g]
        for s in gs_gtf.labels["statistic"]:
            a = float(gs_gtf.data[i, gs_gtf.labels["statistic"][s]])
            b = float(gs_gff3.data[j, gs_gff3.labels["statistic"][s]])
            assert np.isclose(a, b), f"gene_structure mismatch {g}/{s}: {a} vs {b}"

    ag_gtf = run_operator(AnnotationGapsStep, [gtf_form], {})
    ag_gff3 = run_operator(AnnotationGapsStep, [gff3_form], {})
    assert ag_gtf.data.shape == ag_gff3.data.shape
    assert ag_gtf.info["seqid"] == ag_gff3.info["seqid"]
    assert ag_gtf.info["left_gene"] == ag_gff3.info["left_gene"]
    assert ag_gtf.info["right_gene"] == ag_gff3.info["right_gene"]
    assert np.allclose(ag_gtf.data, ag_gff3.data, equal_nan=True)
    print("  GTF / GFF3 outputs identical           ok")


def test_wrong_representation_rejected():
    """A Form without any feature-type column must be rejected."""
    with TemporaryDirectory() as d:
        form = _read_gtf(d, GTF_BODY)
    seqname_enc = form.info["encoders"]["field"]["seqname"]
    # Rebuild a valid Form that only carries the seqname column.
    bad = Form(
        data=form.data[:, :1].copy(),
        dims=form.dims,
        labels={
            "record": dict(form.labels["record"]),
            "field": {"seqname": 0},
        },
        info={
            "missing_code": np.nan,
            "encoders": {"field": {"seqname": seqname_enc}},
        },
    )
    try:
        run_operator(GffFeatureStatsStep, [bad], {})
        raise AssertionError("expected rejection")
    except AssertionError:
        raise
    except StepError as exc:
        assert "no 'type' label" in str(exc), str(exc)
    print("  missing feature-type column rejected   ok")


def test_missing_encoder_rejected():
    """A Form whose feature-type column has no encoder must be rejected."""
    with TemporaryDirectory() as d:
        form = _read_gtf(d, GTF_BODY)
    encoders = dict(form.info["encoders"]["field"])
    encoders.pop("feature")
    form.info["encoders"]["field"] = encoders
    try:
        run_operator(GffFeatureStatsStep, [form], {})
        raise AssertionError("expected rejection")
    except AssertionError:
        raise
    except StepError as exc:
        assert "not encoded" in str(exc), str(exc)
    print("  missing feature encoder rejected       ok")


def main():
    print("gtf_annotation verification")
    test_gtf_reader_lf_crlf_consistent()
    test_gff_feature_stats_hand_counted_gtf()
    test_gene_structure_hand_counted_gtf()
    test_annotation_gaps_hand_counted_gtf()
    test_gtf_gff3_equivalent_outputs()
    test_wrong_representation_rejected()
    test_missing_encoder_rejected()
    print()
    print("all checks passed")


if __name__ == "__main__":
    main()
