"""structure_anm_modes: anisotropic network model."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_anm_modes import anm_hessian, anm_msf, ca_atoms
from src.reader import read_source

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def test_hessian_rank_and_invariance():
    coords = np.array([[0.0, 0.0, 0.0], [4.0, 0.0, 0.0], [0.0, 4.0, 0.0]])
    hessian = anm_hessian(coords, 6.0, 1.0)
    eigenvalues = np.linalg.eigvalsh(hessian)
    assert np.sum(eigenvalues > 1e-8) == 3
    msf, slowest, collectivity = anm_msf(hessian, 3)
    assert msf.shape == (3,)
    assert np.all(msf > 0)
    rotated = coords @ np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]])
    msf2, _, _ = anm_msf(anm_hessian(rotated, 6.0, 1.0), 3)
    assert np.allclose(msf, msf2, rtol=1e-9, atol=1e-9)
    assert 0.0 < collectivity <= 1.0


def test_prody_anm_oracle():
    prody = pytest.importorskip("prody")
    form = read_source(str(FIXTURES / "vhh_1mel.pdb"), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    labels, coords = ca_atoms(form, "atom", "field", "A")
    hessian = anm_hessian(coords, 15.0, 1.0)
    msf, _, _ = anm_msf(hessian, 20)
    import tempfile

    path = Path(tempfile.mkdtemp()) / "chain.pdb"
    head = "ATOM  {serial:5d}  CA  ALA A{number:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C\n"
    path.write_text("".join(head.format(serial=i + 1, number=i + 2, x=coord[0], y=coord[1], z=coord[2]) for i, coord in enumerate(coords)))
    atoms = prody.parsePDB(str(path))
    model = prody.ANM("chain")
    model.buildHessian(atoms, cutoff=15.0, gamma=1.0)
    model.calcModes(n_modes=20)
    vectors = model.getEigvecs()
    values = model.getEigvals()
    expected = ((vectors ** 2) / values).sum(axis=1).reshape(-1, 3).sum(axis=1)
    assert np.allclose(msf, expected, rtol=1e-4, atol=1e-5)


def test_run(tmp_path):
    form = read_source(str(FIXTURES / "vhh_1mel.pdb"), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    run(ctx, [{"name": "structure_anm_modes", "inputs": ["pdb"], "params": {"output": "modes", "chain": "A", "n_modes": 10}}])
    result = ctx["modes"]
    assert result.data.shape == (132, 2)
    assert result.info["n_residues"] == 132
    assert len(result.info["slowest_eigenvalues"]) == 10
    with pytest.raises((StepError, ValueError)):
        run(ctx, [{"name": "structure_anm_modes", "inputs": ["pdb"], "params": {"output": "modes", "n_modes": 0}}])
