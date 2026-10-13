"""The upstream building blocks pass through the actual SDK runner/contracts."""
import numpy as np
import pytest

from src.core import Form
from src.task import Context, STEPS, run
from src.core.contracts import infer_output, describe_form, validate_output


def inputs():
    values = np.array([[1, 2, 3], [2, 4, 1], [3, 1, 5], [7, 4, 2], [5, 5, 6], [8, 2, 4]], dtype=np.float32)
    data = Form(values, ["sample", "feature"], {
        "sample": {f"s{i}": i for i in range(6)}, "feature": {f"f{i}": i for i in range(3)}},
        {"missing_code": np.nan, "batch": list(range(6)), "symbol": ["a", "b", "c"]},
        {"sample": ["batch"], "feature": ["symbol"]})
    meta = Form(np.array([[0], [0], [1], [1], [2], [2]], dtype=np.float32), ["sample", "field"],
                {"sample": dict(data.labels["sample"]), "field": {"group": 0}}, {"missing_code": np.nan})
    return data, meta


@pytest.mark.parametrize("name,params", [
    ("bin", {"dim": "sample", "bins": 2}),
    ("cluster_axis", {"dim": "sample", "method": "hierarchical", "n_clusters": 2}),
    ("rank_axis", {"dim": "feature", "by": "variance", "top_n": 2}),
    ("reduce_axis", {"dim": "feature", "stats": ["sum", "count"]}),
])
def test_axis_output_through_runner(tmp_path, name, params):
    data, _ = inputs()
    ctx = Context(tmp_path, {})
    ctx["input"] = data
    run(ctx, [{"name": name, "inputs": ["input"], "params": {**params, "output": "result"}}])
    result = ctx["result"]
    expected = infer_output(STEPS[name].output_contract, [describe_form(data)], params)
    validate_output(result, expected, name)
    assert result.axis_info["sample"] == ["batch"]
    assert result.info["batch"] == list(range(6))
    if name != "rank_axis":
        assert "symbol" not in result.info


def test_metric_filter_pipeline_keeps_axis_annotations(tmp_path):
    data, _ = inputs()
    ctx = Context(tmp_path, {})
    ctx["input"] = data
    run(ctx, [
        {"name": "reduce_axis", "inputs": ["input"], "params": {"dim": "feature", "stats": ["sum"], "output": "metrics"}},
        {"name": "filter_by", "inputs": ["input", "metrics"], "params": {"dim": "sample", "rules": [{"field": "sum", "min": 10}], "output": "filtered"}},
    ])
    assert list(ctx["filtered"].labels["sample"]) == ["s3", "s4", "s5"]
    assert ctx["filtered"].info["batch"] == [3, 4, 5]


@pytest.mark.parametrize("name,params", [
    ("dotplot", {"feature_dim": "feature", "group_dim": "sample", "group_label": "group", "features": ["f0", "f1"]}),
    ("violin", {"dim": "feature", "group_dim": "sample", "group_label": "group", "value_label": "f0"}),
])
def test_plot_contracts_and_exports(tmp_path, name, params):
    data, meta = inputs()
    ctx = Context(tmp_path, {})
    ctx["input"], ctx["meta"] = data, meta
    run(ctx, [{"name": name, "inputs": ["input", "meta"], "params": {**params, "filename": f"{name}.png"}}])
    assert list(tmp_path.rglob(f"{name}.png"))


@pytest.mark.parametrize("mode", ["one_vs_rest", "pairwise"])
def test_multigroup_contract_retains_feature_metadata(tmp_path, mode):
    data, meta = inputs()
    params = {"dim": "feature", "group_dim": "sample", "group_label": "group", "mode": mode, "method": "welch"}
    ctx = Context(tmp_path, {})
    ctx["input"], ctx["meta"] = data, meta
    run(ctx, [{"name": "compare_groups", "inputs": ["input", "meta"], "params": params}])
    result = ctx["compare_groups"]
    assert result.dims == ["feature", "comparison", "statistic"]
    assert result.data.shape == (3, 3, 6)
    assert result.info["symbol"] == ["a", "b", "c"] and "batch" not in result.info
