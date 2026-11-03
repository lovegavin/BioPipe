"""Isolated interpreter bridge for operators with conflicting runtimes."""

import json
from pathlib import Path

import numpy as np
import pytest

from biopipe import environments


def _descriptor(name="structure_interface_core", environment="fake"):
    registry = json.loads((Path(__file__).resolve().parents[1] / "biopipe/builtin_packages.json").read_text())
    descriptor = next(e for p in registry["packages"] for e in p["descriptors"] if e["id"] == name)
    return {**descriptor, "resources": {**descriptor["resources"], "environment": environment}}


def _form():
    from src.core.forms import Form
    from src.reader.readers._encoder import LabelEncoder

    columns = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element")
    raw = [
        (0, 0, 0, 1, "ALA", "A", "CA", "C"),
        (4, 0, 0, 1, "ALA", "A", "CA", "C"),
        (0, 0, 5, 2, "GLY", "B", "CA", "C"),
        (4, 0, 5, 2, "GLY", "B", "CA", "C"),
    ]
    encoders, data = {}, []
    for column in ("resname", "chain", "atom_name", "element"):
        index = columns.index(column)
        values = [row[index] for row in raw]
        encoder = LabelEncoder()
        encoder.fit_transform(values)
        encoders[column] = encoder
    for row in raw:
        values = []
        for index, (column, value) in enumerate(zip(columns, row)):
            values.append(float(encoders[column].mapping[value]) if column in encoders else float(value))
        data.append(values)
    return Form(
        data=np.asarray(data, dtype=np.float32),
        dims=["atom", "field"],
        labels={"atom": {f"atom{i}": i for i in range(len(raw))},
                "field": {name: index for index, name in enumerate(columns)}},
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


def test_bridge_runs_a_step_in_the_environment_interpreter(monkeypatch, tmp_path):
    import sys

    fake = tmp_path / "fakeenv/bin/python"
    fake.parent.mkdir(parents=True)
    fake.write_text("#!/bin/sh\nexec " + sys.executable + ' "$@"\n')
    fake.chmod(0o755)
    monkeypatch.setattr(environments, "resolve", lambda name: fake)
    monkeypatch.setattr(environments, "code_root", lambda: Path(__file__).resolve().parents[1])

    step = environments.proxy_step(_descriptor())()

    class Ctx(dict):
        step_params = {"output": "core", "binder_chains": "A", "target_chains": "B"}
        metadata = {}

    ctx = Ctx()
    step.run(ctx, [_form()])
    result = ctx["core"]
    assert result.dims == ["residue", "statistic"]
    assert result.data.shape[1] == 4
    assert "n_core" in result.info and "n_rim" in result.info
    assert isinstance(step.export(ctx), dict)


def test_bridge_reports_a_missing_environment():
    from src.core.errors import StepError

    step = environments.proxy_step(_descriptor(environment="absent"))()

    class Ctx(dict):
        step_params = {"output": "core"}
        metadata = {}

    with pytest.raises(StepError, match="is not installed"):
        step.run(Ctx(), [_form()])
