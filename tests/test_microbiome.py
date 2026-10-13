"""Numerical, contract and admission checks for the upstream 16S adapters."""
import numpy as np
import pytest
import json
from pathlib import Path

from src.core import Form
from src.task import STEPS, Context, run
from src.task.step.steps._microbiome import estimate


def form(values, dims, info=None, axes=None):
    data = np.asarray(values, dtype=np.float32)
    return Form(data, dims, {d: {f"{d}{i}": i for i in range(data.shape[a])} for a, d in enumerate(dims)},
                {"missing_code": np.nan, **(info or {})}, axes or {})


def execute(tmp_path, operator, inputs, params):
    ctx = Context(tmp_path, {})
    for i, data in enumerate(inputs):
        ctx[f"input{i}"] = data
    run(ctx, [{"name": operator, "inputs": [f"input{i}" for i in range(len(inputs))], "params": params}])
    return ctx[params.get("output", operator)]


def test_diversity_nd_shape_values_and_projected_metadata(tmp_path):
    data = form([[[1, 1], [2, 0]], [[0, 0], [3, 1]]], ["batch", "sample", "species"],
                {"batch_note": ["a", "b"], "taxon": ["x", "y"], "representation": "counts"},
                {"batch": ["batch_note"], "species": ["taxon"]})
    result = execute(tmp_path, "diversity", [data], {"dim": "species", "metrics": ["shannon", "richness"]})
    assert result.dims == ["batch", "sample", "metric"] and result.data.shape == (2, 2, 2)
    assert result.data[0, 0, 0] == pytest.approx(np.log(2))
    assert np.isnan(result.data[1, 0, 0]) and result.data[1, 0, 1] == 0
    assert result.axis_info == {"batch": ["batch_note"]} and "taxon" not in result.info
    assert result.info["representation"] == "diversity" and data.info["representation"] == "counts"


@pytest.mark.parametrize("operator,metric", [("distance_matrix", "braycurtis"), ("correlation", "spearman")])
def test_pairwise_results_and_metadata(tmp_path, operator, metric):
    data = form([[1, 2, 3], [3, 2, 1]], ["sample", "species"], {"site": ["a", "b"]}, {"sample": ["site"]})
    result = execute(tmp_path, operator, [data], {"dim": "sample", "metric": metric})
    assert result.dims == ["sample", "sample_b"] and result.axis_info == data.axis_info
    assert result.data[0, 1] == pytest.approx(1 / 3 if operator == "distance_matrix" else -1)
    assert result.info["site"] == ["a", "b"]
    with pytest.raises(Exception, match="positions"):
        execute(tmp_path, operator, [data], {"dim": "sample", "max_positions": 1})


def test_reduce_pcoa_preserves_observation_metadata_and_rejects_wrong_label_order(tmp_path):
    data = form([[0, 1, 2], [1, 0, 1], [2, 1, 0]], ["sample", "sample_b"], {"site": ["a", "b", "c"]}, {"sample": ["site"]})
    data.labels["sample_b"] = dict(data.labels["sample"])
    scores = execute(tmp_path, "reduce", [data], {"dim": "sample", "method": "pcoa", "n_components": 2})
    assert scores.data.shape == (3, 1)
    np.testing.assert_allclose(np.abs(scores.data[:, 0, None] - scores.data[None, :, 0]), data.data, atol=1e-5)
    assert scores.axis_info == {"sample": ["site"]}
    data.labels["sample_b"] = {"sample0": 1, "sample1": 0, "sample2": 2}
    with pytest.raises(Exception, match="square distance"):
        execute(tmp_path, "reduce", [data], {"dim": "sample", "method": "pcoa"})


def test_join_keeps_annotations_in_matched_order_and_converts_missing(tmp_path):
    data = form([[10, -1], [20, 30], [40, 50]], ["sample", "feature"],
                {"missing_code": -1, "site": ["a", "b", "c"], "units": ["u", "v"]},
                {"sample": ["site"], "feature": ["units"]})
    meta = form([[7], [-9]], ["sample", "column"], {"missing_code": -9})
    meta.labels["sample"] = {"sample2": 0, "sample0": 1}
    result = execute(tmp_path, "join", [data, meta], {"dim": "sample", "prefix": "meta_"})
    assert list(result.labels["sample"]) == ["sample0", "sample2"]
    assert result.info["site"] == ["a", "c"] and result.info["units"] == ["u", "v", None]
    assert np.isnan(result.data[0, 1]) and np.isnan(result.data[0, 2])
    assert result.data[1, 2] == 7 and data.info["units"] == ["u", "v"]


def test_aggregate_preserves_feature_annotations(tmp_path):
    data = form([[1, 3], [3, 5], [8, 10]], ["sample", "species"], {"taxon": ["a", "b"]}, {"species": ["taxon"]})
    groups = form([[0], [0], [1]], ["sample", "feature"])
    result = execute(tmp_path, "aggregate", [data, groups], {"dim": "sample", "group_col": "feature0", "method": "mean"})
    np.testing.assert_array_equal(result.data, [[2, 4], [8, 10]])
    assert result.dims == ["feature", "species"] and result.axis_info == {"species": ["taxon"]}


def test_quadratic_estimators_do_not_read_payload_and_memory_admission_rejects(tmp_path):
    data = form(np.zeros((2000, 2)), ["sample", "feature"])
    workspace, output = estimate("distance_matrix", [data], {"dim": "sample"}, {})
    assert output >= 2000 * 2000 * 4 and workspace >= 2000 * 2000 * 16
    ctx = Context(tmp_path, {"runtime": {"memory": {"enabled": True, "budget_mb": 2}}})
    try:
        ctx["x"] = data
        with pytest.raises(Exception, match="(?i)(budget|memory|预算|内存)"):
            run(ctx, [{"name": "distance_matrix", "inputs": ["x"], "params": {"dim": "sample"}}])
        assert ctx._run_status == "failed"
    finally:
        ctx.finalize()


def test_strict_new_operator_parameters_are_validated(tmp_path):
    data = form([[1, 2], [2, 1]], ["sample", "species"])
    with pytest.raises(ValueError, match="Additional properties"):
        execute(tmp_path, "distance_matrix", [data], {"dim": "sample", "typo": True})
    assert not STEPS["reduce"].supports_streaming
    assert STEPS["describe"].supports_streaming
    bundle = json.loads((Path(__file__).resolve().parents[1] / 'src/web/builtin_routes.json').read_text(encoding='utf-8'))
    assert next(r for r in bundle['routes'] if r['name'] == '16S Microbiome')['graph']['memory']['enabled']


def test_gini_excludes_missing_entries_instead_of_adding_zeros(tmp_path):
    data = form([[1, 1, np.nan], [0, 1, 1]], ["sample", "species"])
    result = execute(tmp_path, "diversity", [data], {"dim": "species", "metrics": "gini"})
    np.testing.assert_allclose(result.data[:, 0], [0, 1 / 3], atol=1e-7)


def test_group_missing_marker_is_not_a_real_group(tmp_path):
    data = form([[1, 3], [3, 5], [100, 200]], ["sample", "species"])
    groups = form([[0], [0], [-9]], ["sample", "feature"], {"missing_code": -9})
    result = execute(tmp_path, "aggregate", [data, groups], {"dim": "sample", "group_col": "feature0", "method": "mean"})
    np.testing.assert_array_equal(result.data, [[2, 4]])


def test_permanova_matches_hand_calculated_f_and_is_seeded(tmp_path):
    points = np.array([0, 1, 4, 5], dtype=np.float32)
    distances = form(np.abs(points[:, None] - points[None, :]), ["sample", "sample_b"])
    distances.labels["sample_b"] = dict(distances.labels["sample"])
    groups = form([[0], [0], [1], [1]], ["sample", "feature"])
    params = {"group_label": "feature0", "n_permutations": 19, "random_state": 12}
    first = execute(tmp_path, "permanova", [distances, groups], params)
    second = execute(tmp_path, "permanova", [distances, groups], params)
    assert first.data[0, 0] == pytest.approx(32)
    assert first.data[0, 1] == pytest.approx(16 / 17)
    assert 1 / 20 <= first.data[0, 2] <= 1
    np.testing.assert_array_equal(first.data, second.data)
