"""Contract tests for genotype PCA, GRM and loading operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import StepError

from src.task.step.steps.genotype_grm import GenotypeGrmStep
from src.task.step.steps.genotype_pca import GenotypePcaStep
from src.task.step.steps.genotype_pca_loadings import GenotypePcaLoadingsStep
from src.task.step.steps import _genotype_matrix_utils as geno


HEADER = "##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\tS2\tS3\tS4\n"


def write_vcf(tmp_path, rows):
    path = tmp_path / "toy.vcf"
    path.write_text(HEADER + "".join(rows), encoding="utf-8")
    return path


ROWS = [
    "22\t100\t.\tA\tG\t.\t.\t.\tGT\t0/0\t0/1\t1/1\t1/1\n",
    "22\t200\t.\tC\tT\t.\t.\t.\tGT\t0/1\t0/1\t0/0\t1/1\n",
    "22\t300\t.\tG\tA\t.\t.\t.\tGT\t0/0\t0/0\t0/0\t0/0\n",
    "22\t400\t.\tAT\tA\t.\t.\t.\tGT\t0/1\t0/0\t0/0\t1/1\n",
    "22\t500\t.\tT\tC\t.\t.\t.\tGT\t./.\t0/1\t0/1\t0/0\n",
]


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def run_step(step, artifact, params):
    ctx = Ctx(params)
    step.name = step.definition["id"]
    step.run(ctx, [artifact])
    return ctx


class File:
    def __init__(self, path, fmt="vcf"):
        self.files = {"vcf": str(path)}
        self.format = fmt
        self.file_bytes = path.stat().st_size

    def validate(self):
        return None


def test_load_genotypes_skips_non_snp_and_keeps_monomorphic(tmp_path):
    path = write_vcf(tmp_path, ROWS)
    samples, variants, matrix = geno.load_genotypes(path)
    assert samples == ["S1", "S2", "S3", "S4"]
    assert len(variants) == 4
    assert variants[-1] == "22:500:T:C"
    assert matrix.shape == (4, 4)
    assert np.isnan(matrix[3, 0])
    assert matrix[2].tolist() == [0.0, 0.0, 0.0, 0.0]


def test_standardise_centres_and_imputes(tmp_path):
    path = write_vcf(tmp_path, ROWS)
    _samples, _variants, matrix = geno.load_genotypes(path)
    standard, used, frequency = geno.standardise(matrix, 0.0)
    assert used.tolist() == [0, 1, 3]
    assert standard.shape == matrix.shape
    assert np.allclose(standard[2], 0.0)
    assert np.allclose(standard[1].mean(), 0.0, atol=1e-12)
    assert frequency[0] == pytest.approx(0.625)


def test_grm_is_zt_z_over_total_variants(tmp_path):
    path = write_vcf(tmp_path, ROWS)
    _samples, _variants, matrix = geno.load_genotypes(path)
    standard, _used, _frequency = geno.standardise(matrix, 0.0)
    grm = geno.relationship_matrix(standard)
    expected = standard.T @ standard / 4.0
    assert np.allclose(grm, expected, atol=1e-12)
    assert grm.shape == (4, 4)
    assert np.allclose(np.diag(grm), np.diag(grm))


def test_pca_operator_outputs_scores_and_info(tmp_path):
    path = write_vcf(tmp_path, ROWS)
    ctx = run_step(GenotypePcaStep(), File(path), {"output": "pca", "n_components": 2, "maf": 0})
    form = ctx["pca"]
    assert form.dims == ["sample", "component"]
    assert form.data.shape == (4, 2)
    assert set(form.labels["sample"]) == {"S1", "S2", "S3", "S4"}
    assert form.info["eigenvalues"][0] >= form.info["eigenvalues"][1]
    assert sum(form.info["variance_explained"]) == pytest.approx(1.0)


def test_grm_operator_labels_square(tmp_path):
    path = write_vcf(tmp_path, ROWS)
    ctx = run_step(GenotypeGrmStep(), File(path), {"output": "grm", "maf": 0})
    form = ctx["grm"]
    assert form.dims == ["sample_a", "sample_b"]
    assert form.data.shape == (4, 4)
    assert list(form.labels["sample_a"]) == list(form.labels["sample_b"])
    assert form.info["n_variants"] == 4
    assert form.info["diagonal_mean"] > 0


def test_loadings_match_component_scores(tmp_path):
    path = write_vcf(tmp_path, ROWS)
    _samples, variants, matrix = geno.load_genotypes(path)
    standard, used, _frequency = geno.standardise(matrix, 0.0)
    grm = geno.relationship_matrix(standard)
    values, vectors = geno.pca_decomposition(grm, 2)
    expected = standard[used] @ vectors / (2.0 * np.sqrt(values))[None, :]

    ctx = run_step(GenotypePcaLoadingsStep(), File(path), {"output": "loadings", "n_components": 2, "maf": 0})
    form = ctx["loadings"]
    assert form.data.shape == (4, 2)
    assert np.allclose(form.data[used], expected, atol=1e-6)
    assert np.allclose(form.data[2], 0.0)
    assert form.info["n_variants_used"] == 3


def test_maf_filter_drops_monomorphic(tmp_path):
    path = write_vcf(tmp_path, ROWS)
    ctx = run_step(GenotypeGrmStep(), File(path), {"output": "grm", "maf": 0.05})
    form = ctx["grm"]
    assert form.info["n_variants_used"] == 3


def test_empty_after_filter_raises(tmp_path):
    rows = ["22\t100\t.\tA\tG\t.\t.\t.\tGT\t0/0\t0/0\t0/0\t0/0\n"]
    path = write_vcf(tmp_path, rows)
    step = GenotypePcaStep()
    with pytest.raises(StepError, match="no variant passed"):
        run_step(step, File(path), {"output": "pca", "n_components": 2, "maf": 0.0})


def test_missing_gt_becomes_nan(tmp_path):
    path = write_vcf(tmp_path, ["22\t900\t.\tA\tC\t.\t.\t.\tGT\t./.\t0/1\t0/0\t1/1\n"])
    _samples, _variants, matrix = geno.load_genotypes(path)
    assert np.isnan(matrix[0, 0])
    assert matrix[0, 1] == 1.0
