"""ProteinMPNN redesign with a residue mask.

Residues listed in ``mask`` keep their wild-type identity (ProteinMPNN
``fixed_positions``); every other residue is redesigned. The mask accepts author
residue numbering, which is mapped onto ProteinMPNN's 1-based sequential chain
indices here.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps.proteinmpnn_design import MODELS, parse_design_fasta, parse_positions, pdb_chains

_STATISTICS = ("score", "global_score")


def mask_payload(mask: dict[str, list[int]], chains: dict[str, list[int]], stem: str) -> dict[str, dict[str, list[int]]]:
    """Fixed positions = complement of the mask, keyed by the PDB stem."""

    fixed: dict[str, list[int]] = {}
    for chain, numbers in chains.items():
        selected = set(mask.get(chain, []))
        sequential = {number: index + 1 for index, number in enumerate(numbers)}
        fixed[chain] = [sequential[number] for number in numbers if number not in selected]
    return {stem: fixed}


def run_masked_designer(params: dict, structure: Path, chain_text: str, payload: dict) -> list[dict]:
    repo = Path(str(params.get("proteinmpnn_path") or "")).expanduser()
    runner = repo / "protein_mpnn_run.py"
    if not runner.is_file():
        raise StepError(
            f"proteinmpnn_masked_design: {runner} does not exist; point proteinmpnn_path at the "
            "official ProteinMPNN checkout"
        )
    weights_text = str(params.get("weights_path") or "").strip()
    weights = Path(weights_text).expanduser() if weights_text else repo / "vanilla_model_weights"
    if not weights.is_dir():
        raise StepError(
            f"proteinmpnn_masked_design: weights directory {weights} does not exist; "
            "set weights_path to the directory holding v_48_*.pt"
        )

    model_name = str(params.get("model_name") or "v_48_020")
    count = int(params.get("num_seq_per_target") if params.get("num_seq_per_target") is not None else 8)
    temperature = str(params.get("sampling_temp") or "0.1")
    seed = int(params.get("seed") if params.get("seed") is not None else 1)
    device = str(params.get("device") or "cpu")
    timeout = int(params.get("timeout") if params.get("timeout") is not None else 1800)
    if model_name not in MODELS:
        raise StepError(f"proteinmpnn_masked_design: model_name must be one of {', '.join(MODELS)}")
    if count < 1:
        raise StepError("proteinmpnn_masked_design: num_seq_per_target must be at least 1")
    if device not in {"cpu", "cuda"}:
        raise StepError("proteinmpnn_masked_design: device must be 'cpu' or 'cuda'")

    python = str(params.get("python_executable") or "") or sys.executable
    out_dir = Path(tempfile.mkdtemp(prefix="operon-mpnn-masked-"))
    fixed_path = out_dir / "fixed_positions.jsonl"
    fixed_path.write_text(json.dumps(payload), encoding="utf-8")
    command = [
        python,
        runner.as_posix(),
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
        "--fixed_positions_jsonl",
        fixed_path.as_posix(),
        "--path_to_model_weights",
        weights.as_posix(),
    ]
    if chain_text:
        command.extend(["--pdb_path_chains", chain_text])

    env = dict(os.environ)
    if device == "cpu":
        env["CUDA_VISIBLE_DEVICES"] = ""
    try:
        completed = subprocess.run(
            command, cwd=str(repo), capture_output=True, text=True, timeout=timeout, env=env
        )
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-3:]
            raise StepError(
                "proteinmpnn_masked_design: the designer failed with exit code "
                f"{completed.returncode}: {' | '.join(tail)}"
            )
        fasta = out_dir / "seqs" / f"{structure.stem}.fa"
        if not fasta.is_file():
            raise StepError(f"proteinmpnn_masked_design: the designer produced no FASTA at {fasta}")
        designs = parse_design_fasta(fasta)
    except subprocess.TimeoutExpired as error:
        raise StepError(f"proteinmpnn_masked_design: the designer timed out after {timeout} s") from error
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
    if not designs:
        raise StepError("proteinmpnn_masked_design: the designer produced no designs")
    return designs


class ProteinmpnnMaskedDesignStep(Step):
    provider = "operon-core"
    parameters_file = "proteinmpnn_masked_design.ProteinmpnnMaskedDesignStep.parameters.json"

    definition: dict[str, Any] = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_masked_design",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Masked ProteinMPNN design",
        "description": "Redesign a structure while fixing the residues named by a mask.",
        "category": "Machine Learning",
        "icon": "MagicWand",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = dict(ctx.step_params)
        mask_text = str(params.get("mask") or "").strip()
        structure_text = str(params.get("structure_path") or "").strip()
        chain_text = str(params.get("chains") or "").strip()
        design_dim = str(params.get("design_dim") or "design")
        out_name = str(params.get("output") or "designs")

        if not structure_text:
            raise StepError("proteinmpnn_masked_design: structure_path is required")
        structure = Path(structure_text).expanduser()
        if not structure.is_file():
            raise StepError(f"proteinmpnn_masked_design: structure_path {structure} does not exist")
        if structure.suffix.lower() not in {".pdb", ".pdbqt"}:
            raise StepError("proteinmpnn_masked_design: structure_path must be a .pdb file")
        if not mask_text:
            raise StepError(
                "proteinmpnn_masked_design: mask is required, for example 'A:12-18,B:45'"
            )

        chains = pdb_chains(structure)
        mask = parse_positions(mask_text)
        if not mask:
            raise StepError("proteinmpnn_masked_design: mask selects no residues")
        available = {chain: set(numbers) for chain, numbers in chains.items()}
        for chain, numbers in mask.items():
            if chain not in available:
                raise StepError(
                    f"proteinmpnn_masked_design: chain {chain!r} is not present in the structure"
                )
            missing = [number for number in numbers if number not in available[chain]]
            if missing:
                raise StepError(
                    f"proteinmpnn_masked_design: chain {chain} has no residue {missing[0]}"
                )
        if chain_text:
            wanted = [part for part in chain_text.replace(",", " ").split() if part]
            unknown = [chain for chain in wanted if chain not in chains]
            if unknown:
                raise StepError(
                    f"proteinmpnn_masked_design: chains {', '.join(unknown)} are not in the structure"
                )
            if not any(chain in mask for chain in wanted):
                raise StepError(
                    "proteinmpnn_masked_design: the mask must include at least one residue of the designed chains"
                )

        fixed = mask_payload(mask, chains, structure.stem)
        total_fixed = sum(len(positions) for positions in fixed[structure.stem].values())
        if total_fixed == 0:
            raise StepError("proteinmpnn_masked_design: the mask fixes every residue; nothing to design")

        designs = run_masked_designer(params, structure, chain_text, fixed)
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
                "mask": mask_text,
                "fixed_positions": fixed[structure.stem],
                "n_fixed_residues": total_fixed,
                "structure_path": str(structure),
                "model_name": str(params.get("model_name") or "v_48_020"),
                "missing_code": np.nan,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_designs": len(sequences),
            "n_fixed_residues": total_fixed,
            "n_residues": out.info["n_residues"],
            "mask": mask_text,
        }
        print(
            f"[proteinmpnn_masked_design] {len(sequences)} designs with {total_fixed} fixed residues"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
