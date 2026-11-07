"""Tests for assembly NGx operators."""

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.assembly_length_bins import AssemblyLengthBinsStep
from src.task.step.steps.assembly_ngx_curve import AssemblyNgxCurveStep
from src.task.step.steps.assembly_ngx_metrics import AssemblyNgxMetricsStep


class Ctx:
    def __init__(self, **params):
        self.step_params = params
        self.outputs = {}

    def __setitem__(self, key, value):
        self.outputs[key] = value

    def __getitem__(self, key):
        return self.outputs[key]


def assembly(sequences):
    width = max((len(item) for item in sequences), default=0)
    data = np.zeros((len(sequences), width), dtype=np.int8)
    labels = {f"contig{index}": index for index in range(len(sequences))}
    return Form(
        data,
        dims=["sequence", "position"],
        labels={"sequence": labels, "position": {str(index): index for index in range(width)}},
        info={"sequences": list(sequences)},
    )


def test_ngx_hand_values():
    lengths = np.asarray([10, 5, 3, 2], dtype=np.int64)
    ctx = Ctx(genome_size=20, x_values="50,90", output="metrics")
    AssemblyNgxMetricsStep().run(ctx, [assembly(["A" * 10, "A" * 5, "A" * 3, "A" * 2])])
    form = ctx["metrics"]
    values = {name: float(form.data[index, 0]) for name, index in form.labels["statistic"].items()}
    assert values["total_length"] == 20
    assert values["n_contigs"] == 4
    assert values["n50"] == 10 and values["l50"] == 1
    assert values["auN"] == pytest.approx(6.9)
    assert values["NG50"] == 10 and values["NA50"] == 10
    assert form.data.shape == (11, 1)


def test_ngx_curve_points():
    ctx = Ctx(genome_size=20, step=50, output="curve")
    AssemblyNgxCurveStep().run(ctx, [assembly(["A" * 10, "A" * 5, "A" * 3, "A" * 2])])
    form = ctx["curve"]
    assert form.data.shape == (2, 4)
    assert list(form.data[0]) == [10.0, 1.0, 0.5, 0.5]
    assert form.data[1, 0] == pytest.approx(2.0)
    assert form.data[1, 1] == pytest.approx(4.0)
    assert form.data[1, 3] == pytest.approx(1.0)


def test_length_bins():
    ctx = Ctx(edges="0,5,0", output="bins")
    AssemblyLengthBinsStep().run(ctx, [assembly(["A" * 10, "A" * 5, "A" * 3, "A" * 2])])
    form = ctx["bins"]
    assert form.data.shape == (2, 3)
    assert list(form.data[0]) == [2.0, 5.0, 3.0]
    assert list(form.data[1]) == [2.0, 15.0, 10.0]


def test_invalid_x_values():
    ctx = Ctx(x_values="50,abc")
    with pytest.raises(StepError, match="invalid x value"):
        AssemblyNgxMetricsStep().run(ctx, [assembly(["ACGT"])])


def test_invalid_bin_edges():
    ctx = Ctx(edges="7", output="bins")
    with pytest.raises(StepError, match="at least two edges"):
        AssemblyLengthBinsStep().run(ctx, [assembly(["ACGT"])])


def test_empty_assembly_rejected():
    with pytest.raises(StepError, match="empty"):
        AssemblyNgxMetricsStep().run(Ctx(), [assembly([])])
