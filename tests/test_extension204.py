import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.structure_metal_coordination import (
    STATISTICS,
    StructureMetalCoordinationStep,
    coordination_shell,
)

FIELDS = ["x", "y", "z", "residue_number", "chain", "resname", "element", "atom_name"]


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _form(rows, fields=FIELDS):
    data = np.zeros((len(rows), len(fields)), dtype=np.float32)
    encoders = {}
    for column in ("chain", "resname", "residue_number", "element", "atom_name"):
        encoder = LabelEncoder()
        data[:, fields.index(column)] = encoder.fit_transform([row[column] for row in rows])
        encoders[column] = encoder
    for row_index, row in enumerate(rows):
        for name in ("x", "y", "z"):
            data[row_index, fields.index(name)] = row[name]
    return Form(
        data=data,
        dims=["atom", "field"],
        labels={"atom": {f"atom:{index}": index for index in range(len(rows))},
                "field": {name: index for index, name in enumerate(fields)}},
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
        axis_info={},
    )


def _row(coords, number, resname, element, name, chain="A"):
    return {"x": coords[0], "y": coords[1], "z": coords[2], "residue_number": number,
            "chain": chain, "resname": resname, "element": element, "atom_name": name}


def _site_rows():
    return [
        _row((0.0, 0.0, 0.0), "401", "ZN", "ZN", "ZN"),
        _row((2.0, 0.0, 0.0), "10", "HOH", "O", "O"),
        _row((-2.0, 0.0, 0.0), "11", "HOH", "O", "O"),
        _row((0.0, 2.0, 0.0), "12", "ASP", "O", "OD1"),
        _row((0.0, 0.0, 2.0), "13", "ASP", "O", "OD2"),
        _row((0.0, 0.0, 3.5), "14", "CYS", "S", "SG"),
        _row((0.0, 2.2, 0.0), "15", "HIS", "N", "NE2"),
    ]


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return ctx["out"], step.export(ctx)


def test_hand_coordination():
    rows = _site_rows()
    ligands = [(row["element"], f"{row['chain']}:{row['resname']}:{row['residue_number']}") for row in rows[1:]]
    coords = np.asarray([[row["x"], row["y"], row["z"]] for row in rows], dtype=float)
    shells = coordination_shell([0], ligands, coords[[0]], coords[1:], 2.8)
    assert len(shells) == 1
    shell = shells[0]
    assert shell["n_ligands"] == 5.0
    assert shell["n_oxygen"] == 4.0
    assert shell["n_nitrogen"] == 1.0
    assert shell["n_sulfur"] == 0.0
    assert np.isclose(shell["mean_distance"], (4 * 2.0 + 2.2) / 5)


def test_step_output_and_label():
    form = _form(_site_rows())
    out, export = _run(StructureMetalCoordinationStep(), {"cutoff": 2.8}, form)
    assert list(out.dims) == ["metal", "statistic"]
    labels = [name for name, _ in sorted(out.labels["statistic"].items(), key=lambda item: item[1])]
    assert labels == list(STATISTICS)
    assert out.data.shape == (1, 5)
    assert out.labels["metal"] == {"A:ZN:401": 0}
    assert out.data[0, 0] == 5
    assert np.isclose(out.data[0, 1], (4 * 2.0 + 2.2) / 5, rtol=1e-5)
    assert export["n_ions"] == 1


def test_cutoff_includes_sulfur():
    form = _form(_site_rows())
    out, _ = _run(StructureMetalCoordinationStep(), {"cutoff": 3.8}, form)
    assert out.data[0, 0] == 6
    assert out.data[0, 4] == 1


def test_errors():
    form = _form(_site_rows())
    with pytest.raises(StepError, match="cutoff must be between"):
        _run(StructureMetalCoordinationStep(), {"cutoff": 6.0}, form)
    with pytest.raises(StepError, match="no metal ion"):
        no_metal = _form([row for row in _site_rows() if row["resname"] != "ZN"])
        _run(StructureMetalCoordinationStep(), {}, no_metal)
    with pytest.raises(StepError, match="no ligand atom"):
        far = _site_rows()
        for row in far[1:]:
            row["x"] = row["x"] + 50.0
        _run(StructureMetalCoordinationStep(), {}, _form(far))
    with pytest.raises(StepError, match="is required"):
        _run(StructureMetalCoordinationStep(), {"field_dim": "other"}, form)
