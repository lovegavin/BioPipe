"""Tests for the structural zinc-site operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.structure_zinc_sites import atom_labels, zinc_sites

COLUMNS = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element")

ROWS = [
    (0.0, 0.0, 0.0, 100, "ZN", "A", "ZN", "ZN"),
    (2.3, 0.0, 0.0, 10, "CYS", "A", "SG", "S"),
    (0.0, 2.5, 0.0, 11, "CYS", "A", "SG", "S"),
    (0.0, 0.0, 2.8, 12, "HIS", "A", "ND1", "N"),
    (0.0, 0.0, 2.0, 13, "LYS", "A", "NZ", "N"),
    (1.0, 0.0, 0.0, 14, "ASP", "A", "OD1", "O"),
    (20.0, 0.0, 0.0, 200, "ZN", "B", "ZN", "ZN"),
    (22.3, 0.0, 0.0, 20, "CYS", "B", "SG", "S"),
]


def _structure_form(rows, columns: tuple[str, ...] = COLUMNS) -> Form:
    position = {name: index for index, name in enumerate(COLUMNS)}
    arrays: list[np.ndarray] = []
    encoders = {}
    for name in columns:
        column = [row[position[name]] for row in rows]
        if name in ("x", "y", "z", "residue_number"):
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


def _arrays(rows=ROWS):
    coordinates = np.asarray([row[:3] for row in rows], dtype=np.float64)
    elements = np.asarray([row[7] for row in rows], dtype=str)
    names = np.asarray([row[6] for row in rows], dtype=str)
    labels = np.asarray(
        [f"{row[5]}:{row[4]}:{row[3]}" for row in rows], dtype=object
    )
    return coordinates, elements, names, labels


def test_atom_labels() -> None:
    labels = atom_labels(_structure_form(ROWS), "field")
    assert labels[0] == "A:ZN:100"
    assert labels[1] == "A:CYS:10"
    assert labels[6] == "B:ZN:200"


def test_zinc_site_with_atom_names() -> None:
    coordinates, elements, names, labels = _arrays()
    records = zinc_sites(
        coordinates, elements, names, labels, cutoff=2.9, min_ligands=3
    )
    assert len(records) == 1
    record = records[0]
    assert record["zinc_label"] == "A:ZN:100"
    assert record["n_ligands"] == 3
    assert record["mean_distance"] == pytest.approx((2.3 + 2.5 + 2.8) / 3.0)
    assert record["min_distance"] == pytest.approx(2.3)
    assert [row["residue"] for row in record["ligands"]] == [
        "A:CYS:10",
        "A:CYS:11",
        "A:HIS:12",
    ]
    assert [row["atom"] for row in record["ligands"]] == ["SG", "SG", "ND1"]


def test_element_only_fallback_counts_any_nitrogen() -> None:
    coordinates, elements, _, labels = _arrays()
    records = zinc_sites(
        coordinates, elements, None, labels, cutoff=2.9, min_ligands=3
    )
    assert records[0]["n_ligands"] == 4
    assert "A:LYS:13" in [row["residue"] for row in records[0]["ligands"]]


def test_min_ligands_filters_sites() -> None:
    coordinates, elements, names, labels = _arrays()
    records = zinc_sites(
        coordinates, elements, names, labels, cutoff=2.9, min_ligands=4
    )
    assert records == []
    protein = elements != "ZN"
    with pytest.raises(StepError, match="no zinc atoms"):
        zinc_sites(
            coordinates[protein], elements[protein], names[protein], labels[protein]
        )
    with pytest.raises(StepError, match="no cysteine SG or histidine"):
        zinc_sites(
            coordinates[:1],
            elements[:1],
            names[:1],
            labels[:1],
        )


def test_runner_round_trip(tmp_path) -> None:
    ctx = Context(str(tmp_path / "zinc"), {"params": {}})
    ctx["pdb"] = _structure_form(ROWS)
    run(
        ctx,
        [
            {
                "name": "structure_zinc_sites",
                "inputs": ["pdb"],
                "params": {"min_ligands": 3, "output": "sites"},
            }
        ],
    )
    form = ctx["sites"]
    assert form.dims == ["site", "statistic"]
    assert form.data.shape == (1, 3)
    assert form.data[0] == pytest.approx([3.0, (2.3 + 2.5 + 2.8) / 3.0, 2.3])
    assert set(form.labels["site"]) == {"zn1:A:ZN:100"}
    assert set(form.labels["statistic"]) == {
        "n_ligands",
        "mean_distance",
        "min_distance",
    }
    assert form.info["n_sites"] == 1
    assert form.info["sites"][0]["ligands"][0]["atom"] == "SG"
    exports = sorted((tmp_path / "zinc").rglob("*structure_zinc_sites*.json"))
    assert exports


def test_runner_validation_errors(tmp_path) -> None:
    ctx = Context(str(tmp_path / "bad"), {"params": {}})
    ctx["pdb"] = _structure_form(ROWS)

    def _call(**params) -> None:
        run(
            ctx,
            [
                {
                    "name": "structure_zinc_sites",
                    "inputs": ["pdb"],
                    "params": {"output": "sites", **params},
                }
            ],
        )

    with pytest.raises((StepError, ValueError), match="coordination_cutoff"):
        _call(coordination_cutoff=1.0)
    with pytest.raises((StepError, ValueError), match="min_ligands"):
        _call(min_ligands=9)
    with pytest.raises(StepError, match="no zinc site reaches min_ligands"):
        _call(min_ligands=5)
    with pytest.raises(StepError, match="no 'element' column"):
        other = Context(str(tmp_path / "other"), {"params": {}})
        other["pdb"] = _structure_form(ROWS, columns=tuple(c for c in COLUMNS if c != "element"))
        run(
            other,
            [
                {
                    "name": "structure_zinc_sites",
                    "inputs": ["pdb"],
                    "params": {"output": "sites"},
                }
            ],
        )
