"""Contract tests for structure_openmm_energy."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms import Form
from src.reader import read_source
from src.task.context import Context
from src.task.runner import run
pytest.importorskip("openmm")

from src.task.step.steps import structure_openmm_energy as module

FIXTURE = "/home/gavin/BioPipe/tests/fixtures/vhh_1mel.pdb"


def _pdb_form(tmp_path):
    lines = [line for line in open(FIXTURE) if line.startswith("ATOM") and line[21] == "A"]
    path = tmp_path / "chain_a.pdb"
    path.write_text("\n".join(lines) + "\nTER\nEND\n")
    return read_source(str(path), ["atom", "field"], {"atom": "auto", "field": "builtin"}), path


def test_write_pdb_roundtrip(tmp_path):
    form, _ = _pdb_form(tmp_path)
    target = tmp_path / "written.pdb"
    count = module.write_pdb(form, "atom", "field", target)
    assert count == form.data.shape[0]
    text = target.read_text()
    assert text.startswith("ATOM")
    assert text.rstrip().endswith("END")
    from openmm.app import PDBFile

    pdb = PDBFile(str(target))
    assert pdb.topology.getNumAtoms() == count


def test_missing_columns():
    form = Form(data=np.zeros((1, 2)), dims=["atom", "field"], labels={"atom": {"a": 0}, "field": {"x": 0, "y": 1}}, info={})
    with pytest.raises(StepError, match="has no"):
        module.write_pdb(form, "atom", "field", __import__("pathlib").Path("/tmp/x.pdb"))


def test_validation_errors(tmp_path):
    form, _ = _pdb_form(tmp_path)
    with pytest.raises(StepError, match="must be between 0 and 14"):
        module.StructureOpenmmEnergyStep().run(_ctx({"output": "e", "ph": 20.0}), [form])
    with pytest.raises(StepError, match="max_iterations must be at least 1"):
        module.StructureOpenmmEnergyStep().run(_ctx({"output": "e", "max_iterations": 0}), [form])


def _ctx(params):
    ctx = Context(str(__import__("tempfile").mkdtemp()), {"params": {}})
    ctx.step_params = params
    return ctx


def test_real_openmm_energy(tmp_path, monkeypatch):
    pytest.importorskip("openmm")
    pytest.importorskip("pdbfixer")
    form, _ = _pdb_form(tmp_path)
    import tempfile

    ctx = Context(tempfile.mkdtemp(), {"params": {}})
    ctx["pdb"] = form
    run(
        ctx,
        [
            {
                "name": "structure_openmm_energy",
                "inputs": ["pdb"],
                "params": {"output": "energy", "minimize": True, "max_iterations": 200},
            }
        ],
    )
    result = ctx["energy"]
    assert result.data.shape == (2, 2)
    initial, final = float(result.data[0, 0]), float(result.data[1, 0])
    assert np.isfinite(initial) and np.isfinite(final)
    assert final <= initial + 1e-6
    assert result.info["n_particles"] > 1000
