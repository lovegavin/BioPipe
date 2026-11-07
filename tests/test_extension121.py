"""ProteinMPNN score-only operator (v1.21.0)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from src.core import StepError
from src.task.step.steps.proteinmpnn_score import (
    ProteinmpnnScoreStep,
    parse_fasta,
    score_files,
    summarize,
)

FAKE_RUNNER = '''
import argparse
import json
import os
import pathlib
import sys

import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("--pdb_path", required=True)
parser.add_argument("--path_to_fasta", required=True)
parser.add_argument("--out_folder", required=True)
parser.add_argument("--score_only", type=int, default=0)
parser.add_argument("--seed", type=int, default=0)
parser.add_argument("--path_to_model_weights", default="")
parser.add_argument("--model_name", default="")
parser.add_argument("--suppress_print", type=int, default=0)
parser.add_argument("--pdb_path_chains", default="")
args = parser.parse_args()

out = pathlib.Path(args.out_folder)
out.mkdir(parents=True, exist_ok=True)
capture = {
    "argv": sys.argv[1:],
    "pdb": args.pdb_path,
    "fasta": args.path_to_fasta,
    "score_only": args.score_only,
    "seed": args.seed,
    "model_name": args.model_name,
    "chains": args.pdb_path_chains,
    "weights": args.path_to_model_weights,
    "cwd": str(pathlib.Path.cwd()),
    "cuda": os.environ.get("CUDA_VISIBLE_DEVICES", "<unset>"),
}
(out / "captured.json").write_text(json.dumps(capture))
log = os.environ.get("FAKE_MPNN_LOG")
if log:
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(capture) + "\\n")

records = []
name, chunks = None, []
for line in open(args.path_to_fasta, encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    if line.startswith(">"):
        if name is not None:
            records.append((name, "".join(chunks)))
        name, chunks = line[1:].strip(), []
    else:
        chunks.append(line.replace("/", ""))
if name is not None:
    records.append((name, "".join(chunks)))

score_dir = out / "score_only"
score_dir.mkdir(parents=True, exist_ok=True)
stem = pathlib.Path(args.pdb_path).stem
for index, (record_name, sequence) in enumerate(records, start=1):
    np.savez(
        score_dir / f"{stem}_fasta_{index}",
        score=np.array([1.0 + index, 2.0 + index]),
        global_score=np.array([1.5 + index]),
        S=np.zeros(len(sequence)),
        seq_str=sequence,
    )
print("fake runner done")
'''

EMPTY_RUNNER = '''
import sys
sys.exit(0)
'''

FAILING_RUNNER = '''
import sys
sys.stderr.write("model exploded\\n")
sys.exit(3)
'''

PDB = "\n".join([
    "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N",
    "ATOM      2  CA  ALA A   1       1.458   0.000   0.000  1.00  0.00           C",
    "ATOM      3  C   ALA A   1       2.009   1.420   0.000  1.00  0.00           C",
    "ATOM      4  O   ALA A   1       1.252   2.390   0.000  1.00  0.00           O",
    "ATOM      5  N   SER A   2       3.330   1.550   0.000  1.00  0.00           N",
    "ATOM      6  CA  SER A   2       3.980   2.860   0.000  1.00  0.00           C",
    "ATOM      7  C   SER A   2       5.490   2.760   0.000  1.00  0.00           C",
    "ATOM      8  O   SER A   2       6.150   3.790   0.000  1.00  0.00           O",
    "END",
]) + "\n"

FASTA = ">native\nAS\n>scrambled\nSA\n"


def _repo(tmp_path, body=FAKE_RUNNER, model="v_48_020"):
    repo = tmp_path / "ProteinMPNN"
    repo.mkdir()
    (repo / "protein_mpnn_run.py").write_text(body)
    weights = repo / "vanilla_model_weights"
    weights.mkdir()
    (weights / f"{model}.pt").write_bytes(b"weights")
    return repo


def _inputs(tmp_path):
    structure = tmp_path / "mini.pdb"
    structure.write_text(PDB)
    fasta = tmp_path / "seqs.fasta"
    fasta.write_text(FASTA)
    return structure, fasta


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(tmp_path, repo, **params):
    structure, fasta = _inputs(tmp_path)
    step = ProteinmpnnScoreStep()
    ctx = Ctx({
        "structure_path": str(structure),
        "fasta_path": str(fasta),
        "proteinmpnn_path": str(repo),
        **params,
    })
    step.run(ctx, [])
    return ctx["out"], step.export(ctx)


def test_score_output_values(tmp_path):
    repo = _repo(tmp_path)
    out, export = _run(tmp_path, repo)
    assert out.dims == ["sequence", "statistic"]
    assert list(out.labels["sequence"]) == ["native", "scrambled"]
    assert list(out.labels["statistic"]) == [
        "mean_nll", "global_nll", "nll_std", "n_residues"
    ]
    # Fake score arrays: [2, 3] then [3, 4]; globals 2.5 then 3.5.
    np.testing.assert_allclose(
        out.data,
        [[2.5, 2.5, 0.5, 2.0], [3.5, 3.5, 0.5, 2.0]],
        rtol=1e-6,
    )
    assert export["n_sequences"] == 2
    assert export["mean_nll"] == pytest.approx(3.0)
    assert export["structure_path"].endswith("mini.pdb")
    assert out.info["model_name"] == "v_48_020"
    assert out.info["chains"] == "all"
    assert out.info["device"] == "cpu"


def test_operator_passes_posix_paths_and_cpu_env(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    structure, fasta = _inputs(tmp_path)
    logged = tmp_path / "captured.jsonl"
    monkeypatch.setenv("FAKE_MPNN_LOG", str(logged))
    step = ProteinmpnnScoreStep()
    step.run(
        Ctx({
            "structure_path": str(structure),
            "fasta_path": str(fasta),
            "proteinmpnn_path": str(repo),
            "chains": "A",
            "seed": 11,
        }),
        [],
    )
    captured = json.loads(logged.read_text().splitlines()[-1])
    argv = captured["argv"]
    assert argv[argv.index("--score_only") + 1] == "1"
    assert argv[argv.index("--pdb_path") + 1] == structure.as_posix()
    assert "\\" not in argv[argv.index("--pdb_path") + 1]
    assert argv[argv.index("--path_to_fasta") + 1] == fasta.as_posix()
    assert argv[argv.index("--model_name") + 1] == "v_48_020"
    assert argv[argv.index("--seed") + 1] == "11"
    assert argv[argv.index("--pdb_path_chains") + 1] == "A"
    assert argv[argv.index("--path_to_model_weights") + 1] == (
        repo / "vanilla_model_weights"
    ).as_posix()
    assert captured["cwd"] == str(repo)
    assert captured["cuda"] == ""

    out_dir = tmp_path / "manual"
    subprocess.run(
        [
            sys.executable, str(repo / "protein_mpnn_run.py"),
            "--pdb_path", structure.as_posix(),
            "--path_to_fasta", fasta.as_posix(),
            "--out_folder", out_dir.as_posix(),
            "--score_only", "1",
            "--seed", "0",
            "--path_to_model_weights", (repo / "vanilla_model_weights").as_posix(),
            "--model_name", "v_48_020",
            "--suppress_print", "1",
        ],
        env=dict(os.environ, CUDA_VISIBLE_DEVICES=""),
        check=True,
        capture_output=True,
    )
    assert all(path.is_file() for path in score_files(out_dir, structure, 2))
    mean, global_mean, std, length = summarize(score_files(out_dir, structure, 2)[0])
    assert (mean, global_mean, std, length) == pytest.approx((2.5, 2.5, 0.5, 2.0))


def test_parse_fasta_handles_chain_separators(tmp_path):
    path = tmp_path / "multi.fasta"
    path.write_text(">a\nGG/PP\n>b\nCC\n")
    assert parse_fasta(path) == [("a", "GGPP"), ("b", "CC")]


def test_parse_fasta_errors(tmp_path):
    path = tmp_path / "noheader.fasta"
    path.write_text("ACDE\n")
    with pytest.raises(StepError, match="header"):
        parse_fasta(path)
    path.write_text(">a\nACDE\n>a\nFF\n")
    with pytest.raises(StepError, match="unique"):
        parse_fasta(path)
    path.write_text(">empty\n")
    with pytest.raises(StepError, match="is empty"):
        parse_fasta(path)
    path.write_text("")
    with pytest.raises(StepError, match="no records"):
        parse_fasta(path)


def test_parameter_errors(tmp_path):
    repo = _repo(tmp_path)
    structure, fasta = _inputs(tmp_path)
    (tmp_path / "x.cif").write_text("data_x\n")
    step = ProteinmpnnScoreStep()
    base = {
        "structure_path": str(structure),
        "fasta_path": str(fasta),
        "proteinmpnn_path": str(repo),
    }

    def run(**overrides):
        step.run(Ctx({**base, **overrides}), [])

    with pytest.raises(StepError, match="structure_path"):
        run(structure_path=str(tmp_path / "missing.pdb"))
    with pytest.raises(StepError, match="must be a .pdb"):
        run(structure_path=str(tmp_path / "x.cif"))
    with pytest.raises(StepError, match="fasta_path"):
        run(fasta_path=str(tmp_path / "missing.fasta"))
    with pytest.raises(StepError, match="not a directory"):
        run(proteinmpnn_path=str(tmp_path / "nope"))
    empty = tmp_path / "empty_repo"
    empty.mkdir()
    with pytest.raises(StepError, match="does not exist"):
        run(proteinmpnn_path=str(empty))
    weights = repo / "vanilla_model_weights" / "v_48_020.pt"
    weights.unlink()
    with pytest.raises(StepError, match="weights"):
        run()
    weights.write_bytes(b"weights")
    with pytest.raises(StepError, match="model_name"):
        run(model_name="v_99_999")
    with pytest.raises(StepError, match="device"):
        run(device="tpu")


def test_runner_failure_is_reported(tmp_path):
    repo = _repo(tmp_path, body=FAILING_RUNNER)
    with pytest.raises(StepError, match="exit code 3"):
        _run(tmp_path, repo)


def test_missing_score_file_is_reported(tmp_path):
    repo = _repo(tmp_path, body=EMPTY_RUNNER)
    with pytest.raises(StepError, match="no score file"):
        _run(tmp_path, repo)


REAL_REPO = Path(
    os.environ.get("OPERON_PROTEINMPNN_PATH", "/home/gavin/tools/ProteinMPNN")
)
HAS_REAL = (REAL_REPO / "protein_mpnn_run.py").is_file() and (
    REAL_REPO / "vanilla_model_weights" / "v_48_020.pt"
).is_file()


@pytest.mark.skipif(not HAS_REAL, reason="official ProteinMPNN checkout not available")
def test_official_runner_matches_manual_score(tmp_path):
    structure, fasta = _inputs(tmp_path)
    out_dir = tmp_path / "manual"
    subprocess.run(
        [
            sys.executable, str(REAL_REPO / "protein_mpnn_run.py"),
            "--pdb_path", structure.as_posix(),
            "--path_to_fasta", fasta.as_posix(),
            "--out_folder", out_dir.as_posix(),
            "--score_only", "1",
            "--seed", "1",
            "--path_to_model_weights", (REAL_REPO / "vanilla_model_weights").as_posix(),
            "--model_name", "v_48_020",
            "--suppress_print", "1",
        ],
        env=dict(os.environ, CUDA_VISIBLE_DEVICES=""),
        check=True,
        capture_output=True,
    )
    manual = [summarize(path) for path in score_files(out_dir, structure, 2)]

    step = ProteinmpnnScoreStep()
    ctx = Ctx({
        "structure_path": str(structure),
        "fasta_path": str(fasta),
        "proteinmpnn_path": str(REAL_REPO),
        "device": "cpu",
        "seed": 1,
    })
    step.run(ctx, [])
    np.testing.assert_allclose(ctx["out"].data, manual, rtol=1e-6, atol=1e-6)
