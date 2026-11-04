"""structure_pocket_detect: fpocket wrapper."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.reader import read_source
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_pocket_detect import parse_info, pocket_residues, run_fpocket

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "vhh_1mel.pdb"

INFO = """Pocket 1 :
\tScore : \t0.467
\tDruggability Score : \t0.002
\tNumber of Alpha Spheres : \t43
\tTotal SASA : \t129.589
\tVolume : \t491.567
\tMean alpha sphere radius :\t3.887
\tHydrophobicity score:\t7.083

Pocket 2 :
\tScore : \t0.302
\tDruggability Score : \t0.000
\tNumber of Alpha Spheres : \t20
\tVolume : \t120.000
\tMean alpha sphere radius :\t3.100
\tHydrophobicity score:\t4.000
"""

POCKET = """ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C
ATOM      2  CA  ALA A   1       1.000   0.000   0.000  1.00  0.00           C
ATOM      3  CA  GLY A   2       2.000   0.000   0.000  1.00  0.00           C
END
"""


def test_parse_info_and_residues(tmp_path):
    pockets = parse_info(INFO)
    assert [pocket["index"] for pocket in pockets] == [1, 2]
    assert pockets[0]["score"] == pytest.approx(0.467)
    assert pockets[0]["druggability"] == pytest.approx(0.002)
    assert pockets[1]["volume"] == pytest.approx(120.0)
    path = tmp_path / "pocket1_atm.pdb"
    path.write_text(POCKET)
    count, cx, cy, cz = pocket_residues(path)
    assert count == 2
    assert cx == pytest.approx(1.0)


def _script(tmp_path):
    script = tmp_path / "fake_fpocket.py"
    script.write_text(
        "#!/usr/bin/env python\n"
        "import sys, pathlib\n"
        "args = sys.argv[1:]\n"
        "pref = pathlib.Path(args[args.index('-o') + 1])\n"
        "out = pref.parent / (pref.name + '_out')\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / (pref.name + '_info.txt')).write_text(" + repr(INFO) + ")\n"
        "(out / 'pockets').mkdir(exist_ok=True)\n"
        "(out / 'pockets' / 'pocket1_atm.pdb').write_text(" + repr(POCKET) + ")\n"
        "(out / 'pockets' / 'pocket2_atm.pdb').write_text(" + repr(POCKET) + ")\n"
    )
    return script


def test_runner_round_trip_with_fake_fpocket(tmp_path):
    pytest.importorskip("openmm") if False else None
    script = _script(tmp_path)
    form = read_source(str(FIXTURE), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    run(ctx, [{"name": "structure_pocket_detect", "inputs": ["pdb"], "params": {"output": "pockets", "fpocket_path": str(script)}}])
    result = ctx["pockets"]
    assert result.dims == ["pocket", "statistic"]
    assert result.data.shape == (2, 9)
    assert result.info["n_detected"] == 2
    assert result.info["best_score"] == pytest.approx(0.467)


def test_filters_and_errors(tmp_path):
    script = _script(tmp_path)
    with pytest.raises(StepError, match="was not found"):
        run_fpocket("ATOM\n", binary=str(tmp_path / "missing"))
    pockets = parse_info(INFO)
    assert [pocket["score"] for pocket in pockets if pocket["score"] >= 0.4] == [0.467]


def test_real_fpocket_when_available(tmp_path):
    binary = "/home/gavin/tools/fpocket/bin/fpocket"
    if not Path(binary).is_file():
        pytest.skip("fpocket is not built on this host")
    form = read_source(str(FIXTURE), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    run(ctx, [{"name": "structure_pocket_detect", "inputs": ["pdb"], "params": {"output": "pockets", "fpocket_path": binary, "max_pockets": 3}}])
    result = ctx["pockets"]
    assert result.data.shape[0] == 3
    assert result.info["n_detected"] >= 5
    assert 0.0 <= result.info["best_score"] <= 1.0
