"""structure_interface_residue_energy: pairwise decomposition and identity."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_interface_residue_energy import COULOMB, pair_energy

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
OPENMM = __import__("importlib").util.find_spec("openmm") is not None
FIXER = __import__("importlib").util.find_spec("pdbfixer") is not None


def test_pair_energy_analytic():
    coulomb, lj = pair_energy(1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.5)
    assert coulomb == pytest.approx(-COULOMB / 0.5, rel=1e-12)
    assert lj == 0.0
    coulomb, lj = pair_energy(0.0, 0.0, 0.3, 0.3, 1.0, 1.0, 0.3 * 2 ** (1.0 / 6.0))
    assert coulomb == 0.0
    assert lj == pytest.approx(-1.0, rel=1e-9)
    with pytest.raises(StepError, match="distance is zero"):
        pair_energy(1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0)


@pytest.mark.skipif(not (OPENMM and FIXER), reason="openmm and pdbfixer are required")
def test_real_interface_identity():
    from src.task.step.steps.structure_interface_residue_energy import interaction_arrays, prepare_structure

    data = prepare_structure(FIXTURES / "vhh_1mel.pdb")
    side_a = np.array([index for index, chain in enumerate(data["chains"]) if chain in "AB"], dtype=int)
    side_b = np.array([index for index, chain in enumerate(data["chains"]) if chain in "LM"], dtype=int)
    coulomb, lj, mask, distance = interaction_arrays(data, side_a, side_b)
    assert mask.sum() > 1000
    assert np.isfinite(coulomb.sum()) and np.isfinite(lj.sum())


@pytest.mark.skipif(not (OPENMM and FIXER), reason="openmm and pdbfixer are required")
def test_run_round_trip(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "structure_interface_residue_energy", "params": {"structure_path": str(FIXTURES / "vhh_1mel.pdb"), "binder_chains": "AB", "target_chains": "LM"}}])
    result = ctx["energies"]
    assert result.dims == ["residue", "statistic"]
    assert result.info["n_contacts"] > 0
    assert result.info["decomposed_total_kj"] == pytest.approx(result.info["total_interaction_kj"], rel=1e-5, abs=1e-2)
