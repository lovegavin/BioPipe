"""Tests for the 1.2.0 Arrow reader, seasonal decomposition and Fst family."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.core import Form, ReaderError, StepError
from src.reader.readers._encoder import get_encoder
from src.reader.readers.arrow_reader import ArrowReader
from src.task.step.steps.dxy import DxyStep
from src.task.step.steps.heterozygosity import HeterozygosityStep
from src.task.step.steps.patterson_fst import PattersonFstStep
from src.task.step.steps.seasonal_decompose import SeasonalDecomposeStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def _table_form(data, dims, labels, info=None):
    return Form(
        data=np.asarray(data, dtype=np.float32),
        dims=list(dims),
        labels=labels,
        info={"missing_code": np.nan, **(info or {})},
    )


def _write_arrow(df: pd.DataFrame, path, kind: str) -> None:
    pyarrow = pytest.importorskip("pyarrow")
    table = pyarrow.Table.from_pandas(df, preserve_index=False)
    if kind == "feather":
        import pyarrow.feather as feather
        feather.write_feather(table, path)
    elif kind == "ipc":
        import pyarrow.ipc as ipc
        with ipc.new_file(path, table.schema) as writer:
            writer.write_table(table)
    else:
        import pyarrow.orc as orc
        orc.write_table(table, path)


# ---------------------------------------------------------------- ArrowReader

@pytest.mark.parametrize("kind", ["feather", "ipc", "orc"])
def test_arrow_reader_reads_each_container(tmp_path, kind):
    pytest.importorskip("pyarrow")
    df = pd.DataFrame({"a": [1.5, 2.5, 3.5], "b": [4.0, 5.0, 6.0]})
    path = tmp_path / f"table.{'feather' if kind == 'feather' else kind if kind == 'ipc' else 'orc'}"
    _write_arrow(df, path, kind)
    form = ArrowReader().read(
        path, ["sample", "feature"], {"sample": "auto", "feature": "builtin"}
    )
    assert form.dims == ["sample", "feature"]
    assert list(form.labels["feature"]) == ["a", "b"]
    np.testing.assert_allclose(form.data, df.to_numpy(), rtol=0, atol=1e-7)
    assert form.info["missing_code"] is np.nan or np.isnan(form.info["missing_code"])


def test_arrow_reader_accepts_ipc_stream(tmp_path):
    pyarrow = pytest.importorskip("pyarrow")
    import pyarrow.ipc as ipc
    table = pyarrow.table({"x": [1, 2], "y": [3, 4]})
    path = tmp_path / "stream.arrow"
    with ipc.new_stream(path, table.schema) as writer:
        writer.write_table(table)
    form = ArrowReader().read(
        path, ["row", "col"], {"row": "auto", "col": "builtin"}
    )
    np.testing.assert_allclose(form.data, [[1, 3], [2, 4]])


def test_arrow_reader_encodes_text_and_extracts_row_labels(tmp_path):
    pytest.importorskip("pyarrow")
    df = pd.DataFrame({
        "name": ["alpha", "beta", "gamma"],
        "value": [1.0, 2.0, 3.0],
        "group": ["case", "control", "case"],
    })
    path = tmp_path / "table.feather"
    _write_arrow(df, path, "feather")
    form = ArrowReader().read(
        path,
        ["sample", "feature"],
        {"sample": {"feature": 0}, "feature": "builtin"},
    )
    assert list(form.labels["sample"]) == ["alpha", "beta", "gamma"]
    assert list(form.labels["feature"]) == ["value", "group"]
    assert form.info["encoders"]["feature"]["group"] is not None
    assert set(np.unique(form.data[:, 1])) == {0.0, 1.0}


def test_arrow_reader_rejects_unknown_format(tmp_path):
    pytest.importorskip("pyarrow")
    path = tmp_path / "table.feather"
    _write_arrow(pd.DataFrame({"a": [1.0]}), path, "feather")
    with pytest.raises(ReaderError, match="unknown format"):
        ArrowReader().read(path, ["sample", "feature"], {}, format="nope")


def test_arrow_reader_rejects_three_dims(tmp_path):
    with pytest.raises(ReaderError, match="exactly two dims"):
        ArrowReader().read(tmp_path / "x.arrow", ["a", "b", "c"], {})


# ----------------------------------------------------- seasonal_decompose

def _series_form(values):
    data = np.asarray(values, dtype=np.float64).reshape(-1, 1)
    return _table_form(
        data,
        ["sample", "feature"],
        {"sample": {f"t{i}": i for i in range(data.shape[0])},
         "feature": {"value": 0}},
    )


def test_seasonal_decompose_matches_statsmodels_additive():
    from statsmodels.tsa.seasonal import seasonal_decompose as sm_decompose

    t = np.arange(48, dtype=np.float64)
    values = 10 + 0.3 * t + 2 * np.sin(2 * np.pi * t / 12) + 0.4 * np.cos(2 * np.pi * t / 12)
    form, info = _run(
        SeasonalDecomposeStep(),
        {"value_label": "value", "period": 12},
        [_series_form(values)],
    )
    expected = sm_decompose(values, model="additive", period=12, two_sided=True)
    data = form.data.astype(np.float64)
    np.testing.assert_allclose(data[:, 0], values, rtol=0, atol=1e-5)
    np.testing.assert_allclose(data[:, 1], expected.trend, rtol=0, atol=1e-4, equal_nan=True)
    np.testing.assert_allclose(data[:, 2], expected.seasonal, rtol=0, atol=1e-4, equal_nan=True)
    np.testing.assert_allclose(data[:, 3], expected.resid, rtol=0, atol=1e-4, equal_nan=True)
    assert np.isnan(data[0, 1]) and np.isnan(data[-1, 1])
    assert abs(float(np.nansum(data[:, 2]))) < 1e-3
    assert info == {"period": 12, "model": "additive", "two_sided": True, "n": 48}


def test_seasonal_decompose_multiplicative():
    t = np.arange(36, dtype=np.float64)
    values = (5.0 + 0.2 * t) * (1.0 + 0.1 * np.sin(2 * np.pi * t / 12))
    form, info = _run(
        SeasonalDecomposeStep(),
        {"value_label": "value", "period": 12, "model": "multiplicative"},
        [_series_form(values)],
    )
    data = form.data.astype(np.float64)
    finite = np.isfinite(data[:, 1])
    np.testing.assert_allclose(
        data[finite, 0], data[finite, 1] * data[finite, 2] * data[finite, 3],
        rtol=1e-4, atol=1e-4,
    )
    assert abs(float(np.nanmean(data[:, 2])) - 1.0) < 1e-3
    assert info["model"] == "multiplicative"


def test_seasonal_decompose_rejects_short_series():
    with pytest.raises(StepError, match="two full periods"):
        _run(
            SeasonalDecomposeStep(),
            {"value_label": "value", "period": 12},
            [_series_form(np.arange(20, dtype=np.float64))],
        )


def test_seasonal_decompose_rejects_nonpositive_multiplicative():
    with pytest.raises(StepError, match="strictly positive"):
        _run(
            SeasonalDecomposeStep(),
            {"value_label": "value", "period": 6, "model": "multiplicative"},
            [_series_form(np.arange(24, dtype=np.float64) - 5.0)],
        )


# ------------------------------------------------- Fst family / heterozygosity

GENOTYPES = np.asarray(
    [
        [0, 0, 1, 2, 1, 0],
        [2, 2, 1, 1, 0, 0],
        [0, 1, 0, 0, 1, 1],
        [1, 1, 2, 2, 2, 1],
        [0, 2, 0, 2, 0, 2],
        [1, 0, 1, 0, np.nan, 1],
    ],
    dtype=np.float64,
)
POPULATIONS = ["A", "A", "A", "B", "B", "B"]


def _genotype_form():
    return _table_form(
        GENOTYPES,
        ["variant", "sample"],
        {"sample": {f"s{i}": i for i in range(GENOTYPES.shape[1])},
         "variant": {f"v{i}": i for i in range(GENOTYPES.shape[0])}},
        info={"ploidy": 2, "representation": "hard_call"},
    )


def _meta_form():
    encoder = get_encoder("labelencoder")
    codes = encoder.fit_transform(POPULATIONS)
    data = np.asarray(codes, dtype=np.float64).reshape(-1, 1)
    return _table_form(
        data,
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(len(POPULATIONS))},
         "feature": {"pop": 0}},
        info={"encoders": {"feature": {"pop": encoder}}},
    )


def _allel_counts(indices):
    out = []
    for row in GENOTYPES[:, indices]:
        row = row[np.isfinite(row)]
        an = float(len(row)) * 2.0
        alt = float(np.sum(row))
        out.append([an - alt, alt])
    return np.asarray(out, dtype=np.int64)


def test_patterson_fst_matches_scikit_allel():
    allel = pytest.importorskip("allel")
    form, info = _run(
        PattersonFstStep(),
        {"group_label": "pop", "group_a": "A", "group_b": "B"},
        [_genotype_form(), _meta_form()],
    )
    aca = _allel_counts([0, 1, 2])
    acb = _allel_counts([3, 4, 5])
    num, den = allel.patterson_fst(aca, acb)
    data = form.data.astype(np.float64)
    np.testing.assert_allclose(data[:, 0], num, rtol=1e-5, atol=1e-5)
    np.testing.assert_allclose(data[:, 1], den, rtol=1e-5, atol=1e-5)
    np.testing.assert_allclose(data[:, 2], num / den, rtol=1e-5, atol=1e-5)
    assert list(form.labels["statistic"]) == ["num", "den", "fst", "n_a", "n_b", "p_a", "p_b"]
    assert info["n_a"] == 3 and info["n_b"] == 3


def test_dxy_matches_scikit_allel():
    allel = pytest.importorskip("allel")
    form, _ = _run(
        DxyStep(),
        {"group_label": "pop", "group_a": "A", "group_b": "B"},
        [_genotype_form(), _meta_form()],
    )
    allel_counts = _allel_counts([0, 1, 2])
    allel_counts_b = _allel_counts([3, 4, 5])
    expected = allel.mean_pairwise_difference_between(allel_counts, allel_counts_b)
    data = form.data.astype(np.float64)
    np.testing.assert_allclose(data[:, 0], expected, rtol=1e-6, atol=1e-6)


def test_heterozygosity_matches_scikit_allel():
    allel = pytest.importorskip("allel")
    form, info = _run(HeterozygosityStep(), {}, [_genotype_form()])
    g = np.full(GENOTYPES.shape + (2,), -1, dtype=np.int64)
    for i in range(GENOTYPES.shape[0]):
        for j in range(GENOTYPES.shape[1]):
            value = GENOTYPES[i, j]
            if not np.isfinite(value):
                continue
            if value == 0:
                g[i, j] = [0, 0]
            elif value == 1:
                g[i, j] = [0, 1]
            else:
                g[i, j] = [1, 1]
    genotype_array = allel.GenotypeArray(g)
    ho = allel.heterozygosity_observed(genotype_array)
    af = genotype_array.count_alleles().to_frequencies()
    he = allel.heterozygosity_expected(af, ploidy=2)
    data = form.data.astype(np.float64)
    np.testing.assert_allclose(data[:, 2], ho, rtol=1e-6, atol=1e-6)
    np.testing.assert_allclose(data[:, 3], he, rtol=1e-6, atol=1e-6)
    np.testing.assert_allclose(data[:, 4], 1.0 - ho / he, rtol=1e-5, atol=1e-5)
    assert info["n_variants"] == GENOTYPES.shape[0]
    assert info["n_samples"] == GENOTYPES.shape[1]


def _meta_form_with(populations):
    encoder = get_encoder("labelencoder")
    codes = encoder.fit_transform(populations)
    data = np.asarray(codes, dtype=np.float64).reshape(-1, 1)
    return _table_form(
        data,
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(len(populations))},
         "feature": {"pop": 0}},
        info={"encoders": {"feature": {"pop": encoder}}},
    )


def test_fst_family_needs_two_samples_per_group():
    meta = _meta_form_with(["A", "B", "B", "B", "B", "B"])
    with pytest.raises(StepError, match="at least two genotyped samples"):
        _run(
            DxyStep(),
            {"group_label": "pop", "group_a": "A", "group_b": "B"},
            [_genotype_form(), meta],
        )


def test_fst_family_rejects_unknown_group():
    with pytest.raises(StepError, match="not found"):
        _run(
            PattersonFstStep(),
            {"group_label": "pop", "group_a": "A", "group_b": "missing"},
            [_genotype_form(), _meta_form()],
        )


def test_heterozygosity_rejects_non_diploid():
    haploid = _table_form(
        np.where(np.isfinite(GENOTYPES), np.minimum(GENOTYPES, 1.0), np.nan),
        ["variant", "sample"],
        {"sample": {f"s{i}": i for i in range(GENOTYPES.shape[1])},
         "variant": {f"v{i}": i for i in range(GENOTYPES.shape[0])}},
        info={"ploidy": 1, "representation": "hard_call"},
    )
    with pytest.raises(StepError, match="diploid"):
        _run(HeterozygosityStep(), {}, [haploid])
