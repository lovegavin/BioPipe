"""SOP verification for genotype Readers against independent tool APIs."""
from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np
import pytest

from src.reader import read_source

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / "tasks"


def _skip(path: Path):
    if not path.exists() or path.stat().st_size == 0:
        pytest.skip(f"real SOP fixture is not present: {path.relative_to(ROOT)}")


def _read(path, dims=("variant", "sample"), labels=None):
    labels = labels or {dims[0]: "builtin", dims[1]: "builtin"}
    return read_source(path, list(dims), labels)


def test_vcf_matches_pysam(tmp_path):
    source = TASKS / "vcf_demo/input/ALL.chr22.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz"
    _skip(source)
    pysam = pytest.importorskip("pysam")
    header, records = [], []
    with gzip.open(source, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("##"):
                header.append(line)
            elif line.startswith("#CHROM"):
                header.append(line)
                break
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            if fields[4] in (".", "") or "," in fields[4]:
                continue
            fmt = fields[8].split(":")
            if "GT" not in fmt:
                continue
            gt_index = fmt.index("GT")
            calls = [field.split(":")[gt_index] for field in fields[9:]]
            if not all(call in (".", "./.", ".|.") or len(call.replace("|", "/").split("/")) == 2 for call in calls):
                continue
            records.append(line)
            if len(records) >= 120:
                break
    assert records
    path = tmp_path / "subset.vcf"
    path.write_text("".join(header) + "".join(records), encoding="utf-8")

    form = _read(path)
    assert form.info["ploidy"] == 2

    reference = np.full((len(records), len(form.labels["sample"])), np.nan, dtype=np.float64)
    with pysam.VariantFile(str(path)) as vcf:
        samples = list(vcf.header.samples)
        for i, rec in enumerate(vcf):
            for j, sample in enumerate(samples):
                gt = rec.samples[sample].get("GT")
                if gt is None or any(a is None for a in gt):
                    continue
                reference[i, j] = sum(1 for a in gt if a == 1)
    assert list(form.labels["sample"]) == samples
    np.testing.assert_allclose(form.data, reference, equal_nan=True)


def test_plink1_matches_bed_reader():
    path = TASKS / "plink_demo/input/genotype.bed"
    _skip(path)
    bed_reader = pytest.importorskip("bed_reader")
    form = _read(path)
    with bed_reader.open_bed(str(path)) as bed:
        reference = bed.read()
        iid = list(bed.iid)
    assert form.data.shape == reference.T.shape
    assert list(form.labels["sample"]) == iid
    np.testing.assert_allclose(form.data[:20, :50], reference.T[:20, :50], equal_nan=True)


def test_plink2_matches_pgenlib():
    path = TASKS / "plink2_demo/input/genotype.pgen"
    _skip(path)
    pgenlib = pytest.importorskip("pgenlib")
    form = _read(path)

    pvar_path = path.with_suffix(".pvar")
    lines = [line for line in pvar_path.read_text(encoding="utf-8").splitlines()
             if line and not line.startswith("##")]
    header = lines[0].lstrip("#").split("\t")
    variants = [line.split("\t") for line in lines[1:]]
    alt_index = header.index("ALT")
    alt_counts = [len(row[alt_index].split(",")) if row[alt_index] not in (".", "") else 0
                  for row in variants]
    offsets = np.zeros(len(alt_counts) + 1, dtype=np.uintp)
    for i, count in enumerate(alt_counts):
        offsets[i + 1] = offsets[i] + 1 + count

    n_samples = len(form.labels["sample"])
    with pgenlib.PgenReader(str(path).encode(), raw_sample_ct=n_samples,
                            variant_ct=len(variants), allele_idx_offsets=offsets) as reader:
        buf = np.empty(n_samples, dtype=np.int8)
        reader.read(0, buf, allele_idx=1)
    expected = buf.astype(np.float32)
    expected[buf == -9] = np.nan
    np.testing.assert_allclose(form.data[0], expected, equal_nan=True)


def test_bgen_matches_bgen_reader():
    path = TASKS / "bgen_demo/input/example.bgen"
    _skip(path)
    bgen_reader = pytest.importorskip("bgen_reader")
    form = _read(path)
    with bgen_reader.open_bgen(str(path), verbose=False, allow_complex=False) as bgen:
        probs = bgen.read()
        variant_ids = [str(v) for v in bgen.ids]
        samples = [str(s) for s in bgen.samples]
        chromosomes = [str(v) for v in bgen.chromosomes]
        positions = [int(v) for v in bgen.positions]
    expected = (probs[:, :, 1] + 2.0 * probs[:, :, 2]).T.astype(np.float32)
    expected[probs.sum(axis=2).T == 0] = np.nan
    assert list(form.labels["sample"]) == samples
    assert len(form.labels["variant"]) == len(variant_ids)
    np.testing.assert_allclose(form.data, expected, equal_nan=True)
    assert form.info["representation"] == "dosage"
    assert form.info["ploidy"] == 2
    assert form.info["chrom"] == chromosomes
    assert form.info["pos"] == positions
    assert form.axis_info["variant"] == ["chrom", "pos"]
