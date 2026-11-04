"""structure_gnm_flexibility: Kirchhoff matrix and mean-square fluctuations."""

from pathlib import Path

import numpy as np
import pytest

from src.core.forms import Form
from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_gnm_flexibility import ca_atoms, gnm_msf, kirchhoff
from src.reader import read_source

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _tiny_form(tmp_path, count=2):
    head = "ATOM  {serial:5d}  CA  ALA A{number:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C\n"
    text = "".join(head.format(serial=i + 1, number=i + 2, x=float(i) * 3.8, y=0.0, z=0.0) for i in range(count))
    path = tmp_path / "tiny.pdb"
    path.write_text(text)
    return read_source(str(path), ["atom", "field"], {"atom": "auto", "field": "builtin"})


def test_ca_atoms_and_rotation_invariance(tmp_path):
    form = read_source(str(FIXTURES / "vhh_1mel.pdb"), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    labels, coords = ca_atoms(form, "atom", "field", "A")
    assert len(labels) == len(coords) == 132
    matrix = kirchhoff(coords, 1.0, 10.0)
    msf, first, collectivity = gnm_msf(matrix)
    rotated = coords @ np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    msf2, _, _ = gnm_msf(kirchhoff(rotated, 1.0, 10.0))
    assert np.allclose(msf, msf2, rtol=1e-9, atol=1e-9)
    assert 0.0 < collectivity <= 1.0
    assert msf.min() > 0


def test_prody_oracle(tmp_path):
    prody = pytest.importorskip("prody")
    form = read_source(str(FIXTURES / "vhh_1mel.pdb"), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    labels, coords = ca_atoms(form, "atom", "field", "A")
    msf, _, _ = gnm_msf(kirchhoff(coords, 1.0, 10.0))
    import tempfile

    path = Path(tempfile.mkdtemp()) / "chain.pdb"
    head = "ATOM  {serial:5d}  CA  ALA A{number:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C\n"
    text = "".join(head.format(serial=i + 1, number=i + 2, x=coord[0], y=coord[1], z=coord[2]) for i, coord in enumerate(coords))
    path.write_text(text)
    atoms = prody.parsePDB(str(path))
    model = prody.GNM("chain")
    model.buildKirchhoff(atoms, cutoff=10.0, gamma=1.0)
    model.calcModes(None)
    vectors = model.getEigvecs()
    values = model.getEigvals()
    expected = ((vectors ** 2) / values).sum(axis=1)
    assert np.allclose(msf, expected, rtol=1e-5, atol=1e-6)


def test_run_and_errors(tmp_path):
    form = read_source(str(FIXTURES / "vhh_1mel.pdb"), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    run(ctx, [{"name": "structure_gnm_flexibility", "inputs": ["pdb"], "params": {"output": "flex", "chain": "A"}}])
    result = ctx["flex"]
    assert result.dims == ["residue", "statistic"]
    assert result.data.shape == (132, 3)
    assert result.info["n_residues"] == 132
    assert abs(float(result.data[:, 1].mean()) - 1.0) < 1e-4
    with pytest.raises(StepError, match="at least three CA"):
        ca_atoms(_tiny_form(tmp_path, 2), "atom", "field")
    with pytest.raises(StepError, match="cutoff must be positive"):
        kirchhoff(np.zeros((3, 3)), 1.0, 0.0)
