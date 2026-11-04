"""Tests for the interface core operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.structure_interface_core import (
    StructureInterfaceCoreStep,
    core_rows,
    relative_sasa,
)

COLUMNS = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element")


def _pdb_form(rows) -> Form:
    columns = list(zip(*rows))
    numerics = [np.asarray(columns[index], dtype=np.float64) for index in (0, 1, 2, 3)]
    encoders = {}
    encoded = {}
    for index, name in zip((4, 5, 6, 7), ("resname", "chain", "atom_name", "element")):
        encoder = LabelEncoder()
        encoded[name] = encoder.fit_transform(list(columns[index]))
        encoders[name] = encoder
    matrix = np.column_stack(
        [
            numerics[0],
            numerics[1],
            numerics[2],
            numerics[3],
            encoded["resname"],
            encoded["chain"],
            encoded["atom_name"],
            encoded["element"],
        ]
    ).astype(np.float32)
    return Form(
        data=matrix,
        dims=["atom", "field"],
        labels={
            "atom": {f"atom:{index}": index for index in range(len(rows))},
            "field": {name: index for index, name in enumerate(COLUMNS)},
        },
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


def _complex() -> Form:
    return _pdb_form(
        [
            (0.0, 0.0, 0.0, 1, "ALA", "A", "CA", "C"),
            (0.0, 1.5, 0.0, 1, "ALA", "A", "CB", "C"),
            (2.6, 0.0, 0.0, 1, "GLY", "B", "CA", "C"),
            (2.6, 1.5, 0.0, 1, "GLY", "B", "CB", "C"),
        ]
    )


def test_relative_sasa_far_and_close() -> None:
    radii = np.asarray([1.7, 1.7])
    far = np.asarray([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]])
    masks = [np.asarray([True, False]), np.asarray([False, True])]
    complex_far, isolated = relative_sasa(far, radii, masks, n_points=32)
    delta_far = isolated[0].sum() + isolated[1].sum() - complex_far.sum()
    assert delta_far == pytest.approx(0.0, abs=1e-6)

    close = np.asarray([[0.0, 0.0, 0.0], [2.8, 0.0, 0.0]])
    complex_close, isolated_close = relative_sasa(close, radii, masks, n_points=32)
    delta_close = isolated_close[0].sum() + isolated_close[1].sum() - complex_close.sum()
    assert delta_close > 0.5


def test_core_rows() -> None:
    labels = ["A:ALA:1", "B:GLY:2"]
    chains = ["A", "B"]
    rows = core_rows(
        labels,
        chains,
        np.asarray([20.0, 30.0]),
        np.asarray([100.0, 100.0]),
        np.asarray([0, 1]),
        core_fraction=0.25,
    )
    assert [row["residue"] for row in rows] == ["A:ALA:1", "B:GLY:2"]
    assert rows[0]["buried_fraction"] == pytest.approx(0.2)
    assert rows[1]["buried_fraction"] == pytest.approx(0.3)
    assert [row["is_core"] for row in rows] == [False, True]
    assert [row["side"] for row in rows] == ["binder", "target"]

    skipped = core_rows(
        labels,
        chains,
        np.asarray([0.001, 30.0]),
        np.asarray([100.0, 100.0]),
        np.asarray([0, 1]),
        core_fraction=0.25,
    )
    assert [row["residue"] for row in skipped] == ["B:GLY:2"]


def test_run(tmp_path) -> None:
    form = _complex()
    params = {"output": "core", "binder_chains": "A", "target_chains": "B", "core_fraction": 0.5}
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    run(ctx, [{"name": "structure_interface_core", "inputs": ["pdb"], "params": params}])
    out = ctx["core"]
    assert out.dims == ["residue", "statistic"]
    assert out.info["n_interface"] >= 1
    assert out.info["binder_chains"] == ["A"]
    assert out.info["target_chains"] == ["B"]


def test_errors(tmp_path) -> None:
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    single = _pdb_form(
        [
            (0.0, 0.0, 0.0, 1, "ALA", "A", "CA", "C"),
            (1.5, 0.0, 0.0, 1, "ALA", "A", "CB", "C"),
        ]
    )
    ctx["single"] = single
    with pytest.raises(StepError, match="at least two chains"):
        run(ctx, [{"name": "structure_interface_core", "inputs": ["single"], "params": {"output": "core"}}])
    ctx["complex"] = _complex()
    with pytest.raises((StepError, ValueError)):
        run(
            ctx,
            [
                {
                    "name": "structure_interface_core",
                    "inputs": ["complex"],
                    "params": {"output": "core", "binder_chains": "A", "target_chains": "B", "core_fraction": 1.5},
                }
            ],
        )
    assert StructureInterfaceCoreStep.definition["inputs_arity"] == 1
