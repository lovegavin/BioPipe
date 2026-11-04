"""foldseek_align: command construction, parsing and runner contract."""

import sys

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.foldseek_align import foldseek_command, parse_row


FIXTURE = "tests/fixtures/vhh_1mel.pdb"


def test_command_and_parse():
    from pathlib import Path

    command = foldseek_command("foldseek", Path("/tmp/a.pdb"), Path("/tmp/b.pdb"), Path("/tmp/res.m8"), Path("/tmp/work"))
    assert command[1] == "easy-search" and "--format-output" in command
    record = parse_row("a\tb\t0.98\t1.2\t0.9\t0.85\t0.96\t0.97\t120", "a", "b")
    assert record["alntmscore"] == pytest.approx(0.98)
    assert record["rmsd"] == pytest.approx(1.2)
    assert record["alnlen"] == pytest.approx(120)


def test_parse_rejects_empty():
    with pytest.raises(StepError, match="no alignment"):
        parse_row("", "a", "b")
    with pytest.raises(StepError, match="unexpected Foldseek output"):
        parse_row("only\ttwo", "a", "b")


def test_run_round_trip(tmp_path):
    script = tmp_path / "foldseek.py"
    script.write_text(
        "#!/usr/bin/env python\n"
        "import sys\n"
        "open(sys.argv[sys.argv.index('easy-search') + 3], 'w').write('q\\tt\\t0.95\\t1.5\\t0.88\\t0.9\\t0.99\\t1.0\\t130\\n')\n",
        encoding="utf-8",
    )
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "foldseek_align", "params": {"output": "alignment", "query_path": FIXTURE, "target_path": FIXTURE, "foldseek_path": str(script)}}])
    result = ctx["alignment"]
    assert result.data.shape == (1, 7)
    assert result.info["alntmscore"] == pytest.approx(0.95)
    assert result.labels["statistic"]["rmsd"] == 1


def test_errors(tmp_path):
    script = tmp_path / "foldseek.py"
    script.write_text("print('x')\n", encoding="utf-8")
    ctx = Context(str(tmp_path / "t"), {"params": {}})
    with pytest.raises(StepError, match="query_path is required"):
        run(ctx, [{"name": "foldseek_align", "params": {"output": "alignment", "target_path": FIXTURE}}])
    with pytest.raises(StepError, match="is not a file"):
        run(ctx, [{"name": "foldseek_align", "params": {"output": "alignment", "query_path": "/tmp/nope.pdb", "target_path": FIXTURE}}])
    with pytest.raises(StepError, match="was not found"):
        run(ctx, [{"name": "foldseek_align", "params": {"output": "alignment", "query_path": FIXTURE, "target_path": FIXTURE, "foldseek_path": "/tmp/nonexistent-foldseek"}}])
