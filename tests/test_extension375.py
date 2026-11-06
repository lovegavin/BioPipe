import json
import math
from pathlib import Path

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps._sc_utils import (
    bh_adjust,
    log2_fold_change,
    normal_two_sided_p,
    wilcoxon_rank_sum,
)
from src.task.step.steps.sc_cluster_profile import ScClusterProfileStep
from src.task.step.steps.sc_marker_specificity import ScMarkerSpecificityStep
from src.task.step.steps.sc_rank_genes import ScRankGenesStep

PARAMS = Path(__file__).resolve().parents[1] / "library/seed/src/task/step/steps"


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}


def _expression(values, genes, cells):
    data = np.asarray(values, dtype=float)
    return Form(
        data=data,
        dims=["cell", "gene"],
        labels={
            "cell": {name: index for index, name in enumerate(cells)},
            "gene": {name: index for index, name in enumerate(genes)},
        },
    )


def _clusters(values, cells):
    names = {}
    codes = []
    for value in values:
        if value not in names:
            names[value] = len(names)
        codes.append(names[value])
    return Form(
        data=np.asarray(codes, dtype=float).reshape(-1, 1),
        dims=["cell", "cluster"],
        labels={"cell": {name: index for index, name in enumerate(cells)}},
    )


def test_parameters_declare_every_read():
    for name, expected in (
        ("sc_rank_genes", {"cell_dim", "gene_dim", "cluster_dim", "min_cells", "top_n", "output"}),
        ("sc_marker_specificity", {"cell_dim", "gene_dim", "cluster_dim", "min_cells", "output"}),
        ("sc_cluster_profile", {"cell_dim", "gene_dim", "cluster_dim", "min_cells", "output"}),
    ):
        schema = json.loads((PARAMS / f"{name}.parameters.json").read_text())
        assert schema["additionalProperties"] is False
        assert set(schema["properties"]) == expected


def test_wilcoxon_two_sided_p_matches_normal_approximation():
    u_value, z_value, p_value = wilcoxon_rank_sum(np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0, 6.0]))
    assert u_value == 0.0
    expected_z = (0.0 - 4.5) / math.sqrt(5.25)
    assert z_value == pytest.approx(expected_z, abs=1e-12)
    assert p_value == pytest.approx(math.erfc(abs(expected_z) / math.sqrt(2.0)), rel=1e-12)


def test_wilcoxon_fully_tied_returns_neutral_p():
    _, _, p_value = wilcoxon_rank_sum(np.ones(3), np.ones(3))
    assert p_value == 1.0


def test_bh_adjust_known_values():
    adjusted = bh_adjust(np.array([0.01, 0.04, 0.03, 0.002]))
    assert adjusted.tolist() == pytest.approx([0.02, 0.04, 0.04, 0.008], abs=1e-12)


def test_rank_genes_orders_cluster_specific_gene_first():
    cells = [f"c{i}" for i in range(8)]
    genes = ["g0", "g1", "g2", "g3"]
    expression = _expression(
        [
            [8, 0, 2, 0],
            [7, 0, 2, 0],
            [6, 0, 2, 0],
            [9, 0, 2, 0],
            [0, 8, 2, 0],
            [0, 7, 2, 0],
            [0, 6, 2, 0],
            [0, 9, 2, 0],
        ],
        genes,
        cells,
    )
    clusters = _clusters(["A"] * 4 + ["B"] * 4, cells)
    step = ScRankGenesStep()
    ctx = Ctx({"top_n": 2})
    step.run(ctx, [expression, clusters])
    out = ctx["out"]
    assert out.dims == ["test", "statistic"]
    assert out.data.shape[0] == 4
    rows = {name: int(position) for name, position in out.labels["test"].items()}
    assert "0|g0" in rows and "1|g1" in rows
    index = rows["0|g0"]
    assert out.data[index, 7] == 1.0
    assert out.data[index, 0] > 0.0
    assert out.data[index, 5] < 0.05


def test_rank_genes_rejects_wrong_dims():
    cells = ["c0", "c1", "c2", "c3"]
    expression = Form(
        data=np.ones((4, 2)),
        dims=["sample", "gene"],
        labels={"sample": {c: i for i, c in enumerate(cells)}, "gene": {"g0": 0, "g1": 1}},
    )
    clusters = _clusters(["A", "A", "B", "B"], cells)
    with pytest.raises(StepError, match="expected dims"):
        ScRankGenesStep().run(Ctx({}), [expression, clusters])


def test_marker_specificity_tau_and_top_cluster():
    cells = [f"c{i}" for i in range(6)]
    genes = ["g0", "g1", "g2"]
    expression = _expression(
        [[6, 0, 4], [6, 0, 4], [6, 0, 4], [0, 6, 4], [0, 6, 4], [0, 6, 4]],
        genes,
        cells,
    )
    clusters = _clusters(["A", "A", "A", "B", "B", "B"], cells)
    step = ScMarkerSpecificityStep()
    ctx = Ctx({})
    step.run(ctx, [expression, clusters])
    out = ctx["out"]
    rows = {name: int(position) for name, position in out.labels["gene"].items()}
    assert out.data[rows["g0"], 0] == 0.0
    assert out.data[rows["g0"], 1] == pytest.approx(1.0)
    assert out.data[rows["g2"], 1] == pytest.approx(0.0)
    assert out.data[rows["g2"], 0] in (0.0, 1.0)


def test_marker_specificity_zero_gene_has_zero_tau():
    cells = [f"c{i}" for i in range(4)]
    genes = ["g0", "g1", "g2"]
    expression = _expression([[4, 0, 0], [4, 0, 0], [0, 4, 0], [0, 4, 0]], genes, cells)
    clusters = _clusters(["A", "A", "B", "B"], cells)
    step = ScMarkerSpecificityStep()
    ctx = Ctx({"min_cells": 1})
    step.run(ctx, [expression, clusters])
    out = ctx["out"]
    rows = {name: int(position) for name, position in out.labels["gene"].items()}
    assert out.data[rows["g2"], 1] == 0.0


def test_cluster_profile_means_and_detection():
    cells = [f"c{i}" for i in range(6)]
    genes = ["g0", "g1"]
    expression = _expression([[2, 0], [4, 0], [6, 0], [0, 5], [0, 5], [0, 5]], genes, cells)
    clusters = _clusters(["A", "A", "A", "B", "B", "B"], cells)
    step = ScClusterProfileStep()
    ctx = Ctx({})
    step.run(ctx, [expression, clusters])
    out = ctx["out"]
    assert out.data.shape == (4, 3)
    rows = {name: int(position) for name, position in out.labels["cluster_gene"].items()}
    assert out.data[rows["0|g0"], 0] == pytest.approx(4.0)
    assert out.data[rows["0|g0"], 1] == pytest.approx(1.0)
    assert out.data[rows["1|g0"], 1] == pytest.approx(0.0)


def test_single_cluster_rejected():
    cells = ["c0", "c1", "c2", "c3"]
    expression = _expression([[1], [2], [3], [4]], ["g0"], cells)
    clusters = _clusters(["A", "A", "A", "A"], cells)
    with pytest.raises(StepError, match="at least two clusters"):
        ScRankGenesStep().run(Ctx({}), [expression, clusters])


def test_log2_fold_change_pseudocount():
    assert log2_fold_change(np.array([0.0, 0.0]), np.array([0.0, 0.0])) == 0.0
    assert log2_fold_change(np.array([2.0]), np.array([1.0])) == pytest.approx(1.0, abs=1e-6)
