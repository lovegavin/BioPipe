"""Contract tests for restriction digest operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps._restriction_utils import (
    cut_positions, digest, parse_enzymes,
)
from src.task.step.steps.restriction_digest import RestrictionDigestStep
from src.task.step.steps.restriction_fragment_stats import RestrictionFragmentStatsStep


class Ctx:
    def __init__(self, **params):
        self.step_params = params
        self.outputs = {}

    def __setitem__(self, key, value):
        self.outputs[key] = value

    def __getitem__(self, key):
        return self.outputs[key]


def run(step, params, inputs):
    step.name = step.definition["id"]
    ctx = Ctx(**params)
    step.run(ctx, inputs)
    return ctx, ctx.outputs[params.get("output", "out")]


def fasta_form(sequences, names=None):
    names = names or [f"seq{index}" for index in range(len(sequences))]
    length = max(len(sequence) for sequence in sequences)
    data = np.zeros((len(sequences), length), dtype=np.float64)
    return Form(
        data,
        dims=["sequence", "position"],
        labels={
            "sequence": {name: index for index, name in enumerate(names)},
            "position": {str(index): index for index in range(length)},
        },
        info={"sequences": sequences},
    )


def test_cut_positions_linear():
    sequence = "GAATTCAAAAGGATCC"
    assert cut_positions(sequence, ["EcoRI"]) == [1]
    assert cut_positions(sequence, ["EcoRI", "BamHI"]) == [1, 11]


def test_digest_linear_fragments():
    cuts, fragments = digest("A" * 20, ["EcoRI"], False)
    assert cuts == [] and fragments == [(0, 20)]
    cuts, fragments = digest("GAATTCAAAAGGATCC", ["EcoRI", "BamHI"], False)
    assert cuts == [1, 11]
    assert fragments == [(0, 1), (1, 10), (11, 5)]


def test_circular_site_spanning_origin_is_found():
    from library.seed.src.task.step.steps._restriction_utils import digest

    sequence = "AATTC" + "GGATCC" + "A" * 26 + "G"  # EcoRI GAATTC spans the origin
    cuts, fragments = digest(sequence, ["EcoRI", "BamHI"], True)
    assert sorted(cuts) == [0, 6]
    assert sorted(length for _, length in fragments) == [6, 32]


def test_digest_circular_wraps():
    cuts, fragments = digest("GAATTCAAAAGAATTC", ["EcoRI"], True)
    assert cuts == [1, 11]
    assert fragments == [(1, 10), (11, 6)]


def test_parse_enzymes_rejects_unknown():
    with pytest.raises(StepError, match="unsupported enzyme"):
        parse_enzymes("EcoRI,NotAnEnzyme")


def test_operator_linear_digest():
    step = RestrictionDigestStep()
    ctx, out = run(step, {"enzymes": "EcoRI,BamHI", "output": "fragments"},
                   [fasta_form(["GAATTCAAAAGGATCC"])])
    assert out.data.shape[0] == 3
    lengths = out.data[:, out.labels["field"]["length"]]
    assert list(lengths) == [1.0, 10.0, 5.0]
    assert out.info["total_cuts"] == 2


def test_operator_circular_digest():
    step = RestrictionDigestStep()
    ctx, out = run(step, {"enzymes": "EcoRI", "circular": True, "output": "fragments"},
                   [fasta_form(["GAATTCAAAAGAATTC"])])
    starts = out.data[:, out.labels["field"]["start"]]
    ends = out.data[:, out.labels["field"]["end"]]
    assert list(starts) == [1.0, 11.0]
    assert list(ends) == [11.0, 17.0]


def test_fragment_stats():
    data = np.asarray([[10.0], [20.0], [30.0]], dtype=np.float64)
    form = Form(data, dims=["fragment", "field"],
                labels={"fragment": {"a": 0, "b": 1, "c": 2}, "field": {"length": 0}})
    step = RestrictionFragmentStatsStep()
    ctx, out = run(step, {"length_field": "length", "output": "stats"}, [form])
    values = {name: float(out.data[index, 0]) for name, index in out.labels["statistic"].items()}
    assert values["n_fragments"] == 3.0
    assert values["total_length"] == 60.0
    assert values["median_length"] == 20.0


def test_fragment_stats_rejects_missing_column():
    data = np.asarray([[10.0]], dtype=np.float64)
    form = Form(data, dims=["fragment", "field"],
                labels={"fragment": {"a": 0}, "field": {"value": 0}})
    step = RestrictionFragmentStatsStep()
    with pytest.raises(StepError, match="column 'length' is missing"):
        run(step, {"length_field": "length"}, [form])
