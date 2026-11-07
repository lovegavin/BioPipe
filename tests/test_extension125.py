"""Tests for proteinmpnn_interface_design."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
import pytest

from src.core import StepError
from src.task.step.steps.proteinmpnn_design import parse_design_fasta
from src.task.step.steps.proteinmpnn_interface_design import (
    ProteinmpnnInterfaceDesignStep,
    parse_bias,
    parse_tied_positions,
)

FAKE_RUNNER = r'''
import json
import os
import sys
from pathlib import Path

argv = sys.argv[1:]
out = Path(argv[argv.index("--out_folder") + 1])
pdb = argv[argv.index("--pdb_path") + 1]
out.joinpath("seqs").mkdir(parents=True, exist_ok=True)
stem = Path(pdb).stem
files = {}
for flag, key in (
    ("--fixed_positions_jsonl", "fixed"),
    ("--bias_AA_jsonl", "bias"),
    ("--tied_positions_jsonl", "tied"),
):
    if flag in argv:
        files[key] = json.loads(Path(argv[argv.index(flag) + 1]).read_text())
captured = {
    "argv": argv,
    "cwd": os.getcwd(),
    "cuda": os.environ.get("CUDA_VISIBLE_DEVICES"),
    "files": files,
}
Path.cwd().joinpath("captured.json").write_text(json.dumps(captured))
lines = [">" + stem + ", score=1.0, global_score=1.1, seq_recovery=0.5"]
count = int(argv[argv.index("--num_seq_per_target") + 1])
for index in range(count):
    lines.append(
        ">T=0.1, sample=%d, score=%s, global_score=%s, seq_recovery=%s"
        % (index + 1, 1.0 + index, 1.1 + index, 0.5)
    )
    lines.append("SG")
out.joinpath("seqs", stem + ".fa").write_text("\n".join(lines) + "\n")
'''


def _atom(serial, name, resname, chain, number, x, y, z, element):
    return (
        "ATOM  " + str(serial).rjust(5) + " " + name[:4].ljust(4) + " "
        + resname[:3].rjust(3) + " " + chain + str(number).rjust(4) + "    "
        + ("%.3f" % x).rjust(8) + ("%.3f" % y).rjust(8) + ("%.3f" % z).rjust(8)
        + "  1.00  0.00".rjust(16) + element.rjust(2)
    )


def _complex_pdb():
    rows = [
        _atom(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0, "C"),
        _atom(2, "CA", "GLY", "A", 2, 3.8, 0.0, 0.0, "C"),
        _atom(3, "CA", "SER", "B", 1, 0.0, 4.0, 0.0, "C"),
        _atom(4, "CA", "THR", "B", 2, 3.8, 4.0, 0.0, "C"),
    ]
    return "\n".join(rows) + "\nEND\n"


_BACKBONE = [
    ("N", -1.20, 0.00, 0.00, "N"),
    ("CA", 0.00, 0.00, 0.00, "C"),
    ("C", 1.20, 0.50, 0.00, "C"),
    ("O", 1.50, 1.50, 0.00, "O"),
]


def _backbone_pdb(per_chain=6):
    rows = []
    serial = 1
    for index, chain in enumerate("AB"):
        for residue in range(per_chain):
            base_x = 3.8 * residue
            base_y = 4.0 * index
            for name, dx, dy, dz, element in _BACKBONE:
                rows.append(
                    "ATOM  " + str(serial).rjust(5) + "  " + name[:4].ljust(4)
                    + "ALA " + chain + str(residue + 1).rjust(4) + "    "
                    + ("%.3f" % (base_x + dx)).rjust(8)
                    + ("%.3f" % (base_y + dy)).rjust(8)
                    + ("%.3f" % dz).rjust(8)
                    + "  1.00  0.00          " + element.rjust(2)
                )
                serial += 1
    return "\n".join(rows) + "\nEND\n"


def _fake_repo(tmp_path):
    repo = tmp_path / "ProteinMPNN"
    (repo / "vanilla_model_weights").mkdir(parents=True)
    (repo / "vanilla_model_weights" / "v_48_020.pt").write_bytes(b"stub")
    (repo / "protein_mpnn_run.py").write_text(FAKE_RUNNER, encoding="utf-8")
    return repo


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(tmp_path, params):
    structure = tmp_path / "complex.pdb"
    if not structure.exists():
        structure.write_text(_complex_pdb())
    repo = _fake_repo(tmp_path)
    step = ProteinmpnnInterfaceDesignStep()
    ctx = Ctx({"structure_path": str(structure), "proteinmpnn_path": str(repo), **params})
    step.run(ctx, [])
    return ctx, step, repo


def test_command_designs_binder_and_fixes_target(tmp_path):
    structure = tmp_path / "complex.pdb"
    structure.write_text(_complex_pdb())
    repo = _fake_repo(tmp_path)
    step = ProteinmpnnInterfaceDesignStep()
    ctx = Ctx({"structure_path": str(structure), "proteinmpnn_path": str(repo), "num_seq_per_target": 2})
    step.run(ctx, [])
    form = ctx["out"]
    record = json.loads((repo / "captured.json").read_text())
    assert "--pdb_path_chains" in record["argv"]
    assert record["argv"][record["argv"].index("--pdb_path_chains") + 1] == "A"
    assert record["argv"][record["argv"].index("--seed") + 1] == "1"
    assert record["argv"][record["argv"].index("--model_name") + 1] == "v_48_020"
    assert record["cwd"] == str(repo)
    assert record["cuda"] == ""
    assert record["files"]["fixed"] == {"complex": {"A": [], "B": [1, 2]}}
    assert form.dims == ["design", "statistic"]
    assert list(form.labels["design"]) == ["design1", "design2"]
    assert form.data.shape == (2, 3)
    np.testing.assert_allclose(form.data[:, 0], [1.0, 2.0])
    assert form.info["binder_chains"] == ["A"]
    assert form.info["target_chains"] == ["B"]
    assert form.info["sequences"] == ["SG", "SG"]
    assert form.info["fixed_positions"] == {"A": [], "B": [1, 2]}


def test_design_ranges_keep_the_rest_of_the_binder_fixed(tmp_path):
    structure = tmp_path / "complex.pdb"
    structure.write_text(_complex_pdb())
    repo = _fake_repo(tmp_path)
    step = ProteinmpnnInterfaceDesignStep()
    ctx = Ctx({
        "structure_path": str(structure),
        "proteinmpnn_path": str(repo),
        "design_ranges": "A:2",
        "num_seq_per_target": 1,
    })
    step.run(ctx, [])
    record = json.loads((repo / "captured.json").read_text())
    assert record["files"]["fixed"] == {"complex": {"A": [1], "B": [1, 2]}}


def test_bias_omit_and_tied_positions(tmp_path):
    structure = tmp_path / "complex.pdb"
    structure.write_text(_complex_pdb())
    repo = _fake_repo(tmp_path)
    step = ProteinmpnnInterfaceDesignStep()
    ctx = Ctx({
        "structure_path": str(structure),
        "proteinmpnn_path": str(repo),
        "bias_aa": "C:-1.0, W:0.5",
        "omit_aa": "C,W",
        "tied_positions": "A:1,B:1;A:2,B:2",
        "num_seq_per_target": 1,
    })
    step.run(ctx, [])
    record = json.loads((repo / "captured.json").read_text())
    assert record["files"]["bias"] == {"C": -1.0, "W": 0.5}
    assert record["argv"][record["argv"].index("--omit_AAs") + 1] == "CW"
    assert record["files"]["tied"] == {
        "complex": {"A": [[1], [2]], "B": [[1], [2]]}
    }
    assert record["argv"][record["argv"].index("--model_name") + 1] == "v_48_020"


def test_error_paths(tmp_path):
    structure = tmp_path / "complex.pdb"
    structure.write_text(_complex_pdb())
    repo = _fake_repo(tmp_path)
    base = {"structure_path": str(structure), "proteinmpnn_path": str(repo)}
    step = ProteinmpnnInterfaceDesignStep()
    with pytest.raises(StepError, match="is not a file"):
        step.run(Ctx({"structure_path": str(tmp_path / "missing.pdb"), "proteinmpnn_path": str(repo)}), [])
    with pytest.raises(StepError, match="not a directory"):
        step.run(Ctx({**base, "proteinmpnn_path": str(tmp_path / "nope")}), [])
    with pytest.raises(StepError, match="cannot be designed and fixed at once"):
        step.run(Ctx({**base, "binder_chains": "A,B", "target_chains": "B"}), [])
    with pytest.raises(StepError, match="not found in complex.pdb"):
        step.run(Ctx({**base, "binder_chains": "Z"}), [])
    with pytest.raises(StepError, match="bias token"):
        step.run(Ctx({**base, "bias_aa": "C"}), [])
    with pytest.raises(StepError, match="at least two positions"):
        step.run(Ctx({**base, "tied_positions": "A:1"}), [])
    with pytest.raises(StepError, match="not residues of chain B"):
        step.run(Ctx({**base, "fixed_positions": "B:99"}), [])
    with pytest.raises(StepError, match="weights"):
        step.run(
            Ctx({**base, "weights_path": str(tmp_path / "no-weights"), "num_seq_per_target": 1}),
            [],
        )
    with pytest.raises(StepError, match="num_seq_per_target"):
        step.run(Ctx({**base, "num_seq_per_target": 0}), [])


def test_parse_bias_and_tied_helpers():
    assert parse_bias("") == {}
    assert parse_bias("A=-1.1;F:0.7") == {"A": -1.1, "F": 0.7}
    with pytest.raises(StepError, match="must name a single amino acid"):
        parse_bias("AA:-1.0")
    with pytest.raises(StepError, match="is not a number"):
        parse_bias("C:abc")
    chains = {"A": [1, 2], "B": [1, 2]}
    assert parse_tied_positions("A:1,B:1", set(chains), chains) == {"A": [[1]], "B": [[1]]}
    assert parse_tied_positions("A:1,A:2", set(chains), chains) == {"A": [[1, 2]]}


@pytest.mark.skipif(
    not Path(os.environ.get("OPERON_PROTEINMPNN_PATH", "/nonexistent")).is_dir(),
    reason="local ProteinMPNN checkout is not configured",
)
def test_official_runner_interface_design(tmp_path):
    structure = tmp_path / "complex.pdb"
    structure.write_text(_backbone_pdb())
    step = ProteinmpnnInterfaceDesignStep()
    ctx = Ctx({
        "structure_path": str(structure),
        "proteinmpnn_path": os.environ["OPERON_PROTEINMPNN_PATH"],
        "num_seq_per_target": 1,
        "device": "cpu",
    })
    step.run(ctx, [])
    form = ctx["out"]
    assert form.data.shape == (1, 3)
    assert np.all(np.isfinite(form.data))

def test_parse_design_fasta_accepts_non_finite_scores(tmp_path):
    fasta = tmp_path / "nan.fa"
    fasta.write_text(
        ">complex, score=nan, global_score=nan, fixed_chains=['B']\nAG\n"
        ">T=0.1, sample=1, score=nan, global_score=nan, seq_recovery=nan\nAG\n",
        encoding="utf-8",
    )
    designs = parse_design_fasta(fasta)
    assert len(designs) == 1
    assert designs[0]["sample"] == 1
    assert math.isnan(float(designs[0]["score"]))
