"""Export-contract regression tests for native file registration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core import FileArtifact
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps import esmfold_predict
from src.task.step.steps._sequence_common import encode_sequences

PDB = (
    "ATOM      1  N   MET A   1      11.104  13.207   2.100  1.00 70.00           N\n"
    "ATOM      2  CA  MET A   1      12.560  13.207   2.100  1.00 70.00           C\n"
    "ATOM      3  C   MET A   1      13.000  14.500   2.100  1.00 70.00           C\n"
    "END\n"
)


class FakeModel:
    def infer_pdb(self, sequence: str) -> str:
        return PDB


def test_esmfold_registers_native_and_export_results(tmp_path, monkeypatch):
    monkeypatch.setattr(esmfold_predict, "_load_model", lambda *args, **kwargs: FakeModel())
    form = encode_sequences(["MKV"], "sequence", "position", "protein")
    ctx = Context(tmp_path / "task", {})
    ctx["sequence"] = form
    try:
        run(
            ctx,
            [
                {
                    "name": "esmfold_predict",
                    "inputs": ["sequence"],
                    "params": {"output": "structure", "num_recycles": 1},
                },
                {
                    "name": "export_results",
                    "inputs": ["structure"],
                    "params": {"format": "pdb", "output": "saved"},
                },
            ],
        )
        out = ctx["saved"]
        assert isinstance(out, FileArtifact)
        assert out.format == "exported_files"
        assert out.info["formats"]["file_1"] == "pdb"
        path = Path(out.files["file_1"])
        assert path.is_file()
        assert path.read_text() == PDB
        assert path.is_relative_to(ctx.out_dir)
        report = json.loads((ctx.out_dir / "steps/01_esmfold_predict.json").read_text())
        assert report["result_files"][0]["format"] == "pdb"
        assert Path(report["result_files"][0]["path"]) == path
        assert report["result_files"][0]["bytes"] == len(PDB.encode())
    finally:
        ctx.finalize()

FAKE_BOLTZ = """#!/usr/bin/env python
import json
import os
import shutil
import sys
from pathlib import Path

args = sys.argv[1:]
out = Path(args[args.index("--out_dir") + 1]) / "pred"
out.mkdir(parents=True, exist_ok=True)
shutil.copy(os.environ["BIOPIPE_TEST_PDB"], out / "prediction.pdb")
(out / "confidence_model_0.json").write_text(json.dumps({
    "confidence_score": 0.8, "ptm": 0.5, "iptm": 0.4, "complex_plddt": 0.7,
    "complex_iplddt": 0.6, "complex_pde": 1.0, "chain_pair_iptm": 0.3,
}))
"""


def test_boltz_registers_native_pdb(tmp_path, monkeypatch):
    model = tmp_path / "model.pdb"
    model.write_text(PDB)
    script = tmp_path / "boltz.py"
    script.write_text(FAKE_BOLTZ)
    monkeypatch.setenv("BIOPIPE_TEST_PDB", str(model))
    ctx = Context(tmp_path / "task", {})
    ctx["sequence"] = encode_sequences(["MKV"], "sequence", "position", "protein")
    try:
        run(
            ctx,
            [
                {
                    "name": "boltz_predict",
                    "inputs": ["sequence"],
                    "params": {
                        "output": "structure",
                        "boltz_path": str(script),
                        "msa_mode": "empty",
                        "use_msa_server": False,
                        "device": "cpu",
                        "sampling_steps": 1,
                        "diffusion_samples": 1,
                        "num_workers": 0,
                        "output_format": "pdb",
                    },
                },
                {
                    "name": "export_results",
                    "inputs": ["structure"],
                    "params": {"format": "pdb", "output": "saved"},
                },
            ],
        )
        out = ctx["saved"]
        assert out.info["formats"]["file_1"] == "pdb"
        assert Path(out.files["file_1"]).read_text() == PDB
    finally:
        ctx.finalize()


def test_ligand_pdbqt_registers_native(tmp_path):
    pytest.importorskip("rdkit")
    ctx = Context(tmp_path / "task", {})
    try:
        run(
            ctx,
            [
                {
                    "name": "ligand_pdbqt_prepare",
                    "inputs": [],
                    "params": {"smiles": "CCO", "output": "ligand"},
                },
                {
                    "name": "export_results",
                    "inputs": ["ligand"],
                    "params": {"format": "native", "output": "saved"},
                },
            ],
        )
        out = ctx["saved"]
        assert out.info["formats"]["file_1"] == "pdbqt"
        assert "ROOT" in Path(out.files["file_1"]).read_text()
    finally:
        ctx.finalize()


def test_export_results_fasta_from_sequence_form(tmp_path):
    ctx = Context(tmp_path / "task", {})
    ctx["seq"] = encode_sequences(["MKV", "AC"], "sequence", "position", "protein")
    try:
        run(
            ctx,
            [
                {
                    "name": "export_results",
                    "inputs": ["seq"],
                    "params": {"format": "fasta", "output": "saved"},
                }
            ],
        )
        out = ctx["saved"]
        assert out.info["formats"]["data"] == "fasta"
        content = Path(out.files["data"]).read_text()
        assert "MKV" in content and "AC" in content
    finally:
        ctx.finalize()
