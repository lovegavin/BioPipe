"""Runner-level contract checks for the v1.26.0 operators."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.core.forms.form import Form
from src.reader import pick_reader
from src.task.context.base import Context
from src.task.runner import run

VHH = (
    "DVQLQASGGGSVQAGGSLRLSCAASGYTIGPYCMGWFRQAPGKEREGVAAINMGGGITYYADSVKGRFTISQDNAKNTVYLLMNSLEPEDTAIYYCAADSTIYASYYECGHGLSTGGYGYDSWGQGTQVTVSS"
)


def _atom(serial: int, name: str, resname: str, chain: str, number: int, x: float, y: float, z: float) -> str:
    return (
        f"ATOM  {serial:5d} {name:4s} {resname:3s} {chain:1s}{number:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.0:6.2f}{0.0:6.2f}          {name[0]:2s}"
    )


def _two_chain_form(tmp_path: Path) -> Form:
    lines = [
        _atom(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
        _atom(2, "CA", "LEU", "A", 2, 20.0, 0.0, 0.0),
        _atom(3, "CA", "SER", "B", 1, 0.0, 0.0, 4.0),
        _atom(4, "CA", "SER", "B", 2, 23.0, 0.0, 1.0),
    ]
    path = tmp_path / "two_chain.pdb"
    path.write_text("\n".join(lines) + "\nEND\n", encoding="utf-8")
    return pick_reader(path).implementation().read(
        path, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"}
    )


def _sequence_form() -> Form:
    from src.task.step.steps._sequence_common import encode_sequences

    return encode_sequences([VHH], "sequence", "position", "protein")


def test_interface_hydrophobic_patch_through_runner(tmp_path) -> None:
    work = Path(tempfile.mkdtemp(prefix="biopipe-patch-"))
    ctx = Context(work, {"params": {}})
    ctx["structure"] = _two_chain_form(tmp_path)
    run(
        ctx,
        [
            {
                "name": "interface_hydrophobic_patch",
                "inputs": ["structure"],
                "params": {"output": "patches", "binder_chains": "A", "cutoff": 4.5},
            }
        ],
    )
    assert ctx["patches"].data.shape == (2, 5)
    assert (work / "output" / "steps" / "01_interface_hydrophobic_patch.json").is_file()


def test_cdr_hydrophobicity_through_runner() -> None:
    work = Path(tempfile.mkdtemp(prefix="biopipe-cdr-"))
    ctx = Context(work, {"params": {}})
    ctx["vhh"] = _sequence_form()
    run(
        ctx,
        [
            {
                "name": "antibody_cdr_hydrophobicity",
                "inputs": ["vhh"],
                "params": {"output": "hydrophobicity"},
            }
        ],
    )
    assert ctx["hydrophobicity"].data.shape == (3, 5)


def test_rdkit_operators_through_runner() -> None:
    work = Path(tempfile.mkdtemp(prefix="biopipe-rdkit126-"))
    ctx = Context(work, {"params": {}})
    run(
        ctx,
        [
            {
                "name": "rdkit_esol",
                "inputs": [],
                "params": {"output": "solubility", "smiles": "CCO\nc1ccccc1"},
            },
            {
                "name": "rdkit_smarts_matches",
                "inputs": [],
                "params": {"output": "matches", "smiles": "CCO\nc1ccccc1", "smarts": "[OH]\nc1ccccc1"},
            },
        ],
    )
    assert ctx["solubility"].data.shape == (2, 8)
    assert ctx["matches"].data.shape == (2, 2)


def test_esm_if_mutation_scan_through_runner() -> None:
    pytest.importorskip("torch")
    pytest.importorskip("esm")
    pytest.importorskip("biotite")
    pytest.importorskip("torch_scatter")
    checkpoint = Path("/home/gavin/models/esm_if1_gvp4_t16_142M_UR50.pt")
    if not checkpoint.is_file():
        pytest.skip("ESM-IF checkpoint is not available")
    fixture = Path(__file__).parent / "fixtures" / "backbone_1bc8_c60_75.pdb"
    form = pick_reader(fixture).implementation().read(
        fixture, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"}
    )
    work = Path(tempfile.mkdtemp(prefix="biopipe-mutscan-"))
    ctx = Context(work, {"params": {}})
    ctx["structure"] = form
    run(
        ctx,
        [
            {
                "name": "esm_if_mutation_scan",
                "inputs": ["structure"],
                "params": {
                    "output": "mutations",
                    "chain": "C",
                    "model_path": str(checkpoint),
                    "positions": "3",
                },
            }
        ],
    )
    assert ctx["mutations"].data.shape == (19, 4)
