"""Tests for the RFdiffusion backbone design operator."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.rfdiffusion_design import (
    RfdiffusionDesignStep,
    design_command,
    design_paths,
    parse_contigs,
    stack_designs,
)


def _line(
    serial: int,
    name: str,
    resname: str,
    chain: str,
    number: int,
    x: float,
    y: float,
    z: float,
    element: str,
) -> str:
    return (
        f"ATOM  {serial:5d} {name:<4s}{resname:>3s} {chain}{number:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {element:>2s}\n"
    )


def _pdb_text(offset: float = 0.0) -> str:
    return "".join(
        [
            _line(1, "N", "ALA", "A", 1, 0.0, 0.0, 0.0, "N"),
            _line(2, "CA", "ALA", "A", 1, 1.5 + offset, 0.0, 0.0, "C"),
            _line(3, "C", "ALA", "A", 1, 2.5 + offset, 1.0, 0.0, "C"),
            _line(4, "O", "ALA", "A", 1, 3.2 + offset, 1.0, 0.0, "O"),
        ]
    )


def test_parse_contigs() -> None:
    assert parse_contigs(" A1-100 ") == "A1-100"
    assert parse_contigs("50-80 A1-100,0") == "50-80 A1-100,0"
    with pytest.raises(StepError, match="contigs is required"):
        parse_contigs("   ")
    with pytest.raises(StepError, match="does not accept"):
        parse_contigs("A1-100;B2-5")
    with pytest.raises(StepError, match="no residue range"):
        parse_contigs("A")


def test_design_paths_order(tmp_path) -> None:
    for name in ("design_10.pdb", "design_2.pdb", "design_0.pdb", "notes.pdb"):
        (tmp_path / name).write_text(_pdb_text(), encoding="utf-8")
    paths = design_paths(tmp_path)
    assert [path.name for path in paths] == ["design_0.pdb", "design_2.pdb", "design_10.pdb"]


def test_design_command(tmp_path) -> None:
    runner = Path("/repo/run_inference.py")
    outdir = tmp_path / "out"
    params = {
        "contigs": "A1-50",
        "num_designs": 3,
        "device": "cpu",
        "python_executable": "python3",
    }
    command = design_command(params, runner, None, outdir)
    assert command[0] == "python3"
    assert command[1] == str(runner)
    assert "inference.num_designs=3" in command
    assert "contigmap.contigs=[A1-50]" in command
    assert "inference.device=cpu" in command
    assert not any(token.startswith("inference.input_pdb=") for token in command)

    with_structure = design_command(params, runner, Path("/data/in.pdb"), outdir)
    assert "inference.input_pdb=/data/in.pdb" in with_structure


def test_stack_designs(tmp_path) -> None:
    first = tmp_path / "design_0.pdb"
    second = tmp_path / "design_1.pdb"
    first.write_text(_pdb_text(), encoding="utf-8")
    second.write_text(_pdb_text(offset=5.0), encoding="utf-8")
    data, labels, extra = stack_designs([first, second])
    assert data.shape == (2, 4, 12)
    assert data[1, 1, 0] == pytest.approx(6.5)
    assert labels["design"] == {"design1": 0, "design2": 1}
    assert labels["atom"]["atom2"] == 1
    assert extra["designs"][0]["n_atoms"] == 4
    assert extra["n_atoms"] == 4


def _fake_repo(tmp_path: Path, *, fail: bool = False, empty: bool = False) -> Path:
    repo = tmp_path / "rf"
    (repo / "scripts").mkdir(parents=True)
    (repo / "models").mkdir(parents=True)
    (repo / "models" / "Complex_beta_ckpt.pt").write_bytes(b"stub")
    runner = repo / "scripts" / "run_inference.py"
    body = [
        "import pathlib, sys",
        f"TEXT = {_pdb_text()!r}",
        "prefix = None",
        "for arg in sys.argv[1:]:",
        "    if arg.startswith('inference.output_prefix='):",
        "        prefix = pathlib.Path(arg.split('=', 1)[1])",
        "if prefix is None:",
        "    raise SystemExit(2)",
    ]
    if fail:
        body.append("raise SystemExit(3)")
    elif empty:
        body.append("prefix.parent.mkdir(parents=True, exist_ok=True)")
    else:
        body.extend(
            [
                "prefix.parent.mkdir(parents=True, exist_ok=True)",
                "for index in range(2):",
                "    (prefix.parent / f'design_{index}.pdb').write_text(TEXT)",
            ]
        )
    runner.write_text("\n".join(body) + "\n", encoding="utf-8")
    return repo


def _params(repo: Path, **overrides) -> dict:
    params = {
        "output": "designs",
        "rfdiffusion_path": str(repo),
        "python_executable": sys.executable,
        "contigs": "50-60",
        "num_designs": 2,
        "device": "cpu",
    }
    params.update(overrides)
    return params


def test_run(tmp_path) -> None:
    repo = _fake_repo(tmp_path)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "rfdiffusion_design", "inputs": [], "params": _params(repo)}])
    form = ctx["designs"]
    assert form.dims == ["design", "atom", "field"]
    assert form.data.shape == (2, 4, 12)
    assert form.info["n_designs"] == 2
    # The tool's temporary directory is gone; preserved PDBs must remain usable.
    from src.task.step.steps.export_results import ExportResultsStep
    files = ctx.artifacts['native_results']['designs']['files']
    assert len(files) == 2
    assert all(Path(item['path']).read_text() == _pdb_text() for item in files)
    ctx.step_params = {'output': 'saved', 'format': 'pdb', '_input_names': ['designs']}
    ExportResultsStep().run(ctx, [form])
    assert set(ctx['saved'].files.values()) == {item['path'] for item in files}
    assert len(ctx['saved'].info['reused_roles']) == 2
    ctx.finalize()


def test_run_errors(tmp_path) -> None:
    repo = _fake_repo(tmp_path)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    with pytest.raises(StepError, match="is not a file"):
        run(
            ctx,
            [
                {
                    "name": "rfdiffusion_design",
                    "inputs": [],
                    "params": _params(repo, structure_path=str(tmp_path / "nope.pdb")),
                }
            ],
        )

    failing = _fake_repo(tmp_path / "failing", fail=True)
    with pytest.raises(StepError, match="failed with exit code 3"):
        run(ctx, [{"name": "rfdiffusion_design", "inputs": [], "params": _params(failing)}])

    empty = _fake_repo(tmp_path / "empty", empty=True)
    with pytest.raises(StepError, match="produced no PDB"):
        run(ctx, [{"name": "rfdiffusion_design", "inputs": [], "params": _params(empty)}])

    bare = tmp_path / "bare"
    (bare / "models").mkdir(parents=True)
    (bare / "models" / "Complex_beta_ckpt.pt").write_bytes(b"stub")
    with pytest.raises(StepError, match="is partial"):
        run(ctx, [{"name": "rfdiffusion_design", "inputs": [], "params": _params(bare)}])


def test_definition() -> None:
    assert RfdiffusionDesignStep.definition["inputs_arity"] == 0
    assert RfdiffusionDesignStep.definition["icon"] == "ShareNetwork"
