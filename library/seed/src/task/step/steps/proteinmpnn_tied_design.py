"""ProteinMPNN tied-position design with a shared sequence across symmetry mates."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps.proteinmpnn_design import MODELS, parse_design_fasta, pdb_chains

_STATISTICS = ("score", "global_score")
_SEPARATORS = ("|", ";")


def _split_groups(text: str) -> list[str]:
    groups = [text]
    for separator in _SEPARATORS:
        groups = [part for chunk in groups for part in chunk.split(separator)]
    return [part.strip() for part in groups if part.strip()]


def parse_tied_groups(text: str) -> dict[str, list[int]]:
    """Parse ``A:1,2|B:1,2`` into ``{chain: [positions]}``.

    Every chain must list the same number of positions, so site ``i`` ties
    ``A[i]`` to ``B[i]`` and every other chain.
    """

    groups = _split_groups(str(text or ""))
    if not groups:
        raise StepError("proteinmpnn_tied_design: tied_positions is required")
    if len(groups) < 2:
        raise StepError(
            "proteinmpnn_tied_design: tied_positions must declare at least two chains to tie"
        )
    tied: dict[str, list[int]] = {}
    for group in groups:
        if ":" not in group:
            raise StepError(
                f"proteinmpnn_tied_design: '{group}' is not of the form A:1,2"
            )
        chain, positions_text = group.split(":", 1)
        chain = chain.strip()
        if not chain:
            raise StepError(f"proteinmpnn_tied_design: '{group}' is missing the chain name")
        if chain in tied:
            raise StepError(f"proteinmpnn_tied_design: chain {chain} appears twice in tied_positions")
        positions: list[int] = []
        for token in positions_text.replace(",", " ").split():
            try:
                position = int(token)
            except ValueError as error:
                raise StepError(
                    f"proteinmpnn_tied_design: tied position '{token}' is not an integer"
                ) from error
            if position <= 0:
                raise StepError("proteinmpnn_tied_design: tied positions must be positive residue numbers")
            if position in positions:
                raise StepError(
                    f"proteinmpnn_tied_design: chain {chain} lists position {position} twice"
                )
            positions.append(position)
        if not positions:
            raise StepError(f"proteinmpnn_tied_design: chain {chain} lists no tied positions")
        tied[chain] = positions
    lengths = {chain: len(positions) for chain, positions in tied.items()}
    if len(set(lengths.values())) != 1:
        detail = ", ".join(f"{chain} has {count}" for chain, count in lengths.items())
        raise StepError(
            "proteinmpnn_tied_design: every tied chain must list the same number of positions "
            f"({detail})"
        )
    return tied


def tied_payload(
    tied: dict[str, list[int]],
    chains: str,
    stem: str,
    author_numbers: dict[str, list[int]],
) -> dict[str, list[dict[str, list[int]]]]:
    """Build the official ``--tied_positions_jsonl`` payload for one structure."""

    wanted = [chain for chain in chains.replace(",", " ").split() if chain] or sorted(tied)
    for chain, positions in tied.items():
        if chain not in wanted:
            raise StepError(
                f"proteinmpnn_tied_design: chain {chain} is not among the designed chains "
                f"({', '.join(wanted)})"
            )
        if chain not in author_numbers:
            raise StepError(
                f"proteinmpnn_tied_design: chain {chain} is not in the structure file"
            )
        known = set(author_numbers[chain])
        missing = [position for position in positions if position not in known]
        if missing:
            listed = ", ".join(str(position) for position in missing)
            raise StepError(
                f"proteinmpnn_tied_design: residue(s) {listed} are not author residue numbers of "
                f"chain {chain}"
            )
    count = len(next(iter(tied.values())))
    sites: list[dict[str, list[int]]] = []
    for index in range(count):
        sites.append({chain: [positions[index]] for chain, positions in tied.items()})
    return {stem: sites}


def run_tied_designer(
    params: dict,
    structure: Path,
    chain_text: str,
    payload: dict,
    weights: Path | None,
    repo: Path,
) -> list[dict]:
    """Run the official ProteinMPNN runner with a tied-positions payload."""

    runner = repo / "protein_mpnn_run.py"
    model_name = str(params.get("model_name") or "v_48_020")
    count = int(params.get("num_seq_per_target") if params.get("num_seq_per_target") is not None else 8)
    temperature = str(params.get("sampling_temp") or "0.1")
    seed = int(params.get("seed") if params.get("seed") is not None else 1)
    device = str(params.get("device") or "cpu")
    timeout = int(params.get("timeout") if params.get("timeout") is not None else 1800)
    if model_name not in MODELS:
        raise StepError(
            f"proteinmpnn_tied_design: model_name must be one of {', '.join(MODELS)}"
        )
    if count < 1:
        raise StepError("proteinmpnn_tied_design: num_seq_per_target must be at least 1")
    if device not in {"cpu", "cuda"}:
        raise StepError("proteinmpnn_tied_design: device must be 'cpu' or 'cuda'")
    python = str(params.get("python_executable") or "") or sys.executable

    out_dir = Path(tempfile.mkdtemp(prefix="operon-mpnn-tied-"))
    payload_path = out_dir / "tied_positions.jsonl"
    payload_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    command = [
        python,
        str(runner),
        "--pdb_path",
        structure.as_posix(),
        "--out_folder",
        out_dir.as_posix(),
        "--num_seq_per_target",
        str(count),
        "--sampling_temp",
        temperature,
        "--seed",
        str(seed),
        "--suppress_print",
        "1",
        "--model_name",
        model_name,
        "--tied_positions_jsonl",
        payload_path.as_posix(),
    ]
    if weights is not None:
        command.extend(["--path_to_model_weights", weights.as_posix()])
    if chain_text:
        command.extend(["--pdb_path_chains", chain_text])

    env = dict(os.environ)
    if device == "cpu":
        env["CUDA_VISIBLE_DEVICES"] = ""
    try:
        completed = subprocess.run(
            command,
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-3:]
            raise StepError(
                "proteinmpnn_tied_design: the designer failed with exit code "
                f"{completed.returncode}: {' | '.join(tail)}"
            )
        fasta = out_dir / "seqs" / f"{structure.stem}.fa"
        if not fasta.is_file():
            raise StepError(f"proteinmpnn_tied_design: the designer produced no FASTA at {fasta}")
        designs = parse_design_fasta(fasta)
    except subprocess.TimeoutExpired as error:
        raise StepError(f"proteinmpnn_tied_design: the designer timed out after {timeout} s") from error
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
    if not designs:
        raise StepError("proteinmpnn_tied_design: the designer produced no designs")
    return designs


class ProteinmpnnTiedDesignStep(Step):
    """Tie symmetry-equivalent positions to a shared amino acid during design."""

    provider = "operon-core"

    parameters_file = "proteinmpnn_tied_design.ProteinmpnnTiedDesignStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_tied_design",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ProteinMPNN tied-position design",
        "description": (
            "Run the official ProteinMPNN runner with a tied-positions payload so that "
            "symmetry-equivalent residues receive the same amino acid, and report the design "
            "scores together with the tied payload used."
        ),
        "category": "Machine Learning",
        "icon": "ShareNetwork",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": True, "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        structure_text = str(params.get("structure_path") or "").strip()
        if not structure_text:
            raise StepError("proteinmpnn_tied_design: structure_path is required")
        structure = Path(structure_text).expanduser()
        if not structure.is_file():
            raise StepError(f"proteinmpnn_tied_design: structure_path {structure} is not a file")
        if structure.suffix.lower() not in {".pdb", ".ent"}:
            raise StepError("proteinmpnn_tied_design: structure_path must be a .pdb file")

        repo = Path(str(params.get("proteinmpnn_path") or "")).expanduser()
        if not (repo / "protein_mpnn_run.py").is_file():
            raise StepError(
                f"proteinmpnn_tied_design: {repo / 'protein_mpnn_run.py'} does not exist; point "
                "proteinmpnn_path at the official ProteinMPNN checkout"
            )
        weights_text = str(params.get("weights_path") or "").strip()
        if weights_text:
            weights = Path(weights_text).expanduser()
        else:
            candidate = repo / "vanilla_model_weights"
            weights = candidate if candidate.is_dir() else None
        if weights is not None and not weights.is_dir():
            raise StepError(
                f"proteinmpnn_tied_design: weights directory {weights} does not exist; set "
                "weights_path to the directory holding v_48_*.pt"
            )

        tied = parse_tied_groups(str(params.get("tied_positions") or ""))
        chain_text = str(params.get("chains") or "").strip()
        author_numbers = pdb_chains(structure)
        payload = tied_payload(tied, chain_text, structure.stem, author_numbers)
        n_sites = len(payload[structure.stem])
        n_tied = n_sites * len(tied)

        designs = run_tied_designer(params, structure, chain_text, payload, weights, repo)
        design_dim = str(params.get("design_dim") or "design")
        out_name = str(params.get("output") or "designs")
        sequences = [str(record["sequence"]) for record in designs]
        scores = [float(record.get("score", np.nan)) for record in designs]
        globals_ = [float(record.get("global_score", np.nan)) for record in designs]
        data = np.asarray(list(zip(scores, globals_)), dtype=np.float32).reshape(len(designs), 2)
        out = Form(
            data=data,
            dims=[design_dim, "statistic"],
            labels={
                design_dim: {f"design{index + 1}": index for index in range(len(designs))},
                "statistic": {name: position for position, name in enumerate(_STATISTICS)},
            },
            info={
                "sequences": sequences,
                "n_designs": len(sequences),
                "n_residues": len(sequences[0]) if sequences else 0,
                "tied_positions": tied,
                "n_tied_sites": n_sites,
                "n_tied_residues": n_tied,
                "structure_path": str(structure),
                "model_name": str(params.get("model_name") or "v_48_020"),
                "missing_code": np.nan,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_designs": len(sequences),
            "n_tied_sites": n_sites,
            "n_tied_residues": n_tied,
        }
        print(f"[proteinmpnn_tied_design] {len(sequences)} designs, {n_tied} tied residues")

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
