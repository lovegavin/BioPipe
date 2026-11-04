import numpy as np
import pytest

from src.core.errors import StepError
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.structure_surface_hydrophobicity import (
    KD,
    STATISTICS,
    StructureSurfaceHydrophobicityStep,
)

FIELDS = ["x", "y", "z", "occupancy", "bfactor", "residue_number", "chain", "resname", "element"]


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _form(rows, fields=FIELDS):
    data = np.zeros((len(rows), len(fields)), dtype=np.float32)
    encoders = {}
    for column in ("chain", "resname", "element"):
        encoder = LabelEncoder()
        data[:, fields.index(column)] = encoder.fit_transform([row[column] for row in rows])
        encoders[column] = encoder
    for column in ("residue_number",):
        encoder = LabelEncoder()
        data[:, fields.index(column)] = encoder.fit_transform([row[column] for row in rows])
        encoders[column] = encoder
    for row_index, row in enumerate(rows):
        for name in ("x", "y", "z", "occupancy", "bfactor"):
            if name in fields:
                data[row_index, fields.index(name)] = row[name]
    return __import__("src.core.forms.form", fromlist=["Form"]).Form(
        data=data,
        dims=["atom", "field"],
        labels={"atom": {f"atom:{index}": index for index in range(len(rows))},
                "field": {name: index for index, name in enumerate(fields)}},
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
        axis_info={},
    )


def _rows(entries):
    rows = []
    for entry in entries:
        rows.append({
            "x": entry[0], "y": entry[1], "z": entry[2], "occupancy": 1.0, "bfactor": 20.0,
            "residue_number": entry[3], "chain": entry[4], "resname": entry[5], "element": entry[6],
        })
    return rows


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return ctx["out"], step.export(ctx)


def test_columns_and_scale():
    rows = _rows([
        (0.0, 0.0, 0.0, "1", "A", "ALA", "C"),
        (1.5, 0.0, 0.0, "1", "A", "ALA", "C"),
        (0.0, 1.5, 0.0, "1", "A", "ALA", "N"),
        (30.0, 0.0, 0.0, "2", "A", "VAL", "C"),
        (31.5, 0.0, 0.0, "2", "A", "VAL", "C"),
        (30.0, 1.5, 0.0, "2", "A", "VAL", "N"),
    ])
    form = _form(rows)
    out, export = _run(StructureSurfaceHydrophobicityStep(), {}, form)
    assert list(out.dims) == ["residue", "statistic"]
    assert [name for name, _ in sorted(out.labels["statistic"].items(), key=lambda item: item[1])] == list(STATISTICS)
    assert out.data.shape == (2, 4)
    labels = {index: name for name, index in out.labels["residue"].items()}
    assert set(labels.values()) == {"A:ALA:1", "A:VAL:2"}
    assert np.allclose(out.data[:, 2], [4.2, 1.8], rtol=1e-6)
    assert out.info["total_sasa"] > 0
    assert 0.0 < out.info["hydrophobic_fraction"] <= 1.0
    assert export["n_residues"] == 2


def test_isolated_residue_matches_sphere_area():
    # A residue whose atoms are far apart from each other must expose the full sum of spheres.
    rows = _rows([
        (0.0, 0.0, 0.0, "1", "A", "ALA", "C"),
        (100.0, 0.0, 0.0, "1", "A", "ALA", "C"),
    ])
    form = _form(rows)
    out, _ = _run(StructureSurfaceHydrophobicityStep(), {"n_points": 512, "probe_radius": 1.4}, form)
    expected = sum(4.0 * np.pi * (radius + 1.4) ** 2 for radius in (1.70, 1.70))
    assert out.data.shape == (1, 4)
    assert np.isclose(out.data[0, 0], expected, rtol=0.02)
    assert np.isclose(out.data[0, 2], KD["ALA"])


def test_parameter_and_input_errors():
    rows = _rows([(0.0, 0.0, 0.0, "1", "A", "ALA", "C")])
    form = _form(rows)
    with pytest.raises(StepError, match="probe_radius must be between"):
        _run(StructureSurfaceHydrophobicityStep(), {"probe_radius": 4.0}, form)
    with pytest.raises(StepError, match="n_points must be between"):
        _run(StructureSurfaceHydrophobicityStep(), {"n_points": 8}, form)
    with pytest.raises(StepError, match="is required"):
        _run(StructureSurfaceHydrophobicityStep(), {"field_dim": "other"}, form)

    hydrogen = _form(_rows([(0.0, 0.0, 0.0, "1", "A", "ALA", "H")]))
    with pytest.raises(StepError, match="no heavy atoms"):
        _run(StructureSurfaceHydrophobicityStep(), {}, hydrogen)


def test_missing_coordinate_column():
    rows = _rows([(0.0, 0.0, 0.0, "1", "A", "ALA", "C")])
    fields = ["y", "z", "occupancy", "bfactor", "residue_number", "chain", "resname", "element"]
    form = _form([{**row, "x": row["y"]} for row in rows], fields)
    with pytest.raises(StepError, match="no 'x' column"):
        _run(StructureSurfaceHydrophobicityStep(), {}, form)
