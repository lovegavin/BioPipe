"""Tests for the PAE matrix summary operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.structure_pae_summary import StructurePaeSummaryStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = dict(params or {})
        self.metadata = {}


def _pae(matrix, labels=("A:1", "A:2")) -> Form:
    matrix = np.asarray(matrix, dtype=np.float32)
    return Form(
        data=matrix,
        dims=["residue", "residue_b"],
        labels={
            "residue": {label: index for index, label in enumerate(labels)},
            "residue_b": {label: index for index, label in enumerate(labels)},
        },
        info={"missing_code": np.nan},
    )


def test_rows_are_means_maxima_and_threshold_fractions() -> None:
    ctx = Ctx({"threshold": 10.0, "output": "pae"})
    StructurePaeSummaryStep().run(ctx, [_pae([[5.0, 15.0], [20.0, 30.0]])])
    out = ctx["pae"]
    assert out.dims == ["residue", "statistic"]
    labels = [label for label, _ in sorted(out.labels["residue"].items(), key=lambda item: item[1])]
    assert labels == ["A:1", "A:2"]
    np.testing.assert_allclose(out.data, [[10.0, 15.0, 0.5], [25.0, 30.0, 0.0]], rtol=1e-6, atol=1e-6)
    assert out.info["mean_pae"] == pytest.approx(17.5)
    assert out.info["median_pae"] == pytest.approx(17.5)
    assert out.info["max_pae"] == 30.0
    assert out.info["threshold"] == 10.0
    assert out.info["n_residues"] == 2


def test_threshold_changes_the_fraction() -> None:
    ctx = Ctx({"threshold": 16.0, "output": "pae"})
    StructurePaeSummaryStep().run(ctx, [_pae([[5.0, 15.0], [20.0, 30.0]])])
    np.testing.assert_allclose(ctx["pae"].data[:, 2], [1.0, 0.0], atol=1e-6)


def test_default_labels_are_generated_when_missing() -> None:
    form = Form(
        data=np.zeros((2, 2), dtype=np.float32),
        dims=["residue", "residue_b"],
        labels={"residue": {}, "residue_b": {}},
        info={"missing_code": np.nan},
    )
    ctx = Ctx()
    StructurePaeSummaryStep().run(ctx, [form])
    labels = [label for label, _ in sorted(ctx["pae"].labels["residue"].items(), key=lambda item: item[1])]
    assert labels == ["residue1", "residue2"]


def test_validation_errors() -> None:
    step = StructurePaeSummaryStep()
    assert step.definition["inputs_arity"] == 1
    ctx = Ctx()
    with pytest.raises(StepError, match="threshold"):
        StructurePaeSummaryStep().run(Ctx({"threshold": 0.0}), [_pae([[1.0, 2.0], [3.0, 4.0]])])

    with pytest.raises(StepError, match="square"):
        StructurePaeSummaryStep().run(Ctx(), [_pae([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])])

    negative = _pae([[1.0, 2.0], [3.0, 4.0]])
    negative.data[0, 0] = -1.0
    with pytest.raises(StepError, match="negative"):
        StructurePaeSummaryStep().run(Ctx(), [negative])

    with pytest.raises(StepError, match="expected a PAE matrix with dims"):
        StructurePaeSummaryStep().run(
            Ctx({"row_dim": "row"}),
            [_pae([[1.0, 2.0], [3.0, 4.0]])],
        )

    empty = Form(
        data=np.zeros((0, 0), dtype=np.float32),
        dims=["residue", "residue_b"],
        labels={"residue": {}, "residue_b": {}},
        info={"missing_code": np.nan},
    )
    with pytest.raises(StepError, match="empty"):
        StructurePaeSummaryStep().run(Ctx(), [empty])


def test_runner_round_trip(tmp_path) -> None:
    ctx = Context(str(tmp_path / "pae"), {"params": {}})
    ctx["matrix"] = _pae([[3.0, 4.0], [12.0, 13.0]])
    run(
        ctx,
        [
            {
                "name": "structure_pae_summary",
                "inputs": ["matrix"],
                "params": {"threshold": 10.0, "output": "summary"},
            }
        ],
    )
    form = ctx["summary"]
    assert form.dims == ["residue", "statistic"]
    assert form.data.shape == (2, 3)
    assert list((tmp_path / "pae").rglob("*structure_pae_summary*.json"))
