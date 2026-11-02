"""Tests for the secondary-structure bridge network operator."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.structure_secondary_structure import assign_states, backbone_angles, segment_rows
from src.task.step.steps.structure_ss_bridge_network import (
    StructureSsBridgeNetworkStep,
    bridge_rows,
)

FIXTURE = Path(__file__).parent / "fixtures" / "vhh_1mel.pdb"
COLUMNS = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element")
LABEL = re.compile(r"^(helix|strand)-?(helix|strand)?:?(H|E)\d+-\d+/(H|E)\d+-\d+$")


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "bridges", **params}
        self.metadata = {}


def _pdb_form(path: Path, keep: tuple[str, ...] = COLUMNS) -> Form:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("ATOM  "):
            continue
        rows.append(
            (
                float(line[30:38]),
                float(line[38:46]),
                float(line[46:54]),
                float(int(line[22:26])),
                line[17:20].strip(),
                line[21:22].strip() or "_",
                line[12:16].strip(),
                (line[76:78].strip() or line[12:13].strip()),
            )
        )
    columns = list(zip(*rows))
    numerics = [np.asarray(columns[index], dtype=np.float64) for index in (0, 1, 2, 3)]
    encoded: dict[str, np.ndarray] = {}
    encoders: dict[str, LabelEncoder] = {}
    for index, name in zip((4, 5, 6, 7), ("resname", "chain", "atom_name", "element")):
        encoder = LabelEncoder()
        encoded[name] = encoder.fit_transform(list(columns[index]))
        encoders[name] = encoder
    matrix = np.column_stack(
        [numerics[0], numerics[1], numerics[2], numerics[3]]
        + [encoded[name] for name in ("resname", "chain", "atom_name", "element")]
    ).astype(np.float32)
    return Form(
        data=matrix[:, [COLUMNS.index(name) for name in keep]],
        dims=["atom", "field"],
        labels={
            "atom": {f"atom:{index}": index for index in range(len(rows))},
            "field": {name: position for position, name in enumerate(keep)},
        },
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


def test_bridge_rows_hand_computed() -> None:
    # Helix along x at y=0 and strand along x at y=4: every cross distance is
    # sqrt(dx**2 + 16) with dx in {0, 1, 2, 3}, so the minimum is 4.0 and all
    # 4 x 4 = 16 pairs sit at or below 5.0 (the largest is exactly 5.0).
    ca = np.asarray(
        [[float(i), 0.0, 0.0] for i in range(4)] + [[float(i), 4.0, 0.0] for i in range(4)]
    )
    segments = [
        {
            "state": "H",
            "start": 1,
            "end": 4,
            "length": 4,
            "residues": ["A:ALA:1", "A:ALA:2", "A:ALA:3", "A:ALA:4"],
        },
        {
            "state": "E",
            "start": 10,
            "end": 13,
            "length": 4,
            "residues": ["A:GLY:10", "A:GLY:11", "A:GLY:12", "A:GLY:13"],
        },
    ]
    index = {
        label: position
        for position, label in enumerate(
            [f"A:ALA:{i}" for i in range(1, 5)] + [f"A:GLY:{i}" for i in range(10, 14)]
        )
    }
    rows = bridge_rows(segments, ca, index, cutoff=8.0, contact=5.0)
    assert rows == [("helix-strand:H1-4/E10-13", 4.0, 16.0)]


def test_bridges_on_vhh_fixture() -> None:
    form = _pdb_form(FIXTURE)
    step = StructureSsBridgeNetworkStep()
    ctx = Ctx({"cutoff": 8.0, "contact": 5.0})
    step.run(ctx, [form])
    out = ctx["bridges"]
    assert out.dims == ["bridge", "statistic"]
    assert list(out.labels["statistic"]) == ["distance", "n_contacts"]
    assert out.data.dtype == np.float32
    assert out.info["n_segments"] >= 2
    assert out.data.shape[0] == out.info["n_bridges"]
    assert np.all(out.data[:, 0] <= 8.0 + 1e-6)
    assert np.all(out.data[:, 1] >= 0.0)
    assert np.any(out.data[:, 1] >= 1.0)
    for label in out.labels["bridge"]:
        assert re.match(r"^(helix-helix|helix-strand|strand-strand):[HE]\d+-\d+/[HE]\d+-\d+$", label)
    assert step.export(ctx)["n_bridges"] == out.info["n_bridges"]
    assert out.info["cutoff"] == 8.0 and out.info["contact"] == 5.0


def test_distances_are_independently_recomputable() -> None:
    form = _pdb_form(FIXTURE)
    ctx = Ctx({})
    StructureSsBridgeNetworkStep().run(ctx, [form])
    out = ctx["bridges"]

    labels = []
    names = form.info["encoders"]["field"]["atom_name"].inverse_transform(form.data[:, 6].astype(int))
    chain = form.info["encoders"]["field"]["chain"].inverse_transform(form.data[:, 5].astype(int))
    number = form.data[:, 3].astype(int)
    for index in range(form.data.shape[0]):
        labels.append(f"{chain[index]}:{number[index]}")
    ordered = list(dict.fromkeys(labels))
    ca = {}
    for index, label in enumerate(labels):
        if names[index] == "CA" and label not in ca:
            ca[label] = form.data[index, :3].astype(np.float64)
    residues = [label for label in ordered if label in ca]
    angles = backbone_angles(
        form.data[:, :3].astype(np.float64),
        labels,
        names,
    )
    states = assign_states(angles[1])
    segments = [segment for segment in segment_rows(states, angles[0]) if segment["state"] != "C"]
    segment_index = {segment["state"] + str(segment["start"]) + "-" + str(segment["end"]): segment for segment in segments}

    for label, row in zip(out.labels["bridge"], out.data):
        kind, rest = label.split(":")
        first, second = rest.split("/")
        first_state, first_range = first[0], first[1:]
        second_state, second_range = second[0], second[1:]
        points_a = np.asarray([ca[residue] for residue in segment_index[first_state + first_range]["residues"]])
        points_b = np.asarray([ca[residue] for residue in segment_index[second_state + second_range]["residues"]])
        distances = np.linalg.norm(points_a[:, None, :] - points_b[None, :, :], axis=2)
        assert row[0] == pytest.approx(float(distances.min()), abs=1e-4)
        assert row[1] == pytest.approx(float(np.sum(distances <= 5.0)), abs=1e-6)


def test_parameter_errors() -> None:
    form = _pdb_form(FIXTURE)
    cases = [
        ({"window": 0}, "window must be between"),
        ({"cutoff": 0.5}, "cutoff must be in"),
        ({"contact": 9.0, "cutoff": 8.0}, "contact must be in"),
        ({"min_length": 0}, "min_length must be at least 1"),
    ]
    for overrides, message in cases:
        ctx = Ctx(overrides)
        with pytest.raises(StepError, match=message):
            StructureSsBridgeNetworkStep().run(ctx, [form])


def test_wrong_input_contract() -> None:
    form = _pdb_form(FIXTURE)
    renamed = Form(
        data=form.data,
        dims=["atom", "other"],
        labels={"atom": form.labels["atom"], "other": form.labels["field"]},
        info=form.info,
    )
    ctx = Ctx({})
    with pytest.raises(StepError, match="a structure form with dims"):
        StructureSsBridgeNetworkStep().run(ctx, [renamed])


def test_missing_atom_name_column() -> None:
    form = _pdb_form(FIXTURE, keep=("x", "y", "z", "residue_number", "resname", "chain", "element"))
    ctx = Ctx({})
    with pytest.raises(StepError, match="atom_name"):
        StructureSsBridgeNetworkStep().run(ctx, [form])
