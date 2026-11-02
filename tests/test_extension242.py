"""Tests for the per-residue pLDDT profile operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.structure_plddt_profile import StructurePlddtProfileStep

COLUMNS = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element", "bfactor")
LABELS = ("resname", "chain", "atom_name", "element")


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = dict(params or {})
        self.metadata = {}


def _form(rows, columns=COLUMNS) -> Form:
    table = {name: [row[index] for row in rows] for index, name in enumerate(columns)}
    encoders = {}
    parts = []
    for name in columns:
        if name in LABELS:
            encoder = LabelEncoder()
            parts.append(encoder.fit_transform(table[name]))
            encoders[name] = encoder
        else:
            parts.append(np.asarray(table[name], dtype=np.float64))
    matrix = np.column_stack(parts).astype(np.float32)
    return Form(
        data=matrix,
        dims=["atom", "field"],
        labels={
            "atom": {f"atom:{index}": index for index in range(len(rows))},
            "field": {name: index for index, name in enumerate(columns)},
        },
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


def test_profile_aggregates_per_residue() -> None:
    rows = [
        (0.0, 0.0, 0.0, 1, "ALA", "A", "N", "N", 80.0),
        (1.0, 0.0, 0.0, 1, "ALA", "A", "CA", "C", 60.0),
        (2.0, 0.0, 0.0, 2, "GLY", "A", "CA", "C", 95.0),
        (3.0, 0.0, 0.0, 3, "SER", "B", "CA", "C", np.nan),
    ]
    ctx = Ctx({"output": "plddt"})
    StructurePlddtProfileStep().run(ctx, [_form(rows)])
    out = ctx["plddt"]
    assert out.dims == ["residue", "statistic"]
    labels = [label for label, _ in sorted(out.labels["residue"].items(), key=lambda item: item[1])]
    assert labels == ["A:ALA:1", "A:GLY:2"]
    by_label = {labels[index]: out.data[index].tolist() for index in range(len(labels))}
    assert by_label["A:ALA:1"] == [70.0, 60.0, 80.0, 2.0]
    assert by_label["A:GLY:2"] == [95.0, 95.0, 95.0, 1.0]
    assert out.info["mean_plddt"] == pytest.approx((80.0 + 60.0 + 95.0) / 3.0)
    assert out.info["median_plddt"] == 80.0
    assert out.info["n_residues"] == 2
    assert out.info["n_atoms"] == 3
    assert out.info["scale"] == "hundred"


def test_fraction_scale_is_reported() -> None:
    rows = [
        (0.0, 0.0, 0.0, 1, "ALA", "A", "CA", "C", 0.9),
        (1.0, 0.0, 0.0, 2, "GLY", "A", "CA", "C", 0.8),
    ]
    ctx = Ctx()
    StructurePlddtProfileStep().run(ctx, [_form(rows)])
    out = ctx["plddt"]
    assert out.info["scale"] == "fraction"
    assert out.info["mean_plddt"] == pytest.approx(0.85, rel=1e-6)


def test_missing_bfactor_and_empty_form() -> None:
    step = StructurePlddtProfileStep()
    assert step.definition["inputs_arity"] == 1
    ctx = Ctx()
    no_bfactor = _form(
        [(0.0, 0.0, 0.0, 1, "ALA", "A", "CA", "C")],
        columns=("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element"),
    )
    with pytest.raises(StepError, match="no 'bfactor' column"):
        step.run(ctx, [no_bfactor])
    empty = Form(
        data=np.zeros((0, 9), dtype=np.float32),
        dims=["atom", "field"],
        labels={"atom": {}, "field": {name: index for index, name in enumerate(COLUMNS)}},
        info={"missing_code": np.nan},
    )
    with pytest.raises(StepError, match="empty"):
        step.run(ctx, [empty])


def test_runner_round_trip(tmp_path) -> None:
    rows = [
        (0.0, 0.0, 0.0, 1, "ALA", "A", "CA", "C", 70.0),
        (1.0, 0.0, 0.0, 2, "GLY", "A", "CA", "C", 90.0),
    ]
    ctx = Context(str(tmp_path / "plddt"), {"params": {}})
    ctx["structure"] = _form(rows)
    run(
        ctx,
        [
            {
                "name": "structure_plddt_profile",
                "inputs": ["structure"],
                "params": {"output": "profile"},
            }
        ],
    )
    form = ctx["profile"]
    assert form.dims == ["residue", "statistic"]
    assert form.data.shape == (2, 4)
    assert list((tmp_path / "plddt").rglob("*structure_plddt_profile*.json"))
