"""Contracts, real transformations and cache round-trips, including false promises."""
from copy import deepcopy

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.core import Form, StepError
from src.core.contracts import port
from src.reader import READERS, read_source
from src.task import Context, STEPS, run
from src.task.operator_catalog import build_catalog
from src.task.step.base import Step
from src.web.api import create_app
from src.web.service import Settings


def annotated():
    return Form(np.array([[0, 1, 2, 1], [2, 1, 0, 1], [0, 0, 1, 2]], dtype=np.float32),
                ["variant", "sample"],
                {"variant": {"v0": 0, "v1": 1, "v2": 2}, "sample": {f"s{i}": i for i in range(4)}},
                {"missing_code": np.nan, "ploidy": 2, "representation": "hard_call",
                 "chrom": ["1", "2", "3"], "pos": np.array([10, 20, 30]), "group": ["a", "b", "a", "b"]},
                {"variant": ["chrom", "pos"], "sample": ["group"]})


def execute(tmp_path, inputs, steps, managed=False):
    cfg = {"runtime": {"memory": {"enabled": True, "budget_mb": 16, "keep": ["out"]}}} if managed else {}
    ctx = Context(tmp_path, cfg)
    for name, form in inputs.items():
        ctx[name] = form
    try:
        run(ctx, steps)
    except BaseException:
        if ctx.memory:
            ctx.memory.close("failed")
        raise
    return ctx


def step(name, inputs=None, **params):
    payload = {"name": name, "inputs": inputs or ["x"], "params": dict(params)}
    if STEPS[name].output_parameter:
        payload["params"].setdefault("output", "out")
    return payload


def test_registry_all_ports_and_readers_json():
    import json
    catalog = build_catalog(STEPS)
    assert catalog["contract_version"] == 1
    assert len(catalog["readers"]) == len(READERS)
    assert all(reader["output_contract"] for reader in catalog["readers"])
    for op in catalog["operators"]:
        assert op["contracts"]["output"]
        arity = op["inputs_arity"]
        if isinstance(arity, int):
            assert len(op["contracts"]["inputs"]) == arity, op["id"]
        else:
            assert op["contracts"]["inputs"], op["id"]
    json.dumps(catalog, allow_nan=False)


@pytest.mark.parametrize("representation,value", [("dosage", 1.25), ("hard_call", .5), ("hard_call", 3), ("hard_call", np.inf)])
def test_hwe_rejects_wrong_semantics_and_lying_info(tmp_path, representation, value):
    form = annotated()
    form.info["representation"] = representation
    form.data[0, 0] = value
    with pytest.raises(StepError, match="contract"):
        execute(tmp_path, {"x": form}, [step("hwe", dim="variant")])


def test_legacy_missing_semantic_tag_is_not_inferred_from_numbers(tmp_path):
    form = annotated()
    del form.info["representation"]
    with pytest.raises(StepError, match="representation"):
        execute(tmp_path, {"x": form}, [step("hwe", dim="variant")])


@pytest.mark.parametrize("managed", [False, True])
def test_subset_rename_transpose_branch_and_spill(tmp_path, managed):
    original = annotated()
    ctx = execute(tmp_path, {"x": original}, [
        step("select", dim="variant", labels=["v2", "v0"], output="selected"),
        step("rename_dim", ["selected"], **{"from": "variant", "to": "locus", "output": "renamed"}),
        step("transpose", ["renamed"], order=["sample", "locus"]),
        step("drop", dim="variant", labels=["v0"], output="branch"),
    ], managed)
    result = ctx["out"]
    assert result.dims == ["sample", "locus"]
    assert result.info["chrom"] == ["3", "1"]
    assert result.axis_info == {"locus": ["chrom", "pos"], "sample": ["group"]}
    assert original.info["chrom"] == ["1", "2", "3"]
    assert ctx["branch"].info["chrom"] == ["2", "3"]
    if managed:
        ctx.forms.spill(ctx.forms.entry("out"), "test")
        restored = ctx["out"]
        np.testing.assert_array_equal(restored.info["pos"], [30, 10])
        assert restored.axis_info == result.axis_info
        ctx.memory.close("complete")


def test_pca_preserves_only_retained_axis_and_replaces_semantics(tmp_path):
    ctx = execute(tmp_path, {"x": annotated()}, [step("pca", dim="variant", n_components=2)])
    result = ctx["out"]
    assert result.info["representation"] == "scores"
    assert result.axis_info == {"sample": ["group"]}
    assert not {"chrom", "pos", "ploidy"} & result.info.keys()
    assert result.info["group"] == ["a", "b", "a", "b"]


def test_concat_reorders_annotations_and_refuses_conflicts(tmp_path):
    a = annotated().subset_axis("variant", [0])
    b = annotated().subset_axis("variant", [1, 2]).subset_axis("sample", [2, 0, 3])
    ctx = execute(tmp_path / "valid", {"a": a, "b": b}, [step("concat", ["a", "b"], axis="variant")])
    result = ctx["out"]
    assert result.labels["sample"] == {"s0": 0, "s2": 1, "s3": 2}
    assert result.info["chrom"] == ["1", "2", "3"]
    assert result.info["group"] == ["a", "a", "b"]
    np.testing.assert_array_equal(result.data, annotated().data[:, [0, 2, 3]])
    b.info["group"][0] = "wrong"
    with pytest.raises(StepError, match="conflicting info.group"):
        execute(tmp_path / "conflict", {"a": a, "b": b}, [step("concat", ["a", "b"], axis="variant")])


def test_regression_fdr_metadata_alignment(tmp_path):
    rng = np.random.default_rng(8)
    data = rng.normal(size=(4, 24)).astype(np.float32)
    form = Form(data, ["variant", "sample"],
                {"variant": {"a": 0, "response": 1, "b": 2, "covar": 3}, "sample": {str(i): i for i in range(24)}},
                {"missing_code": np.nan, "chrom": ["1", "2", "3", "4"], "pos": [10, 20, 30, 40]},
                {"variant": ["chrom", "pos"]})
    ctx = execute(tmp_path, {"x": form}, [step("regress", dim="variant", response="response", covariates=["covar"], output="r"),
                                         step("correction", ["r"], method="fdr")])
    result = ctx["out"]
    assert result.info["chrom"] == ["1", "3"]
    assert result.info["pos"] == [10, 30]
    assert result.axis_info == {"variant": ["chrom", "pos"]}
    assert result.info["representation"] == "regression"
    assert result.info["correction_method"] == "fdr"
    assert "Q_VALUE" in result.labels["statistic"]


def test_attach_uses_label_positions_not_insertion_order(tmp_path):
    target = annotated().subset_axis("variant", [2, 0])
    target.labels["variant"] = {"v0": 1, "v2": 0}
    target.info.pop("chrom")
    target.axis_info["variant"].remove("chrom")
    ctx = execute(tmp_path, {"x": target, "source": annotated()},
                  [step("attach_info", ["x", "source"], fields=["chrom"], target_dim="variant")])
    assert ctx["out"].info["chrom"] == ["3", "1"]
    assert "chrom" not in target.info


def test_runtime_checks_output_before_cache_and_requires_new_write(tmp_path, monkeypatch):
    class Broken(Step):
        name = "broken"
        inputs_arity = 1
        input_contracts = [port()]
        output_contract = {"mode": "preserve"}
        output_parameter = "output"
        def run(self, ctx, inputs):
            value = deepcopy(inputs[0])
            value.info.pop("ploidy")
            ctx["out"] = value
    monkeypatch.setitem(STEPS, "broken", Broken)
    with pytest.raises(StepError, match="output out contract"):
        execute(tmp_path / "bad", {"x": annotated()}, [step("broken")], True)
    Broken.run = lambda self, ctx, inputs: None
    with pytest.raises(StepError, match="did not register"):
        execute(tmp_path / "stale", {"x": annotated(), "out": annotated()}, [step("broken")])


def test_reader_output_checked_even_without_operator(tmp_path, monkeypatch):
    file = tmp_path / "data.csv"
    file.write_text("a,b\n1,2\n3,4\n")
    result = read_source(file, ["sample", "feature"], {"sample": "auto", "feature": "builtin"})
    assert "missing_code" in result.info
    reader = next(r for r in READERS if type(r).__name__ == "CsvReader")
    monkeypatch.setattr(reader, "read", lambda *a, **k: Form(np.ones((1, 1)), ["sample", "feature"], {"sample": {"s": 0}, "feature": {"f": 0}}, {}))
    with pytest.raises(StepError, match="reader CsvReader output contract"):
        read_source(file, ["sample", "feature"], {})


def test_partial_canvas_and_backend_reject_dosage_to_hwe(tmp_path):
    app = create_app(Settings(tmp_path, tmp_path / "studio", tmp_path / "frontend", testing=True))
    with TestClient(app) as client:
        client.headers["X-Studio-Token"] = client.get("/api/bootstrap").json()["token"]
        graph = {"nodes": [{"id": "data", "kind": "source", "position": {"x": 0, "y": 0},
                            "source": {"path": "example.bgen", "dims": ["variant", "sample"]}},
                           {"id": "hwe", "kind": "operator", "operator": "hwe", "position": {"x": 300, "y": 0},
                            "params": {"dim": "variant", "output": "out"}}],
                 "edges": [{"id": "edge", "source": "data", "target": "hwe"}]}
        response = client.post("/api/contracts", json=graph)
        assert response.status_code == 200
        assert response.json()["edges"][0]["status"] == "incompatible"
        assert "hard_call" in str(response.json()["edges"][0]["reasons"])
        assert client.post("/api/export", json=graph).status_code == 422
        graph["nodes"][0]["source"]["path"] = "example.vcf"
        assert client.post("/api/contracts", json=graph).json()["edges"][0]["status"] == "unknown"  # ploidy is file-dependent
        graph["edges"] = []
        assert client.post("/api/contracts", json=graph).status_code == 200


def test_stream_contract_checks_cached_values_without_loading_whole_tensor(tmp_path, monkeypatch):
    from src.task.step.steps.describe import DescribeStep
    class StrictStream(DescribeStep):
        name = "strict_stream"
        parameters_schema = {
            "type": "object",
            "properties": {"dim": {"type": "string"}},
            "additionalProperties": False,
        }
        input_contracts = STEPS["hwe"].input_contracts
    monkeypatch.setitem(STEPS, "strict_stream", StrictStream)
    ctx = Context(tmp_path, {"runtime": {"memory": {"budget_mb": 8}}})
    value = annotated()
    value.data[-1, -1] = .5
    ctx["x"] = value
    ctx.forms.spill(ctx.forms.entry("x"), "test")
    monkeypatch.setattr(ctx.forms, "_load", lambda entry: pytest.fail("stream validator loaded a full tensor"))
    with pytest.raises(StepError, match="invalid hard_call"):
        run(ctx, [step("strict_stream", dim="variant")])
    assert ctx.forms.entry("x").form is None
    ctx.memory.close("failed")


def test_encoder_maps_follow_select_and_rename(tmp_path):
    file = tmp_path / "encoded.csv"
    file.write_text("color,value\nred,1\nblue,2\nred,3\n")
    form = read_source(file, ["sample", "feature"], {"sample": "auto", "feature": "builtin"})
    ctx = execute(tmp_path / "rename", {"x": form}, [step("rename_dim", **{"from": "feature", "to": "variable"})])
    assert "color" in ctx["out"].info["encoders"]["variable"]
    assert "feature" in form.info["encoders"]
    ctx = execute(tmp_path / "select", {"x": form}, [step("select", dim="feature", labels=["value"])])
    assert "encoders" not in ctx["out"].info


def test_three_dimensional_concat_and_key_alignment(tmp_path):
    a = Form(np.arange(24).reshape(2, 3, 4), ["x", "y", "z"],
             {"x": {"a": 0, "b": 1}, "y": {str(i): i for i in range(3)}, "z": {str(i): i for i in range(4)}},
             {"missing_code": np.nan, "row": [1, 2]}, {"x": ["row"]})
    b = a.subset_axis("x", [1]).subset_axis("z", [3, 1])
    b.labels["y"] = {f"other{i}": i for i in range(3)}
    ctx = execute(tmp_path / "nd", {"a": a, "b": b}, [step("concat", ["a", "b"], axis="y")])
    assert ctx["out"].data.shape == (1, 6, 2)
    assert ctx["out"].info["row"] == [2]
    a = Form(np.array([[10, 1], [20, 2], [30, 3]], dtype=np.float32), ["row", "field"],
             {"row": {"r1": 0, "r2": 1, "r3": 2}, "field": {"id": 0, "a": 1}},
             {"missing_code": np.nan, "group": ["a", "b", "c"], "units": ["id", "a-unit"]},
             {"row": ["group"], "field": ["units"]})
    b = Form(np.array([[30, 9], [10, 8]], dtype=np.float32), ["row", "field"],
             {"row": {"other3": 0, "other1": 1}, "field": {"key": 0, "b": 1}},
             {"missing_code": np.nan, "group": ["c", "a"], "units": ["id", "b-unit"]},
             {"row": ["group"], "field": ["units"]})
    ctx = execute(tmp_path / "key", {"a": a, "b": b}, [step("concat", ["a", "b"], axis="field", align={"dim": "row", "key": {"a": "id", "b": "key"}}, label="ID")])
    result = ctx["out"]
    assert result.info["group"] == ["a", "c"]
    assert result.info["units"] == ["id", "a-unit", "b-unit"]
    assert result.labels["row"] == {"r1": 0, "r3": 1}
    np.testing.assert_array_equal(result.data, [[10, 1, 8], [30, 3, 9]])


def test_fdr_rejects_out_of_range_probability_and_extends_axis_annotation(tmp_path):
    form = Form(np.array([[.2], [.7]], dtype=np.float32), ["feature", "statistic"],
                {"feature": {"a": 0, "b": 1}, "statistic": {"P": 0}},
                {"column_note": ["raw"]}, {"statistic": ["column_note"]})
    ctx = execute(tmp_path / "good", {"x": form}, [step("correction")])
    assert ctx["out"].info["column_note"] == ["raw", None, None]
    form.data[0, 0] = 1.2
    with pytest.raises(StepError, match="invalid pvalue"):
        execute(tmp_path / "bad", {"x": form}, [step("correction")])
