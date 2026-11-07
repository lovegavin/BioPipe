import numpy as np
import pytest

from src.core import Form
from src.core.encoding import LabelEncoder
from src.core.errors import StepError
from src.task.step.steps.network_communities import NetworkCommunitiesStep
from src.task.step.steps.network_centrality import NetworkCentralityStep
from src.task.step.steps.network_summary import NetworkSummaryStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def edge_form(edges, weight=False):
    encoder_a = LabelEncoder()
    encoder_b = LabelEncoder()
    codes_a = encoder_a.fit_transform([edge[0] for edge in edges])
    codes_b = encoder_b.fit_transform([edge[1] for edge in edges])
    columns = [codes_a, codes_b]
    fields = ["node_a", "node_b"]
    if weight:
        columns.append(np.asarray([edge[2] for edge in edges], dtype=float))
        fields.append("score")
    data = np.column_stack(columns)
    return Form(
        data,
        dims=["edge", "field"],
        labels={"edge": {str(index): index for index in range(len(edges))},
                "field": {name: index for index, name in enumerate(fields)}},
        info={"encoders": {"field": {"node_a": encoder_a, "node_b": encoder_b}}},
    )


def run(step, form, params):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return ctx


def test_summary_toy_graph():
    form = edge_form([("a", "b"), ("b", "c"), ("a", "c"), ("c", "d")])
    ctx = run(NetworkSummaryStep(), form, {"output": "summary"})
    summary = ctx["summary"]
    values = {name: float(summary.data[position, 0])
              for name, position in summary.labels["statistic"].items()}
    assert values["n_nodes"] == 4
    assert values["n_edges"] == 4
    assert values["density"] == pytest.approx(2.0 / 3.0)
    assert values["n_components"] == 1
    assert values["diameter"] == 2
    assert values["clustering_coefficient"] == pytest.approx((1 + 1 + 1 / 3 + 0) / 4)


def test_centrality_degree_and_shapes():
    form = edge_form([("a", "b"), ("b", "c"), ("a", "c"), ("c", "d")])
    ctx = run(NetworkCentralityStep(), form, {"output": "centrality"})
    table = ctx["centrality"]
    metrics = list(table.labels["statistic"])
    assert table.data.shape == (4, 5)
    degree_column = metrics.index("degree")
    degree = {name: table.data[position, degree_column]
              for name, position in table.labels["node"].items()}
    assert degree["d"] == pytest.approx(1 / 3)
    assert degree["a"] == pytest.approx(2 / 3)
    betweenness = {name: table.data[position, metrics.index("betweenness")]
                   for name, position in table.labels["node"].items()}
    assert betweenness["c"] == pytest.approx(2 / 3)
    assert betweenness["d"] == pytest.approx(0.0)


def test_communities_cover_all_nodes():
    form = edge_form([("a", "b"), ("b", "c"), ("a", "c"), ("c", "d")])
    ctx = run(NetworkCommunitiesStep(), form, {"output": "communities"})
    table = ctx["communities"]
    assert table.data.shape == (4, 1)
    assert table.info["n_communities"] >= 1
    assert 0.0 <= table.info["modularity"] <= 1.0


def test_missing_node_column_raises():
    form = edge_form([("a", "b")])
    step = NetworkSummaryStep()
    with pytest.raises(StepError, match="missing node columns"):
        step.run(Ctx({"output": "summary", "node_a_field": "source"}), [form])


def test_self_loops_and_weights_are_handled():
    form = edge_form([("a", "a", 1.0), ("a", "b", 0.5), ("b", "c", 0.5), ("a", "c", 0.5)], weight=True)
    ctx = run(NetworkSummaryStep(), form, {"output": "summary", "weight_field": "score"})
    values = {name: float(ctx["summary"].data[position, 0])
              for name, position in ctx["summary"].labels["statistic"].items()}
    assert values["n_edges"] == 3
    assert values["n_nodes"] == 3
