"""Contract tests for interface_alanine_scan."""

from __future__ import annotations

import pytest

pytest.importorskip("openmm")
pytest.importorskip("pdbfixer")

from src.core.errors import StepError
from src.task.step.steps import interface_alanine_scan as module

FIXTURE = "/home/gavin/BioPipe/tests/fixtures/vhh_1mel.pdb"


def _complex_text(tmp_path):
    lines = [line for line in open(FIXTURE) if line.startswith("ATOM") and line[21] in "ABLM"]
    return "\n".join(lines) + "\nTER\nEND\n"


def test_mutate_to_alanine_truncates_side_chain(tmp_path):
    text = _complex_text(tmp_path)
    mutated = module.mutate_to_alanine(text, "L", 30)
    kept = [line for line in mutated.splitlines() if line.startswith("ATOM") and line[21] == "L" and line[22:26].strip() == "30"]
    names = {line[12:16].strip() for line in kept}
    assert names <= module._BACKBONE
    assert "CB" in names or "CA" in names
    assert all(line[17:20] == "ALA" for line in kept)
    with pytest.raises(StepError, match="is not in the structure file"):
        module.mutate_to_alanine(text, "Z", 999)


def test_validation(tmp_path):
    import numpy as np

    from src.core.forms import Form

    form = Form(data=np.zeros((1, 2)), dims=["atom", "field"], labels={"atom": {"a": 0}, "field": {"x": 0, "y": 1}}, info={})
    step = module.InterfaceAlanineScanStep()
    with pytest.raises(StepError, match="binder_chains must name at least one chain"):
        step.run(_ctx({"output": "scan"}), [form])
    with pytest.raises(StepError, match="are in both sides"):
        step.run(_ctx({"output": "scan", "binder_chains": "A", "target_chains": "A"}), [form])


def _ctx(params):
    import tempfile

    from src.task.context import Context

    ctx = Context(tempfile.mkdtemp(), {"params": {}})
    ctx.step_params = params
    return ctx


def test_interface_contacts_are_ranked():
    import tempfile
    from pathlib import Path

    workdir = Path(tempfile.mkdtemp())
    path = workdir / "complex.pdb"
    path.write_text(_complex_text(workdir))
    contacts = module.interface_contacts(path, ("A", "B"), ("L", "M"), 4.5)
    assert contacts
    assert all(chain in ("L", "M") for chain, _ in contacts)


def test_real_alanine_scan(tmp_path):
    import tempfile
    from pathlib import Path

    from src.reader import read_source
    from src.task.context import Context
    from src.task.runner import run

    path = tmp_path / "complex.pdb"
    path.write_text(_complex_text(tmp_path))
    form = read_source(str(path), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    ctx = Context(tempfile.mkdtemp(), {"params": {}})
    ctx["pdb"] = form
    run(
        ctx,
        [
            {
                "name": "interface_alanine_scan",
                "inputs": ["pdb"],
                "params": {
                    "output": "scan",
                    "binder_chains": "A,B",
                    "target_chains": "L,M",
                    "max_residues": 2,
                },
            }
        ],
    )
    result = ctx["scan"]
    assert result.data.shape[0] == 2
    assert result.data.shape[1] == 3
    deltas = result.data[:, 2].astype(float)
    assert any(abs(value) > 1e-6 for value in deltas)
    assert result.info["wt_delta_kj"] == pytest.approx(float(result.data[0, 0]), rel=1e-5)
