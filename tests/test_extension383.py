"""Tests for genotype filtering and the LD r^2 matrix operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps import _ld_utils as ld
from src.task.step.steps.genotype_filter import GenotypeFilterStep
from src.task.step.steps.ld_matrix import LdMatrixStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def _genotypes(rows, positions, names=None, missing=None):
    data = np.asarray(rows, dtype=np.float32)
    names = names or [f"v{index}" for index in range(data.shape[0])]
    samples = [f"s{index}" for index in range(data.shape[1])]
    info = {"pos": list(positions), "chrom": ["22"] * data.shape[0]}
    if missing is not None:
        info["missing_code"] = missing
    return Form(
        data,
        dims=["variant", "sample"],
        labels={"variant": {name: index for index, name in enumerate(names)},
                "sample": {name: index for index, name in enumerate(samples)}},
        info=info,
        axis_info={"variant": ["pos", "chrom"]},
    )


G = [
    [0, 0, 1, 1, 2, 2],
    [0, 0, 1, 1, 2, 2],
    [2, 2, 1, 1, 0, 0],
    [0, 1, 0, 1, 0, 1],
]
POS = [100, 150, 1000, 1050]


def test_r2_matrix_matches_dosage_correlation():
    genotypes = np.asarray(G, dtype=np.float64)
    z = (genotypes - genotypes.mean(axis=1, keepdims=True)) / genotypes.std(axis=1, keepdims=True)
    matrix = ld.r2_matrix(z)
    assert matrix.shape == (4, 4)
    assert np.allclose(np.diag(matrix), 1.0)
    assert matrix[0, 1] == pytest.approx(1.0)
    assert matrix[0, 2] == pytest.approx(1.0)      # exact reverse genotype -> r = -1
    assert matrix[0, 3] < 1.0
    assert matrix[0, 3] == pytest.approx(matrix[3, 0])
    assert np.all(matrix >= 0.0) and np.all(matrix <= 1.0)


def test_select_variants_is_deterministic_and_keeps_endpoints():
    assert ld.select_variants(10, 4).tolist() == [0, 3, 6, 9]
    assert ld.select_variants(5, 0).tolist() == [0, 1, 2, 3, 4]
    assert ld.select_variants(5, 99).tolist() == [0, 1, 2, 3, 4]


def test_standardize_rejects_monomorphic_variants():
    genotypes = np.asarray([[0, 0, 0], [0, 1, 2]], dtype=np.float64)
    with pytest.raises(StepError):
        ld.standardize(genotypes, "test")


def test_ld_matrix_r2_values_follow_dosage_correlation():
    step = LdMatrixStep()
    step.name = "ld_matrix"
    ctx = Ctx({"output": "ld", "max_variants": 10, "min_maf": 0.01})
    step.run(ctx, [_genotypes(G, POS)])
    form = ctx["ld"]
    matrix = np.asarray(form.data)
    assert form.dims == ["variant", "variant_b"]
    assert matrix.shape == (4, 4)
    assert matrix[0, 0] == pytest.approx(1.0)
    assert matrix[0, 1] == pytest.approx(1.0)
    assert matrix[0, 2] == pytest.approx(1.0)
    assert matrix[0, 3] < 1.0
    assert matrix[0, 3] == pytest.approx(matrix[3, 0])
    assert form.labels["variant"] == {"v0": 0, "v1": 1, "v2": 2, "v3": 3}
    assert form.labels["variant_b"]["v2"] == 2
    assert form.info["n_variants"] == 4
    assert form.info["max_r2"] == pytest.approx(1.0)


def test_ld_matrix_subsamples_variants_by_stride():
    rows = G + [[0, 1, 0, 1, 0, 1]]
    step = LdMatrixStep()
    step.name = "ld_matrix"
    ctx = Ctx({"output": "ld", "max_variants": 3, "min_maf": 0.01})
    step.run(ctx, [_genotypes(rows, POS + [2000])])
    form = ctx["ld"]
    assert np.asarray(form.data).shape == (3, 3)
    assert sorted(form.labels["variant"]) == ["v0", "v2", "v4"]


def test_missing_and_monomorphic_variants_are_dropped():
    rows = G + [[0, 0, 0, 0, 0, 0], [0, np.nan, 1, 1, 2, 2]]
    step = LdMatrixStep()
    step.name = "ld_matrix"
    ctx = Ctx({"output": "ld", "max_variants": 10, "min_maf": 0.01})
    step.run(ctx, [_genotypes(rows, POS + [2000, 3000])])
    form = ctx["ld"]
    assert form.data.shape == (4, 4)
    assert form.info["n_dropped_maf"] == 1
    assert form.info["n_dropped_missing"] == 1


def test_genotype_filter_drops_low_maf_and_missing_variants():
    rows = [
        [0, 1, 2, 0, 1, 2],
        [0, 0, 0, 0, 0, 1],
        [0, 1, np.nan, np.nan, 2, 0],
        [2, 1, 0, 2, 1, 0],
    ]
    step = GenotypeFilterStep()
    step.name = "genotype_filter"
    ctx = Ctx({"output": "filtered", "min_maf": 0.1, "max_missing_rate": 0.2})
    step.run(ctx, [_genotypes(rows, [100, 200, 300, 400], missing=np.nan)])
    form = ctx["filtered"]
    assert form.dims == ["variant", "sample"]
    assert np.asarray(form.data).shape == (2, 6)
    assert form.labels["variant"] == {"v0": 0, "v3": 1}
    assert list(form.info["pos"]) == [100, 400]
    assert len(form.info["chrom"]) == 2
    assert form.axis_info.get("variant") == ["pos", "chrom"]
    assert form.get_parallel("pos", "variant").tolist() == [100, 400]
    assert form.info["n_input"] == 4
    assert form.info["n_kept"] == 2
    exported = step.export(ctx)
    assert exported["n_dropped_maf"] == 1
    assert exported["n_dropped_missing"] == 1
    assert exported["n_kept"] == 2


def test_genotype_filter_rejects_invalid_parameters():
    step = GenotypeFilterStep()
    step.name = "genotype_filter"
    ctx = Ctx({"min_maf": 0.9})
    with pytest.raises(StepError):
        step.run(ctx, [_genotypes(G, POS)])
    ctx = Ctx({"max_missing_rate": 1.5})
    with pytest.raises(StepError):
        step.run(ctx, [_genotypes(G, POS)])


def test_genotype_filter_requires_two_remaining_variants():
    rows = [[0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 1]]
    step = GenotypeFilterStep()
    step.name = "genotype_filter"
    ctx = Ctx({"min_maf": 0.2})
    with pytest.raises(StepError):
        step.run(ctx, [_genotypes(rows, [100, 200])])


def test_genotype_matrix_rejects_bad_shape_and_values():
    ctx = Ctx({})
    with pytest.raises(StepError):
        ld.genotype_matrix(_genotypes(G, POS), "variant", "other", "test")
    bad = _genotypes([[0, 3, 1, 1, 2, 2]] * 2, POS[:2])
    with pytest.raises(StepError):
        ld.genotype_matrix(bad, "variant", "sample", "test")
