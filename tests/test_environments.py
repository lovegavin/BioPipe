"""Isolated interpreter bridge for operators with conflicting runtimes."""

import json
from pathlib import Path

import numpy as np
import pytest

from operon import environments


def _descriptor(name="structure_interface_core", environment="fake"):
    registry = json.loads((Path(__file__).resolve().parents[1] / "library/seed/operon/builtin_packages.json").read_text(encoding="utf-8"))
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

    monkeypatch.setattr(environments, "resolve", lambda name: Path(sys.executable))
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


def test_bridge_preserves_axis_metadata_missing_values_and_cleans_files(monkeypatch, tmp_path):
    import sys
    from src.core.forms import Form
    monkeypatch.setattr(environments.tempfile, 'tempdir', str(tmp_path))
    form = Form(data=np.array([[3.0, np.nan]]), dims=['sample', 'feature'],
                labels={'sample': {'s': 0}, 'feature': {'a': 0, 'b': 1}},
                info={'missing_code': np.nan, 'group': ['control']},
                axis_info={'sample': ['group']})
    result, _, _ = environments.run_step(_descriptor('log_transform'), [form],
                                         {'output': 'log', 'base': 2, 'pseudocount': 1}, Path(sys.executable))
    assert result.axis_info == form.axis_info
    assert result.info['group'] == ['control']
    assert np.isnan(result.info['missing_code'])
    np.testing.assert_allclose(result.data, [[2, np.nan]], equal_nan=True)
    assert not list(tmp_path.glob('envbridge-*'))
    with pytest.raises(Exception):
        environments.run_step(_descriptor('log_transform'), [form],
                              {'output': 'log', 'pseudocount': -1}, Path(sys.executable))
    assert not list(tmp_path.glob('envbridge-*'))


def test_bridge_uses_portable_interpreter_and_process_environment(monkeypatch, tmp_path):
    import os
    executable = tmp_path / 'example/python.exe'
    executable.parent.mkdir()
    executable.touch()
    executable.chmod(0o755)
    monkeypatch.setenv('OPERON_ENVIRONMENTS_ROOT', str(tmp_path))
    monkeypatch.setenv('SystemRoot', 'windows-system-location')
    monkeypatch.setenv('PYTHONHOME', 'unrelated-python')
    monkeypatch.setenv('PYTHONPATH', 'unrelated-modules')
    monkeypatch.setenv('HF_ENDPOINT', 'https://example.invalid/models')
    assert environments.resolve('example') == executable
    env = environments.worker_environment(executable)
    assert {key.upper(): value for key, value in env.items()}['SYSTEMROOT'] == 'windows-system-location'
    assert 'PYTHONHOME' not in env
    assert env['PYTHONPATH'] == str(environments.code_root())
    assert env['PATH'].split(os.pathsep)[0] == str(executable.parent)
    assert env['HF_ENDPOINT'] == 'https://example.invalid/models'
