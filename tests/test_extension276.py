"""structure_ligand_interaction_fingerprint: interaction counts."""

import numpy as np
import pytest

from src.core.forms import Form
from src.core.errors import StepError
from src.reader.readers._encoder import LabelEncoder
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_ligand_interaction_fingerprint import (
    StructureLigandInteractionFingerprintStep,
    fingerprint_rows,
)

COLUMNS = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element")


def _form(rows):
    encoders = {}
    codes = {}
    for index, name in enumerate(COLUMNS):
        if name in ("x", "y", "z", "residue_number"):
            continue
        encoder = LabelEncoder()
        values = [str(row[index]) for row in rows]
        encoded = encoder.fit_transform(values)
        encoders[name] = encoder
        codes[name] = [float(code) for code in encoded]
    data = []
    for row_index, row in enumerate(rows):
        values = []
        for name, value in zip(COLUMNS, row):
            if name in ("x", "y", "z", "residue_number"):
                values.append(float(value))
            else:
                values.append(codes[name][row_index])
        data.append(values)
    return Form(
        data=np.asarray(data, dtype=np.float32),
        dims=["atom", "field"],
        labels={
            "atom": {f"atom{i}": i for i in range(len(rows))},
            "field": {name: i for i, name in enumerate(COLUMNS)},
        },
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


def _rows():
    return [
        (0.0, 0.0, 0.0, 1, "LIG", "L", "C1", "C"),
        (3.0, 0.0, 0.0, 10, "PHE", "A", "CZ", "C"),
        (2.5, 0.0, 0.0, 11, "ASP", "A", "OD1", "O"),
        (2.0, 0.0, 0.0, 12, "LIG", "L", "N1", "N"),
        (30.0, 0.0, 0.0, 13, "LYS", "A", "NZ", "N"),
    ]


def test_fingerprint_rows_hand_case():
    rows = fingerprint_rows(
        np.zeros((2, 3)),
        np.array(["C", "N"]),
        ["L:C1", "L:N1"],
        np.array([[3.0, 0.0, 0.0], [2.5, 0.0, 0.0], [30.0, 0.0, 0.0]]),
        np.array(["C", "O", "N"]),
        np.array(["PHE", "ASP", "LYS"]),
        ["A:PHE:10", "A:ASP:11", "A:LYS:13"],
        cutoff=4.0,
    )
    first = rows[0]
    assert first["n_contacts"] == 2
    assert first["n_hydrophobic"] == 1
    assert first["n_aromatic"] == 1
    assert first["n_polar"] == 0
    assert first["min_distance"] == pytest.approx(2.5)
    second = rows[1]
    assert second["n_contacts"] == 2
    assert second["n_polar"] == 1
    assert second["n_charged"] == 1


def test_run_writes_fingerprint_table():
    import tempfile

    form = _form(_rows())
    ctx = Context(tempfile.mkdtemp(), {"params": {}})
    ctx["pdb"] = form
    run(ctx, [{"name": "structure_ligand_interaction_fingerprint", "inputs": ["pdb"], "params": {"output": "fingerprint"}}])
    result = ctx["fingerprint"]
    assert result.dims == ["atom", "statistic"]
    assert result.data.shape[0] == 2
    assert result.info["n_ligand_atoms"] == 2


def test_errors():
    import tempfile

    form = _form(_rows())
    ctx = Context(tempfile.mkdtemp(), {"params": {}})
    ctx["pdb"] = form
    with pytest.raises(StepError, match="no ligand atom matches"):
        run(ctx, [{"name": "structure_ligand_interaction_fingerprint", "inputs": ["pdb"], "params": {"output": "f", "ligand_resnames": "XXX"}}])
