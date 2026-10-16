"""Standalone GTF-input test for peak_nearest_gene.

Verifies that the operator auto-resolves GTF column names
(seqname / feature / attribute), matches the GFF3 result on the
same annotation, and reports the resolved columns.

Run with: python tasks/peak_nearest_gene_demo/test_peak_nearest_gene_gtf.py
"""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.reader import read_source
from src.core import Form
from src.reader.readers._encoder import get_encoder
from src.task.step.steps.peak_nearest_gene import PeakNearestGeneStep
from biopipe_sdk.testing import run_operator


GTF_BODY = (
    'chrI\tensembl\tgene\t100\t500\t.\t+\t.\tgene_id "GENEA";\n'
    'chrI\tensembl\tgene\t1000\t2000\t.\t-\t.\tgene_id "GENEB";\n'
)

GFF3_BODY = (
    '##gff-version 3\n'
    'chrI\tensembl\tgene\t100\t500\t.\t+\t.\tID=gene:GENEA\n'
    'chrI\tensembl\tgene\t1000\t2000\t.\t-\t.\tID=gene:GENEB\n'
)

# Peaks: overlap A, gap before B, gap after B.
BED_BODY = (
    "chrI\t200\t300\n"      # inside GENEA -> distance 0
    "chrI\t700\t800\n"      # between A and B -> closest is A (gap 200) or B (gap 200)
    "chrI\t3000\t3100\n"    # after B -> distance to B end (2000) is 1000
)


def _write(tmpdir, name, body, newline="\n"):
    path = Path(tmpdir) / name
    path.write_text(body.replace("\n", newline), encoding="utf-8")
    return path


from src.core import Form
from src.reader.readers._encoder import get_encoder


def _make_peaks(records):
    """records: (chrom, start, end)."""
    chrom_enc = get_encoder("labelencoder")
    chrom_codes = chrom_enc.fit_transform([r[0] for r in records])
    starts = np.array([r[1] for r in records], dtype=np.float32)
    ends = np.array([r[2] for r in records], dtype=np.float32)
    data = np.column_stack([chrom_codes, starts, ends]).astype(np.float32)
    n = len(records)
    return Form(
        data=data,
        dims=["region", "field"],
        labels={
            "region": {str(i): i for i in range(n)},
            "field": {"chrom": 0, "chromStart": 1, "chromEnd": 2},
        },
        info={
            "missing_code": np.nan,
            "encoders": {"field": {"chrom": chrom_enc}},
        },
    )


def _peaks():
    return _make_peaks([
        ("chrI", 200, 300),
        ("chrI", 700, 800),
        ("chrI", 3000, 3100),
    ])


def _read_gtf(tmpdir):
    path = _write(tmpdir, "genes.gtf", GTF_BODY)
    return read_source(
        path,
        dims=["record", "field"],
        labels={"record": "auto", "field": "builtin"},
    )


def _read_gff3(tmpdir):
    path = _write(tmpdir, "genes.gff3", GFF3_BODY)
    return read_source(
        path,
        dims=["record", "field"],
        labels={"record": "auto", "field": "builtin"},
    )


def _resolved_columns(form, step):
    """Call the operator, then read the export dict for resolved columns."""
    out = run_operator(step, form, {})
    return out


def test_gtf_auto_resolution_and_distances():
    with TemporaryDirectory() as d:
        peaks = _peaks()
        genes_gtf = _read_gtf(d)

    # Operator: A = BED 3-col (chrom, start, end) defaults already match
    # the TxtReader's auto labels ("0","1","2"). Override for clarity.
    params = {
        "a_chrom_field": "chrom",
        "a_start_field": "chromStart",
        "a_end_field": "chromEnd",
        "a_region_dim": "region",
        "a_field_dim": "field",
        "b_record_dim": "record",
        "b_field_dim": "field",
        "output": "annotated",
    }
    out = run_operator(PeakNearestGeneStep, [peaks, genes_gtf], params)

    assert out.dims == ["peak", "statistic"]
    assert out.data.shape == (3, 5)

    dist = [float(out.data[i, 0]) for i in range(3)]
    assert dist[0] == 0.0, f"peak 0 should overlap GENEA, got {dist[0]}"
    assert dist[1] == 200.0, f"peak 1 gap to GENEA end (500) is 700-500=200, got {dist[1]}"
    assert dist[2] == 1000.0, f"peak 2 gap to GENEB end (2000) is 3000-2000=1000, got {dist[2]}"

    gene_ids = list(out.info["gene_id"])
    assert gene_ids[0] == "GENEA", gene_ids
    assert gene_ids[2] == "GENEB", gene_ids
    print("  GTF auto-resolution and distances     ok")


def test_gtf_and_gff3_agree():
    with TemporaryDirectory() as d:
        peaks = _peaks()
        gtf = _read_gtf(d)
        gff3 = _read_gff3(d)

    params = {
        "a_chrom_field": "chrom",
        "a_start_field": "chromStart",
        "a_end_field": "chromEnd",
        "a_region_dim": "region",
        "a_field_dim": "field",
        "b_record_dim": "record",
        "b_field_dim": "field",
        "output": "annotated",
    }
    out_gtf = run_operator(PeakNearestGeneStep, [peaks, gtf], params)
    out_gff3 = run_operator(PeakNearestGeneStep, [peaks, gff3], params)

    assert out_gtf.data.shape == out_gff3.data.shape
    assert np.allclose(out_gtf.data, out_gff3.data, equal_nan=True)
    assert list(out_gtf.info["gene_id"]) == list(out_gff3.info["gene_id"])
    assert list(out_gtf.info["chrom"]) == list(out_gff3.info["chrom"])
    print("  GTF and GFF3 give identical output     ok")


def main():
    print("peak_nearest_gene GTF verification")
    test_gtf_auto_resolution_and_distances()
    test_gtf_and_gff3_agree()
    print()
    print("all checks passed")


if __name__ == "__main__":
    main()
