"""structure_protonation_sites: pKa shifts and charge fractions."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_protonation_sites import (
    pka_shift,
    protonation_fraction,
    titratable_rows,
)


def test_fraction_and_shift():
    assert protonation_fraction(3.9, 7.4, acidic=True) > 0.99
    assert protonation_fraction(6.0, 7.4, acidic=False) < 0.05
    assert pka_shift("HIS", []) == 6.0
    assert pka_shift("HIS", ["ASP"]) == pytest.approx(5.6)
    assert pka_shift("ASP", ["LYS"]) == pytest.approx(4.3)


def test_titratable_rows_hand_case():
    groups = [
        {"label": "A:HIS:10", "residue": "HIS", "coords": np.zeros(3)},
        {"label": "A:ASP:11", "residue": "ASP", "coords": np.array([3.0, 0.0, 0.0])},
        {"label": "A:ALA:12", "residue": "ALA", "coords": np.array([30.0, 0.0, 0.0])},
    ]
    rows = titratable_rows(groups, ph=7.4)
    assert [r["label"] for r in rows] == ["A:HIS:10", "A:ASP:11"]
    assert rows[0]["pka"] == pytest.approx(5.6)
    assert rows[1]["pka"] == pytest.approx(4.3)


def test_run_on_fixture(tmp_path):
    from src.reader import read_source

    fixture = Path(__file__).parent / "fixtures" / "vhh_1mel.pdb"
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = read_source(str(fixture), dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"})
    run(ctx, [{"name": "structure_protonation_sites", "inputs": ["pdb"], "params": {"output": "sites", "ph": 7.4}}])
    result = ctx["sites"]
    assert result.info["n_sites"] > 20
    assert "net_charge" in result.info


def test_errors():
    with pytest.raises(StepError, match="no titratable residue"):
        titratable_rows([{"label": "A:ALA:1", "residue": "ALA", "coords": np.zeros(3)}], ph=7.0)
