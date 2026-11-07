"""Hand and oracle checks for the ProteinMPNN design operator."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from src.core import StepError
from src.task.step.steps.proteinmpnn_design import (
    ProteinMpnnDesignStep,
    parse_design_fasta,
    parse_positions,
    pdb_chains,
)

FAKE_RUNNER = '''\
import json
import os
import sys
from pathlib import Path


def value(flag):
    return sys.argv[sys.argv.index(flag) + 1]


out = Path(value("--out_folder"))
pdb = Path(value("--pdb_path"))
(out / "seqs").mkdir(parents=True, exist_ok=True)
fixed = {}
if "--fixed_positions_jsonl" in sys.argv:
    fixed_path = Path(value("--fixed_positions_jsonl"))
    fixed = json.loads(fixed_path.read_text())
(out / "seqs" / (pdb.stem + ".fa")).write_text(
    ">native, score=1.9000, global_score=2.0000, fixed_chains=['A'], "
    "designed_chains=['A'], model_name=v_48_020, git_hash=None, seed=0\\n"
    "ACDEFG/HIKLMN\\n"
    ">T=0.10, sample=1, score=1.2345, global_score=1.3456, "
    "seq_recovery=0.4567\\n"
    "ACDEYG/HIKLMN\\n"
    ">T=0.10, sample=2, score=1.1000, global_score=1.2000, "
    "seq_recovery=0.5000\\n"
    "ACDEFG/WWWWWW\\n"
)
Path("captured.json").write_text(json.dumps({
    "argv": sys.argv[1:],
    "cwd": os.getcwd(),
    "cuda": os.environ.get("CUDA_VISIBLE_DEVICES", "unset"),
    "fixed": fixed,
}))
'''


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _atom(serial, name, resname, chain, number, x, y, z, element):
    return (
        f"ATOM  {serial:5d} {name:^4} {resname:>3} {chain:1}{number:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{0.00:6.2f}          "
        f"{element:>2}"
    )


def _write_pdb(tmp_path: Path) -> Path:
    lines = [
        _atom(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0, "C"),
        _atom(2, "CA", "GLY", "A", 2, 3.0, 0.0, 0.0, "C"),
        _atom(3, "CA", "THR", "A", 3, 0.0, 0.0, 10.0, "C"),
        _atom(4, "CA", "SER", "B", 1, 0.0, 0.0, 4.0, "C"),
        _atom(5, "CA", "SER", "B", 2, 0.0, 0.0, 6.0, "C"),
    ]
    path = tmp_path / "tiny_structure.pdb"
    path.write_text("\n".join(lines) + "\nEND\n", encoding="utf-8")
    return path


def _fake_repo(tmp_path: Path, weights: bool = True) -> Path:
    repo = tmp_path / "ProteinMPNN"
    repo.mkdir()
    (repo / "protein_mpnn_run.py").write_text(FAKE_RUNNER, encoding="utf-8")
    if weights:
        (repo / "vanilla_model_weights").mkdir()
        (repo / "vanilla_model_weights" / "v_48_020.pt").write_bytes(b"fake")
    return repo


def _run(params):
    ctx = Ctx(params)
    ProteinMpnnDesignStep().run(ctx, [])
    return ctx["out"]


def test_parse_positions_hand():
    assert parse_positions("A:97-110,A:26-33") == {
        "A": list(range(26, 34)) + list(range(97, 111))
    }
    assert parse_positions("A:1,3,5") == {"A": [1, 3, 5]}
    assert parse_positions("B:5 A:2-3") == {"A": [2, 3], "B": [5]}
    assert parse_positions("") == {}
    with pytest.raises(StepError, match="is not of the form"):
        parse_positions("A:")
    with pytest.raises(StepError, match="ends before it starts"):
        parse_positions("A:9-3")
    with pytest.raises(StepError, match="positions must start with a chain"):
        parse_positions("97-110")


def test_saved_native_files_and_sequence_axis(tmp_path):
    from src.task.context import Context
    from src.task.runner import run
    structure, repo = _write_pdb(tmp_path), _fake_repo(tmp_path)
    ctx = Context(tmp_path / 'native-task', {})
    try:
        run(ctx, [
            {'name': 'proteinmpnn_design', 'inputs': [], 'params': {
                'output': 'designs', 'structure_path': str(structure),
                'proteinmpnn_path': str(repo), 'device': 'cpu'}},
            {'name': 'export_results', 'inputs': ['designs'], 'params': {
                'output': 'native', 'format': 'native'}}])
        files = ctx.artifacts['native_results']['designs']['files']
        assert {item['format'] for item in files} == {'fasta', 'csv'}
        assert set(ctx['native'].files.values()) == {item['path'] for item in files}
        assert len(ctx['native'].info['reused_roles']) == 2
        fasta = Path(next(item['path'] for item in files if item['format'] == 'fasta')).read_text()
        assert '>native, score=1.9000' in fasta and 'ACDEYG/HIKLMN' in fasta
        selected = ctx['designs'].subset_axis('design', [1])
        assert selected.info['sequences'] == ['ACDEFG/WWWWWW']
    finally:
        ctx.finalize()


def test_pdb_chains_hand(tmp_path):
    path = _write_pdb(tmp_path)
    assert pdb_chains(path) == {"A": [1, 2, 3], "B": [1, 2]}


def test_parse_design_fasta_hand(tmp_path):
    path = tmp_path / "seqs.fa"
    path.write_text(
        ">T=0.10, sample=2, score=1.1000, global_score=1.2000, "
        "seq_recovery=0.5000\nACDEFG\n"
        ">native, score=1.9, global_score=2.0, fixed_chains=['A']\nAAAAAA\n",
        encoding="utf-8",
    )
    records = parse_design_fasta(path)
    assert len(records) == 1
    assert records[0]["sample"] == 2
    assert records[0]["score"] == pytest.approx(1.1)
    assert records[0]["sequence"] == "ACDEFG"


def test_design_command_and_output(tmp_path):
    structure = _write_pdb(tmp_path)
    repo = _fake_repo(tmp_path)
    form = _run({
        "structure_path": str(structure),
        "proteinmpnn_path": str(repo),
        "num_seq_per_target": 4,
        "sampling_temp": "0.1",
        "seed": 7,
        "design_ranges": "A:2-3,B:1",
        "chains": "A",
        "device": "cpu",
    })

    assert list(form.dims) == ["design", "statistic"]
    assert form.labels["design"] == {"design_1": 0, "design_2": 1}
    assert form.labels["statistic"] == {
        "score": 0,
        "global_score": 1,
        "seq_recovery": 2,
    }
    np.testing.assert_allclose(
        form.data,
        [[1.2345, 1.3456, 0.4567], [1.1, 1.2, 0.5]],
        rtol=1e-5,
        atol=1e-6,
    )
    assert form.info["sequences"] == ["ACDEYG/HIKLMN", "ACDEFG/WWWWWW"]
    assert form.info["model_name"] == "v_48_020"
    assert form.info["design_positions"] == {"A": [2, 3], "B": [1]}

    captured = json.loads((repo / "captured.json").read_text())
    argv = captured["argv"]
    assert "--pdb_path" in argv
    pdb_argument = argv[argv.index("--pdb_path") + 1]
    assert pdb_argument == structure.as_posix()
    assert "\\" not in pdb_argument
    assert argv[argv.index("--num_seq_per_target") + 1] == "4"
    assert argv[argv.index("--seed") + 1] == "7"
    assert argv[argv.index("--model_name") + 1] == "v_48_020"
    assert argv[argv.index("--pdb_path_chains") + 1] == "A"
    assert argv[argv.index("--path_to_model_weights") + 1] == (
        repo / "vanilla_model_weights"
    ).as_posix()
    assert argv[argv.index("--suppress_print") + 1] == "1"
    assert captured["cwd"] == str(repo)
    assert captured["cuda"] == ""
    assert captured["fixed"] == {structure.as_posix(): {"A": [1], "B": [2]}}


def test_fixed_positions_parameter(tmp_path):
    structure = _write_pdb(tmp_path)
    repo = _fake_repo(tmp_path)
    _run({
        "structure_path": str(structure),
        "proteinmpnn_path": str(repo),
        "fixed_positions": "A:1-2",
        "num_seq_per_target": 1,
    })
    captured = json.loads((repo / "captured.json").read_text())
    argv = captured["argv"]
    pdb_argument = argv[argv.index("--pdb_path") + 1]
    assert captured["fixed"] == {pdb_argument: {"A": [1, 2]}}
    assert pdb_argument == structure.as_posix()


def test_design_errors(tmp_path):
    structure = _write_pdb(tmp_path)
    repo = _fake_repo(tmp_path)
    base = {"proteinmpnn_path": str(repo)}

    with pytest.raises(StepError, match="is not a file"):
        _run({"structure_path": str(tmp_path / "missing.pdb"), **base})

    with pytest.raises(StepError, match="not a directory"):
        _run({"structure_path": str(structure), "proteinmpnn_path": str(tmp_path / "nope")})

    with pytest.raises(StepError, match="does not exist"):
        broken = tmp_path / "broken"
        broken.mkdir()
        _run({"structure_path": str(structure), "proteinmpnn_path": str(broken)})

    with pytest.raises(StepError, match="weights"):
        repo_no_weights = tmp_path / "no_weights"
        repo_no_weights.mkdir()
        (repo_no_weights / "protein_mpnn_run.py").write_text("", encoding="utf-8")
        _run({
            "structure_path": str(structure),
            "proteinmpnn_path": str(repo_no_weights),
        })

    with pytest.raises(StepError, match="not both"):
        _run({
            "structure_path": str(structure),
            **base,
            "design_ranges": "A:1",
            "fixed_positions": "A:2",
        })

    with pytest.raises(StepError, match="absent from chain"):
        _run({"structure_path": str(structure), **base, "design_ranges": "A:99"})

    with pytest.raises(StepError, match="but the structure has"):
        _run({"structure_path": str(structure), **base, "design_ranges": "Z:1"})

    with pytest.raises(StepError, match="at least 1"):
        _run({
            "structure_path": str(structure),
            **base,
            "num_seq_per_target": 0,
        })

    with pytest.raises(StepError, match="device must be"):
        _run({"structure_path": str(structure), **base, "device": "tpu"})


def test_runner_failure_reports_stderr(tmp_path):
    structure = _write_pdb(tmp_path)
    repo = tmp_path / "failing"
    repo.mkdir()
    (repo / "vanilla_model_weights").mkdir()
    (repo / "vanilla_model_weights" / "v_48_020.pt").write_bytes(b"fake")
    (repo / "protein_mpnn_run.py").write_text(
        "import sys\nprint('boom-details', file=sys.stderr)\nsys.exit(3)\n",
        encoding="utf-8",
    )
    with pytest.raises(StepError, match="exit code 3"):
        _run({"structure_path": str(structure), "proteinmpnn_path": str(repo)})


REAL_REPO = Path("/home/gavin/tools/ProteinMPNN")


@pytest.mark.skipif(
    not (REAL_REPO / "protein_mpnn_run.py").is_file()
    or not (REAL_REPO / "vanilla_model_weights" / "v_48_020.pt").is_file()
    or not __import__("os").environ.get("OPERON_RUN_PROTEINMPNN"),
    reason="official ProteinMPNN checkout or OPERON_RUN_PROTEINMPNN is absent",
)
def test_official_runner_minimal(tmp_path):
    """Oracle: the official runner must accept our command line."""
    structure = tmp_path / "mini.pdb"
    structure.write_text(
        "\n".join(
            _atom(serial, name, resname, "A", number, x, 0.0, 0.0, "C")
            for serial, (name, resname, number, x) in enumerate(
                [
                    ("N", "ALA", 1, 0.0),
                    ("CA", "ALA", 1, 1.4),
                    ("C", "ALA", 1, 2.5),
                    ("O", "ALA", 1, 3.6),
                    ("N", "GLY", 2, 4.0),
                    ("CA", "GLY", 2, 5.4),
                    ("C", "GLY", 2, 6.5),
                    ("O", "GLY", 2, 7.6),
                ],
                start=1,
            )
        )
        + "\nEND\n",
        encoding="utf-8",
    )
    form = _run({
        "structure_path": str(structure),
        "proteinmpnn_path": str(REAL_REPO),
        "num_seq_per_target": 1,
        "device": "cpu",
    })
    assert form.data.shape == (1, 3)
    assert form.info["sequences"][0]
