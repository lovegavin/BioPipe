"""Contract tests for the VCF sample QC operators."""
from __future__ import annotations

import gzip
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "library" / "seed" / "src"))

from src.core import FileArtifact  # noqa: E402

from src.task.step.steps import vcf_hardy_weinberg, vcf_sample_stats, vcf_site_missingness  # noqa: E402
from src.task.step.steps._vcf_qc_utils import (  # noqa: E402
    hwe_exact,
    sample_summary,
    site_missingness,
)

VCF = """##fileformat=VCFv4.2
##contig=<ID=22,length=1000>
##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\tS2\tS3
22\t100\t.\tA\tG\t.\tPASS\t.\tGT\t0/0\t0/1\t1/1
22\t200\t.\tC\tT\t.\tPASS\t.\tGT\t0/1\t./.\t0/0
22\t300\t.\tG\tA\t.\tPASS\t.\tGT\t1/1\t0/0\t./.
22\t400\t.\tT\tC\t.\tPASS\t.\tGT\t0/0\t0/0\t0/0
"""


@pytest.fixture()
def vcf_path(tmp_path):
    path = tmp_path / "sample.vcf.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(VCF)
    return str(path)


def artifact(path, kind="vcf"):
    return FileArtifact(kind, {"variants": path}, info={"representation": kind})


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def test_sample_summary_counts(vcf_path):
    summary = sample_summary(vcf_path)
    assert summary["n_samples"] == 3
    assert summary["n_sites"] == 4
    s1 = summary["samples"]["S1"]
    assert (s1["called"], s1["missing"], s1["het"], s1["hom_ref"], s1["hom_alt"]) == (4, 0, 1, 2, 1)
    s2 = summary["samples"]["S2"]
    assert (s2["called"], s2["missing"], s2["het"]) == (3, 1, 1)


def test_site_missingness_rates(vcf_path):
    rows = site_missingness(vcf_path)
    assert [row["site"] for row in rows] == ["22:100", "22:200", "22:300", "22:400"]
    assert rows[1]["n_missing"] == 1
    assert rows[1]["call_rate"] == pytest.approx(2 / 3)
    assert rows[3]["call_rate"] == 1.0


def test_hwe_exact_known_cases():
    assert hwe_exact(0, 10, 0) == pytest.approx(1.0)
    assert hwe_exact(10, 0, 0) < 0.01
    p = hwe_exact(5, 5, 0)
    assert 0.0 <= p <= 1.0


def test_hwe_operator_output(vcf_path):
    step = vcf_hardy_weinberg.VcfHardyWeinbergStep()
    ctx = Ctx({"output": "hwe"})
    step.run(ctx, [artifact(vcf_path)])
    form = ctx["hwe"]
    assert form.dims == ["site", "statistic"]
    assert form.data.shape == (4, 5)
    assert list(form.labels["statistic"]) == list(vcf_hardy_weinberg.STATISTICS)
    row = form.data[0]
    assert row[0] == 3 and row[1] == 1
    assert row[4] == pytest.approx(1.0, abs=1e-9)


def test_sample_stats_operator_output(vcf_path):
    step = vcf_sample_stats.VcfSampleStatsStep()
    ctx = Ctx({"output": "sample_stats"})
    step.run(ctx, [artifact(vcf_path)])
    form = ctx["sample_stats"]
    assert form.dims == ["sample", "statistic"]
    assert form.data.shape == (3, 8)
    assert form.labels["sample"]["S1"] == 0
    assert form.data[0][2] == pytest.approx(1.0)
    exported = step.export(ctx)
    assert exported["n_samples"] == 3


def test_missingness_operator_output(vcf_path):
    step = vcf_site_missingness.VcfSiteMissingnessStep()
    ctx = Ctx({"output": "missing"})
    step.run(ctx, [artifact(vcf_path)])
    form = ctx["missing"]
    assert form.data.shape == (4, 3)
    assert form.data[1][1] == 1.0


def test_rejects_missing_file(tmp_path):
    step = vcf_sample_stats.VcfSampleStatsStep()
    ctx = Ctx()
    with pytest.raises(Exception):
        step.run(ctx, [artifact(str(tmp_path / "nope.vcf"))])
