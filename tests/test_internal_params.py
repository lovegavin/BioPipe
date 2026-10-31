"""Regression: the engine-only _input_names key cannot reach validation."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task import Context, run
from src.task.operator_catalog import build_catalog
from src.task import STEPS
from src.web.graph import compile_graph, import_manifest
from src.web.models import Graph, GraphNode, GraphEdge, Position, Source


def _form(name):
    return Form(
        data=np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32),
        dims=["sample", "feature"],
        labels={"sample": {f"{name}{i}": i for i in range(2)},
                "feature": {"f0": 0, "f1": 1}},
        info={"missing_code": np.nan},
    )


def test_runner_ignores_persisted_input_names(tmp_path):
    ctx = Context(tmp_path, {})
    ctx["a"] = _form("a")
    ctx["b"] = _form("b")
    run(ctx, [{
        "name": "concat",
        "inputs": ["a", "b"],
        "params": {"axis": "sample", "output": "c", "_input_names": ["a", "b"]},
    }])
    assert list(ctx["c"].labels["sample"]) == ["a0", "a1", "b0", "b1"]


def test_import_manifest_drops_input_names(tmp_path):
    text = """
name: demo
sources:
  x:
    path: input.csv
    dims: [sample, feature]
    labels: {sample: auto, feature: builtin}
steps:
  - name: normalize
    inputs: [x]
    params:
      method: cpm
      dim: sample
      output: y
      _input_names: [x]
"""
    graph = import_manifest(text, str(tmp_path), build_catalog(STEPS), str(tmp_path))
    operator = next(node for node in graph.nodes if node.kind == "operator")
    assert "_input_names" not in operator.params


def test_compile_graph_drops_input_names_before_validation(tmp_path):
    import pandas as pd

    for name in ("a", "b"):
        pd.DataFrame({"f0": [1, 2], "f1": [3, 4]}).to_csv(tmp_path / f"{name}.csv", index=False)
    graph = Graph(
        name="demo",
        nodes=[
            GraphNode(id="a", kind="source", title="a", position=Position(x=0, y=0),
                      source=Source(path=str(tmp_path / "a.csv"), dims=["sample", "feature"],
                                    labels={"sample": "auto", "feature": "builtin"})),
            GraphNode(id="b", kind="source", title="b", position=Position(x=0, y=100),
                      source=Source(path=str(tmp_path / "b.csv"), dims=["sample", "feature"],
                                    labels={"sample": "auto", "feature": "builtin"})),
            GraphNode(id="c", kind="operator", operator="concat", title="concat",
                      position=Position(x=300, y=50), input_count=2,
                      params={"axis": "feature", "output": "c", "_input_names": ["a", "b"]}),
        ],
        edges=[
            GraphEdge(id="e1", source="a", target="c", targetHandle="in-0"),
            GraphEdge(id="e2", source="b", target="c", targetHandle="in-1"),
        ],
        memory={"enabled": False},
    )
    manifest, _ = compile_graph(graph, build_catalog(STEPS), tmp_path)
    assert "_input_names" not in manifest["steps"][0]["params"]
