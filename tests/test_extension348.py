"""foldseek_cluster: collection, aggregation and runner contract."""

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.foldseek_cluster import cluster_rows, collect_structures


def test_collect_structures(tmp_path):
    (tmp_path / "a.pdb").write_text("END\n")
    (tmp_path / "b.pdb").write_text("END\n")
    (tmp_path / "notes.txt").write_text("x")
    found = collect_structures(str(tmp_path))
    assert [path.name for path in found] == ["a.pdb", "b.pdb"]
    with pytest.raises(StepError, match="at least two structures"):
        collect_structures("", str(tmp_path / "a.pdb"))
    with pytest.raises(StepError, match="is not a directory"):
        collect_structures(str(tmp_path / "missing"))


def test_cluster_rows_aggregates():
    pairs = [("0000_A.pdb", "0000_A.pdb"), ("0000_A.pdb", "0001_B.pdb"), ("0002_L.pdb", "0003_M.pdb")]
    order, data, info = cluster_rows(pairs)
    assert order == ["A.pdb", "L.pdb"]
    assert info["n_clusters"] == 2 and info["n_structures"] == 3
    assert info["cluster_sizes"] == {"A.pdb": 2, "L.pdb": 1}
    assert data.shape == (3, 3)
    assert data[0].tolist() == [1.0, 2.0, 1.0]


def test_run_round_trip(tmp_path):
    source = tmp_path / "structures"
    source.mkdir()
    for name in ("a.pdb", "b.pdb", "c.pdb"):
        (source / name).write_text("END\n")
    script = tmp_path / "foldseek.py"
    script.write_text(
        "#!/usr/bin/env python\n"
        "import pathlib, sys\n"
        "cmd = sys.argv[1]\n"
        "if cmd == 'createtsv':\n"
        "    pathlib.Path(sys.argv[5]).write_text('0000_a.pdb\\t0000_a.pdb\\n0000_a.pdb\\t0001_b.pdb\\n0002_c.pdb\\t0002_c.pdb\\n')\n",
        encoding="utf-8",
    )
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "foldseek_cluster", "params": {"output": "clusters", "structure_dir": str(source), "foldseek_path": str(script)}}])
    result = ctx["clusters"]
    assert result.info["n_clusters"] == 2
    assert result.info["n_structures"] == 3
    assert result.data.shape == (3, 3)


def test_errors(tmp_path):
    ctx = Context(str(tmp_path / "t"), {"params": {}})
    with pytest.raises(StepError, match="no structure file"):
        run(ctx, [{"name": "foldseek_cluster", "params": {"output": "clusters", "structure_dir": str(tmp_path)}}])
    with pytest.raises((StepError, ValueError)):
        run(ctx, [{"name": "foldseek_cluster", "params": {"output": "clusters", "structure_dir": str(tmp_path), "coverage": 2.0}}])
