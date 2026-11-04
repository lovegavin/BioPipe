"""Population-genetics operators checked against scikit-allel 1.3.13.

Every statistic is compared value by value with the scikit-allel function
that defines it, and the failure paths are asserted explicitly. Window
semantics follow ``allel.stats.window.position_windows``: the first window
starts at the first annotated position, windows advance by ``step_size``
(default ``window_size``) and the last window is clipped to the final
position.
"""
from __future__ import annotations

import numpy as np
import pytest
from scipy.spatial.distance import squareform

allel = pytest.importorskip("allel")

from src.core import Form, StepError
from src.task.step.steps.ld_decay import LdDecayStep
from src.task.step.steps.nucleotide_diversity import NucleotideDiversityStep
from src.task.step.steps.site_frequency_spectrum import SiteFrequencySpectrumStep
from src.task.step.steps.tajimas_d import TajimasDStep
from src.task.step.steps.watterson_theta import WattersonThetaStep


class Ctx(dict):
    """Minimal execution context matching the step runner."""

    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)


def _form(data, pos, chrom=None, ploidy=2, representation="hard_call"):
    values = np.asarray(data, dtype=np.float32)
    n_variants, n_samples = values.shape
    labels = {
        "variant": {str(index): index for index in range(n_variants)},
        "sample": {f"sample_{index}": index for index in range(n_samples)},
    }
    info = {"missing_code": np.nan}
    if ploidy is not None:
        info["ploidy"] = ploidy
    if representation is not None:
        info["representation"] = representation
    axis_info = {}
    if pos is not None:
        info["pos"] = [float(value) for value in pos]
        axis_info["variant"] = ["pos"]
    if chrom is not None:
        info["chrom"] = [str(name) for name in chrom]
        axis_info["variant"] = ["chrom", "pos"]
    form = Form(data=values, dims=["variant", "sample"], labels=labels,
                info=info, axis_info=axis_info)
    form.validate()
    return form


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    out = ctx[params.get("output", step.name)]
    return out, step.export(ctx)


def _allele_counts(data, ploidy=2):
    counts = []
    for row in np.asarray(data, dtype=float):
        called = row[np.isfinite(row)]
        alt = int(np.sum(called))
        an = int(called.size) * ploidy
        counts.append([an - alt, alt])
    return np.asarray(counts, dtype=int)


GENOTYPES = np.array([
    [0, 0, 0, 0],
    [0, 0, 0, 1],
    [0, 0, 1, 1],
    [0, 1, 1, 1],
    [1, 1, 1, 1],
    [0, 1, 1, 2],
    [0, 0, 1, 2],
    [0, 1, 2, 2],
    [1, 1, 2, 2],
    [0, 2, 2, 2],
    [1, 2, 2, 2],
    [2, 2, 2, 2],
], dtype=float)
POSITIONS = np.array([100, 120, 140, 160, 180, 200, 220, 240, 260, 280, 300, 320])
CHROM = ["chr1"] * len(POSITIONS)
WINDOW_PARAMS = {"window_size": 100, "step_size": 50}


def test_tajima_d_whole_input_matches_allel():
    form = _form(GENOTYPES, POSITIONS, CHROM)
    out, info = _run(TajimasDStep(), {}, form)
    counts = _allele_counts(GENOTYPES)
    expected = allel.tajima_d(counts)
    assert np.isfinite(expected)
    mpd = allel.mean_pairwise_difference(counts, fill=0)
    harmonic = float(np.sum(1.0 / np.arange(1, 8)))
    row = out.data[0]
    assert out.dims == ["window", "statistic"]
    assert list(out.labels["statistic"].keys()) == [
        "start", "end", "n_variants", "n_segregating", "pi", "theta_w", "tajima_d"
    ]
    assert row[2] == 12
    assert row[3] == 10
    assert row[4] == pytest.approx(float(np.sum(mpd)), rel=1e-5)
    assert row[5] == pytest.approx(10.0 / harmonic, rel=1e-5)
    assert row[6] == pytest.approx(float(expected), rel=1e-5)
    assert info["n_chromosomes"] == 8


def test_tajima_d_windows_match_allel():
    form = _form(GENOTYPES, POSITIONS, CHROM)
    out, _ = _run(TajimasDStep(), WINDOW_PARAMS, form)
    counts = _allele_counts(GENOTYPES)
    expected, windows, sites = allel.windowed_tajima_d(
        POSITIONS, counts, size=100, step=50
    )
    assert np.isfinite(expected).all()
    assert out.data.shape[0] == windows.shape[0]
    np.testing.assert_allclose(out.data[:, 0], windows[:, 0].astype(float), rtol=0)
    np.testing.assert_allclose(out.data[:, 1], windows[:, 1].astype(float), rtol=0)
    np.testing.assert_array_equal(out.data[:, 2].astype(int), sites)
    np.testing.assert_allclose(out.data[:, 6], expected.astype(float), rtol=1e-5,
                               equal_nan=True)
    assert next(iter(out.labels["window"].keys())) == "chr1:100-199"


def test_nucleotide_diversity_windows_match_allel():
    form = _form(GENOTYPES, POSITIONS, CHROM)
    out, _ = _run(NucleotideDiversityStep(), WINDOW_PARAMS, form)
    counts = _allele_counts(GENOTYPES)
    pi, windows, n_bases, sites = allel.windowed_diversity(
        POSITIONS, counts, size=100, step=50
    )
    assert np.isfinite(pi).all()
    np.testing.assert_allclose(out.data[:, 0], windows[:, 0].astype(float), rtol=0)
    np.testing.assert_allclose(out.data[:, 1], windows[:, 1].astype(float), rtol=0)
    np.testing.assert_array_equal(out.data[:, 2].astype(int), sites)
    np.testing.assert_allclose(out.data[:, 3], n_bases.astype(float), rtol=0)
    np.testing.assert_allclose(out.data[:, 5], pi.astype(float), rtol=1e-5,
                               equal_nan=True)
    np.testing.assert_allclose(out.data[:, 4], (pi * n_bases).astype(float), rtol=1e-5)


def test_watterson_theta_windows_match_allel():
    form = _form(GENOTYPES, POSITIONS, CHROM)
    out, info = _run(WattersonThetaStep(), WINDOW_PARAMS, form)
    counts = _allele_counts(GENOTYPES)
    theta, windows, n_bases, sites = allel.windowed_watterson_theta(
        POSITIONS, counts, size=100, step=50
    )
    assert np.isfinite(theta).all()
    np.testing.assert_allclose(out.data[:, 0], windows[:, 0].astype(float), rtol=0)
    np.testing.assert_allclose(out.data[:, 1], windows[:, 1].astype(float), rtol=0)
    np.testing.assert_array_equal(out.data[:, 2].astype(int), sites)
    np.testing.assert_allclose(out.data[:, 3], n_bases.astype(float), rtol=0)
    np.testing.assert_allclose(out.data[:, 6], theta.astype(float), rtol=1e-5)
    assert info["n_chromosomes"] == 8
    whole, _ = _run(WattersonThetaStep(), {}, form)
    expected = allel.watterson_theta(POSITIONS, counts)
    assert whole.data[0, 6] == pytest.approx(float(expected), rel=1e-5)
    assert int(whole.data[0, 2]) == len(POSITIONS)


def test_site_frequency_spectrum_unfolded_matches_allel():
    data = np.array([
        [0, 0, 0, 0],
        [0, 0, 0, 1],
        [0, 0, 1, 1],
        [0, 1, 1, 1],
        [1, 1, 1, 1],
        [1, 1, 2, 2],
    ], dtype=float)
    form = _form(data, [10, 20, 30, 40, 50, 60], ["chr1"] * 6)
    out, info = _run(SiteFrequencySpectrumStep(), {}, form)
    expected = allel.sfs(np.array([0, 1, 2, 3, 4, 6]), n=8)
    np.testing.assert_array_equal(out.data[:, 0].astype(int), expected[1:8])
    np.testing.assert_allclose(out.data[:, 1], expected[1:8] / 6.0, rtol=1e-6)
    assert list(out.labels["frequency"].keys()) == [str(i) for i in range(1, 8)]
    assert info["n_chromosomes"] == 8
    assert info["n_segregating"] == 5


def test_site_frequency_spectrum_folded_matches_allel():
    data = np.array([
        [0, 0, 0, 0],
        [0, 0, 0, 1],
        [0, 0, 1, 1],
        [0, 1, 1, 1],
        [1, 1, 1, 1],
        [1, 1, 2, 2],
    ], dtype=float)
    form = _form(data, [10, 20, 30, 40, 50, 60], ["chr1"] * 6)
    out, _ = _run(SiteFrequencySpectrumStep(), {"folded": True}, form)
    expected = allel.sfs_folded(_allele_counts(data), n=8)
    np.testing.assert_array_equal(out.data[:, 0].astype(int), expected[1:5])
    assert list(out.labels["frequency"].keys()) == ["1", "2", "3", "4"]


def test_ld_decay_matches_rogers_huff_r():
    rng = np.random.default_rng(20261101)
    data = rng.integers(0, 3, size=(10, 8)).astype(float)
    positions = np.array([10, 15, 25, 30, 40, 55, 60, 75, 80, 95])
    form = _form(data, positions, ["chr1"] * 10)
    out, info = _run(LdDecayStep(), {"max_distance": 100, "n_bins": 5}, form)
    r_squared = squareform(allel.rogers_huff_r(data.astype("i1")) ** 2)
    width = 20.0
    buckets = [[] for _ in range(5)]
    for i in range(data.shape[0]):
        for j in range(i + 1, data.shape[0]):
            distance = positions[j] - positions[i]
            bucket = min(int(np.ceil(distance / width)) - 1, 4)
            buckets[bucket].append(r_squared[i, j])
    for bucket, values in enumerate(buckets):
        values = np.clip(np.asarray(values, dtype=float), 0.0, 1.0)
        assert int(out.data[bucket, 2]) == values.size
        if values.size:
            assert out.data[bucket, 3] == pytest.approx(float(values.mean()), rel=1e-5)
            assert out.data[bucket, 4] == pytest.approx(float(np.median(values)),
                                                        rel=1e-5)
    assert info["n_pairs"] == 45
    assert int(out.data[:, 2].sum()) == 45
    assert info["chromosome"] == "chr1"


def test_nucleotide_diversity_hand_computed():
    form = _form(GENOTYPES, POSITIONS, CHROM)
    out, _ = _run(NucleotideDiversityStep(), {}, form)
    alt = _allele_counts(GENOTYPES)[:, 1].astype(float)
    expected = float(np.sum(2.0 * alt * (8.0 - alt) / (8.0 * 7.0)))
    assert expected == pytest.approx(4.535714285714286, rel=1e-9)
    assert out.data[0, 4] == pytest.approx(expected, rel=1e-6)
    assert out.data[0, 4] == pytest.approx(4.535714285714286, rel=1e-6)


def test_tajima_d_hand_computed_theta_w():
    form = _form(GENOTYPES, POSITIONS, CHROM)
    out, _ = _run(TajimasDStep(), {}, form)
    harmonic = float(np.sum(1.0 / np.arange(1, 8)))
    assert out.data[0, 5] == pytest.approx(10.0 / harmonic, rel=1e-6)
    assert out.data[0, 5] == pytest.approx(3.8567493, rel=1e-5)


def test_operators_require_ploidy():
    form = _form(GENOTYPES, POSITIONS, CHROM, ploidy=None)
    with pytest.raises(StepError, match="ploidy"):
        _run(TajimasDStep(), {}, form)


def test_operators_reject_dosage_representation():
    form = _form(GENOTYPES, POSITIONS, CHROM, representation="dosage")
    with pytest.raises(StepError, match="hard-call"):
        _run(NucleotideDiversityStep(), {}, form)


def test_operators_reject_non_integer_counts():
    data = GENOTYPES.copy()
    data[1, 0] = 0.5
    form = _form(data, POSITIONS, CHROM)
    with pytest.raises(StepError, match="integers"):
        _run(WattersonThetaStep(), {}, form)


def test_operators_reject_out_of_range_counts():
    data = GENOTYPES.copy()
    data[1, 0] = 3.0
    form = _form(data, POSITIONS, CHROM)
    with pytest.raises(StepError, match=r"\[0, 2\]"):
        _run(TajimasDStep(), {}, form)


def test_windowed_analysis_requires_positions():
    form = _form(GENOTYPES, None, None)
    with pytest.raises(StepError, match="pos"):
        _run(NucleotideDiversityStep(), WINDOW_PARAMS, form)


def test_tajima_d_respects_min_sites():
    form = _form(GENOTYPES, POSITIONS, CHROM)
    out, _ = _run(TajimasDStep(), {"min_sites": 11}, form)
    assert np.isnan(out.data[0, 6])


def test_ld_decay_requires_single_chromosome():
    rng = np.random.default_rng(7)
    data = rng.integers(0, 3, size=(8, 6)).astype(float)
    positions = np.arange(10, 90, 10)
    form = _form(data, positions, ["chr1"] * 4 + ["chr2"] * 4)
    with pytest.raises(StepError, match="multiple chromosomes"):
        _run(LdDecayStep(), {"max_distance": 100, "n_bins": 5}, form)


def test_ld_decay_pair_guard():
    rng = np.random.default_rng(11)
    data = rng.integers(0, 3, size=(10, 6)).astype(float)
    positions = np.arange(10, 110, 10)
    form = _form(data, positions, ["chr1"] * 10)
    with pytest.raises(StepError, match="max_pairs"):
        _run(LdDecayStep(), {"max_distance": 100, "n_bins": 5, "max_pairs": 10}, form)
