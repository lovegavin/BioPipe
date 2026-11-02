"""Tests for the B-factor disorder profile operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.structure_disorder_profile import (
    disorder_rows,
    residue_table,
)

COLUMNS = (
    "x",
    "y",
    "z",
    "residue_number",
    "resname",
    "chain",
    "atom_name",
    "element",
    "bfactor",
)


def _form(rows, columns: tuple[str, ...] = COLUMNS) -> Form:
    position = {name: index for index, name in enumerate(COLUMNS)}
    arrays: list[np.ndarray] = []
    encoders = {}
    for name in columns:
        column = [row[position[name]] for row in rows]
        if name in ("x", "y", "z", "residue_number", "bfactor"):
            arrays.append(np.asarray(column, dtype=np.float64))
        else:
            encoder = LabelEncoder()
            arrays.append(np.asarray(encoder.fit_transform(column), dtype=np.float64))
            encoders[name] = encoder
    return Form(
        data=np.column_stack(arrays).astype(np.float32),
        dims=["atom", "field"],
        labels={
            "atom": {f"atom:{index}": index for index in range(len(rows))},
            "field": {name: index for index, name in enumerate(columns)},
        },
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


ROWS = [
    (0.0, 0.0, 0.0, 1, "ALA", "A", "CA", "C", 10.0),
    (4.0, 0.0, 0.0, 2, "GLY", "A", "CA", "C", 20.0),
    (8.0, 0.0, 0.0, 4, "SER", "A", "CA", "C", 30.0),
]


def _params(**overrides):
    params = {"atom_dim": "atom", "field_dim": "field", "residue_dim": "residue",
              "z_clip": 3.0, "output": "disorder"}
    params.update(overrides)
    return params


def test_residue_table_reads_bfactors():
    form = _form(ROWS)
    records = residue_table(form, "atom", "field")
    assert [record["label"] for record in records] == ["A:ALA:1", "A:GLY:2", "A:SER:4"]
    assert [record["mean_bfactor"] for record in records] == pytest.approx([10.0, 20.0, 30.0])
    with pytest.raises(StepError, match="no 'bfactor' column"):
        residue_table(_form(ROWS, COLUMNS[:-1]), "atom", "field")
    with pytest.raises(StepError, match="no residue carries a finite"):
        rows = [
            (0.0, 0.0, 0.0, 1, "ALA", "A", "CA", "C", float("nan")),
        ]
        residue_table(_form(rows), "atom", "field")


def test_disorder_rows_z_scores_and_gaps():
    rows, summary = disorder_rows(residue_table(_form(ROWS), "atom", "field"), z_clip=3.0)
    assert [row["label"] for row in rows] == ["A:ALA:1", "A:GLY:2", "A:SER:4"]
    assert [row["gap_to_next"] for row in rows] == [0, 1, 0]
    assert [row["bfactor_z"] for row in rows] == pytest.approx(
        [-1.224745, 0.0, 1.224745], abs=1e-5
    )
    assert [row["disorder_score"] for row in rows] == pytest.approx(
        [-0.612372, 0.5, 0.612372], abs=1e-5
    )
    assert summary["n_residues"] == 3
    assert summary["missing_residues"] == 1
    assert summary["mean_disorder"] == pytest.approx(0.166667, abs=1e-5)


def test_disorder_rows_clips_z_scores():
    wide = [
        (0.0, 0.0, 0.0, 1, "ALA", "A", "CA", "C", 0.0),
        (4.0, 0.0, 0.0, 2, "GLY", "A", "CA", "C", 0.0),
        (8.0, 0.0, 0.0, 3, "SER", "A", "CA", "C", 0.0),
        (12.0, 0.0, 0.0, 4, "THR", "A", "CA", "C", 100.0),
    ]
    rows, _summary = disorder_rows(residue_table(_form(wide), "atom", "field"), z_clip=0.2)
    # mean 25, population sd 43.3 -> z(-25) = -0.577 and z(75) = 1.732; both clamp to 0.2.
    assert rows[0]["bfactor_z"] == pytest.approx(-0.2)
    assert rows[3]["bfactor_z"] == pytest.approx(0.2)
    assert rows[0]["disorder_score"] == pytest.approx(-0.1)
    assert rows[3]["disorder_score"] == pytest.approx(0.1)


def test_run_writes_disorder_table(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx.step_params = _params()
    ctx["pdb"] = _form(ROWS)
    run(ctx, [
        {
            "name": "structure_disorder_profile",
            "inputs": ["pdb"],
            "params": dict(ctx.step_params),
        }
    ])
    output = ctx["disorder"]
    assert list(output.dims) == ["residue", "statistic"]
    assert output.data.shape == (3, 4)
    assert output.labels["residue"]["A:GLY:2"] == 1
    assert output.data[1].tolist() == pytest.approx([20.0, 0.0, 1.0, 0.5], abs=1e-5)
    assert output.info["n_residues"] == 3
    assert output.info["missing_residues"] == 1


def test_validation_errors(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx.step_params = _params(z_clip=0.0)
    ctx["pdb"] = _form(ROWS)
    with pytest.raises(StepError, match="z_clip must be positive"):
        run(ctx, [
            {
                "name": "structure_disorder_profile",
                "inputs": ["pdb"],
                "params": dict(ctx.step_params),
            }
        ])

    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx.step_params = _params(z_clip=50.0)
    ctx["pdb"] = _form(ROWS)
    with pytest.raises((StepError, ValueError), match="z_clip|maximum"):
        run(ctx, [
            {
                "name": "structure_disorder_profile",
                "inputs": ["pdb"],
                "params": dict(ctx.step_params),
            }
        ])
