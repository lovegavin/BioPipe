"""Tests for the antibody CDR-fixed framework redesign operator."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.errors import StepError
from src.task.step.steps.antibody_cdr_redesign import (
    AntibodyCdrRedesignStep,
    cdr_positions,
    chain_sequence,
    fixed_payload,
)

FIXTURE = Path(__file__).parent / "fixtures" / "vhh_1mel.pdb"
REAL_REPO = Path("/home/gavin/tools/ProteinMPNN")

FAKE_RUNNER = r'''
import json
import sys
from pathlib import Path

args = sys.argv[1:]
def value(flag, default=""):
    return args[args.index(flag) + 1] if flag in args else default

pdb = Path(value("--pdb_path"))
out = Path(value("--out_folder"))
fixed_path = value("--fixed_positions_jsonl")
fixed = json.loads(Path(fixed_path).read_text()) if fixed_path else {}
stem = fixed[next(iter(fixed))] if fixed else {}

letters = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q",
    "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K",
    "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
    "TYR": "Y", "VAL": "V",
}
seen = []
for line in pdb.read_text().splitlines():
    if not line.startswith("ATOM  ") or line[21:22] != "A":
        continue
    key = (int(line[22:26]), line[26:27])
    if key in seen:
        continue
    seen.append(key)

chain = []
numbers = []
seen = []
for line in pdb.read_text().splitlines():
    if not line.startswith("ATOM  ") or line[21:22] != "A":
        continue
    key = (int(line[22:26]), line[26:27])
    if key in seen:
        continue
    seen.append(key)
    numbers.append(key[0])
    chain.append(letters[line[17:20].strip()])

mutation = value("--mutation")
designed = list(chain)
if mutation:
    position = int(mutation) - 1
    designed[position] = "W"
sequence = "".join(designed)

count = int(value("--num_seq_per_target", "2"))
lines = []
for index in range(1, count + 1):
    lines.append(
        ">T=0.1, sample=" + str(index) + ", score=1." + str(index)
        + ", global_score=1." + str(index) + ", seq_recovery=0.5"
    )
    lines.append(sequence)
seqs = out / "seqs"
seqs.mkdir(parents=True, exist_ok=True)
(seqs / (pdb.stem + ".fa")).write_text("\n".join(lines) + "\n")
'''


def _repo(tmp_path: Path, mutation: str = "") -> Path:
    repo = tmp_path / "ProteinMPNN"
    (repo / "vanilla_model_weights").mkdir(parents=True)
    (repo / "vanilla_model_weights" / "v_48_020.pt").write_bytes(b"x")
    script = repo / "protein_mpnn_run.py"
    script.write_text(FAKE_RUNNER)
    if mutation:
        script.write_text(FAKE_RUNNER.replace('mutation = value("--mutation")', 'mutation = value("--mutation")'))
    return repo


def _params(repo: Path, **overrides):
    params = {
        "structure_path": str(FIXTURE),
        "proteinmpnn_path": str(repo),
        "num_seq_per_target": 2,
        "seed": 1,
        "device": "cpu",
        "output": "designs",
    }
    params.update(overrides)
    return params


class Ctx(dict):
    def __init__(self, params):
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(step, params):
    ctx = Ctx(params)
    step.run(ctx, [])
    return ctx[ctx.step_params["output"]], step.export(ctx)


def test_chain_sequence_and_cdrs():
    sequence, numbers = chain_sequence(FIXTURE, "A")
    text = "".join(sequence)
    assert len(text) == 132
    assert text.startswith("VQLQASGGGSVQAGGSLRLSCAASGYTIG")
    assert numbers[0] == 2 and numbers[-1] == 133
    residues, positions = cdr_positions(text)
    assert residues == [
        "PYCMG",
        "AINMGGGITYYADSVKG",
        "DSTIYASYYECGHGLSTGGYGYDS",
    ]
    assert positions[:5] == [30, 31, 32, 33, 34]
    assert len(positions) == 46


def test_fixed_payload_covers_all_chains():
    sequence, numbers = chain_sequence(FIXTURE, "A")
    _, positions = cdr_positions("".join(sequence))
    payload = fixed_payload(FIXTURE, "A", positions, numbers)
    assert list(payload) == ["vhh_1mel"]
    chains = payload["vhh_1mel"]
    assert set(chains) == {"A", "B", "L", "M"}
    assert chains["B"] and chains["L"] and chains["M"]
    assert chains["A"][:5] == [30, 31, 32, 33, 34]
    assert 99 in chains["A"]
    assert 1 not in chains["A"]


def test_step_keeps_cdrs(tmp_path):
    repo = _repo(tmp_path)
    step = AntibodyCdrRedesignStep()
    form, export = _run(step, _params(repo))
    assert form.data.shape == (2, 3)
    assert list(form.dims) == ["design", "statistic"]
    assert list(form.labels["statistic"]) == ["score", "global_score", "seq_recovery"]
    assert form.info["chain"] == "A"
    assert form.info["cdr_sequences"]["CDR1"] == "PYCMG"
    assert form.info["native_sequence"].startswith("VQLQASGGG")
    assert len(form.info["fixed_positions"]) == 46
    assert export["n_designs"] == 2
    assert export["sequences"][0] == form.info["native_sequence"]


def test_changed_cdr_is_rejected(tmp_path):
    repo = _repo(tmp_path)
    script = repo / "protein_mpnn_run.py"
    script.write_text(
        FAKE_RUNNER.replace(
            'mutation = value("--mutation")',
            'mutation = "31"',
        )
    )
    step = AntibodyCdrRedesignStep()
    with pytest.raises(StepError, match="changed fixed CDR"):
        _run(step, _params(repo))
    script.write_text(FAKE_RUNNER)


def test_parameter_errors(tmp_path, monkeypatch):
    monkeypatch.delenv("OPERON_PROTEINMPNN_PATH", raising=False)
    step = AntibodyCdrRedesignStep()
    repo = _repo(tmp_path)
    with pytest.raises(StepError, match="structure_path is required"):
        _run(step, _params(repo, structure_path=""))
    with pytest.raises(StepError, match="is not a file"):
        _run(step, _params(repo, structure_path=str(tmp_path / "missing.pdb")))
    with pytest.raises(StepError, match="proteinmpnn_path is required"):
        _run(step, _params(repo, proteinmpnn_path=""))
    with pytest.raises(StepError, match="must contain protein_mpnn_run.py"):
        _run(step, _params(repo, proteinmpnn_path=str(tmp_path)))
    with pytest.raises(StepError, match="weights_path"):
        empty = tmp_path / "noweights"
        empty.mkdir()
        (empty / "protein_mpnn_run.py").write_text("raise SystemExit(0)")
        _run(step, _params(empty))
    with pytest.raises(StepError, match="model_name must be one of"):
        _run(step, _params(repo, model_name="v_99_999"))
    with pytest.raises(StepError, match="num_seq_per_target must be positive"):
        _run(step, _params(repo, num_seq_per_target=0))
    with pytest.raises(StepError, match="seed must not be negative"):
        _run(step, _params(repo, seed=-1))
    with pytest.raises(StepError, match="device must be"):
        _run(step, _params(repo, device="tpu"))
    with pytest.raises(StepError, match="timeout must be positive"):
        _run(step, _params(repo, timeout=0))
    with pytest.raises(StepError, match="was not found in the structure"):
        _run(step, _params(repo, chain="Z"))


def test_runner_failure(tmp_path):
    repo = _repo(tmp_path)
    (repo / "protein_mpnn_run.py").write_text("import sys\nsys.exit(3)\n")
    step = AntibodyCdrRedesignStep()
    with pytest.raises(StepError, match="exit code 3"):
        _run(step, _params(repo))


def test_missing_fasta(tmp_path):
    repo = _repo(tmp_path)
    (repo / "protein_mpnn_run.py").write_text("import sys\nsys.exit(0)\n")
    step = AntibodyCdrRedesignStep()
    with pytest.raises(StepError, match="produced no FASTA"):
        _run(step, _params(repo))


@pytest.mark.skipif(
    not REAL_REPO.is_dir()
    or not (REAL_REPO / "vanilla_model_weights" / "v_48_020.pt").is_file(),
    reason="official ProteinMPNN checkout is not available",
)
def test_official_runner_keeps_cdrs():
    step = AntibodyCdrRedesignStep()
    form, export = _run(
        step,
        {
            "structure_path": str(FIXTURE),
            "proteinmpnn_path": str(REAL_REPO),
            "num_seq_per_target": 2,
            "seed": 1,
            "device": "cpu",
            "output": "designs",
        },
    )
    assert form.data.shape == (2, 3)
    native = form.info["native_sequence"]
    residues, positions = cdr_positions(native)
    for design in form.info["sequences"]:
        for position in positions:
            assert design[position - 1] == native[position - 1]
    assert export["n_designs"] == 2
