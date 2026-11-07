"""Design antibody framework positions while keeping every Kabat CDR fixed."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step
from src.task.step.steps.antibody_cdr_kabat import kabat_regions
from src.task.step.steps.proteinmpnn_design import (
    MODELS,
    parse_design_fasta,
    pdb_chains,
)


def chain_sequence(path: Path, chain: str) -> tuple[list[str], list[int]]:
    """Return the one-letter sequence and residue numbers of ``chain``."""
    protein_letters = _three_to_one()
    letters: list[str] = []
    numbers: list[int] = []
    seen: set[tuple[int, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("ATOM  "):
            continue
        if line[21:22] != chain:
            continue
        try:
            number = int(line[22:26])
        except ValueError as exc:  # pragma: no cover - defensive
            raise StepError(
                f"antibody_cdr_redesign: chain '{chain}' has a non-numeric residue number"
            ) from exc
        key = (number, line[26:27])
        if key in seen:
            continue
        seen.add(key)
        three = line[17:20].strip().upper()
        residue = protein_letters.get(three)
        if residue is None or residue == "X":
            raise StepError(
                f"antibody_cdr_redesign: residue '{three}' at {number} of chain '{chain}' "
                "is not a standard amino acid"
            )
        letters.append(residue)
        numbers.append(number)
    if not letters:
        raise StepError(
            f"antibody_cdr_redesign: chain '{chain}' was not found in the structure"
        )
    return letters, numbers


def _three_to_one() -> dict[str, str]:
    try:
        from Bio.PDB.Polypeptide import protein_letters_3to1
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise StepError(
            "antibody_cdr_redesign: biopython is required to translate residues"
        ) from exc
    return {
        key.upper(): value
        for key, value in protein_letters_3to1.items()
    }


def cdr_positions(sequence: str) -> tuple[list[str], list[int]]:
    """Return the CDR residues and their 1-based positions."""
    residues: list[str] = []
    positions: list[int] = []
    for name, start, end, block in kabat_regions(sequence):
        if name not in {"CDR1", "CDR2", "CDR3"}:
            continue
        residues.append(block)
        positions.extend(range(start, end + 1))
    if not positions:
        raise StepError(
            "antibody_cdr_redesign: no Kabat CDR could be located in the chain sequence"
        )
    return residues, positions


def fixed_payload(
    structure: Path,
    chain: str,
    positions: list[int],
    numbers: list[int],
) -> dict[str, dict[str, list[int]]]:
    """Build the ProteinMPNN fixed-position payload keyed by the PDB stem."""
    chains = pdb_chains(structure)
    if chain not in chains:
        raise StepError(
            f"antibody_cdr_redesign: chain '{chain}' was not found in the structure"
        )
    fixed = sorted(int(position) for position in positions)
    payload: dict[str, list[int]] = {}
    for name, residues in chains.items():
        if name == chain:
            payload[name] = fixed
        else:
            payload[name] = list(range(1, len(residues) + 1))
    return {structure.stem: payload}


class AntibodyCdrRedesignStep(Step):
    provider = "operon-core"
    parameters_file = "antibody_cdr_redesign.AntibodyCdrRedesignStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "antibody_cdr_redesign",
        "version": "1.0.0",
        "kind": "operator",
        "title": "CDR 固定框架重设计",
        "description": "保持 Kabat CDR 不变，用 ProteinMPNN 重设计抗体框架位点。",
        "category": "Machine Learning",
        "icon": "Tag",
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
        "dependencies": ["numpy>=1.24", "biopython>=1.80"],
        "dependency_imports": ["numpy", "Bio"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list[Form]) -> None:
        params = ctx.step_params
        structure = str(params.get("structure_path", "")).strip()
        if not structure:
            raise StepError(
                "antibody_cdr_redesign: structure_path is required; point it at a PDB file"
            )
        structure_path = Path(structure)
        if not structure_path.is_file():
            raise StepError(
                f"antibody_cdr_redesign: structure_path '{structure}' is not a file"
            )
        repo = str(params.get("proteinmpnn_path", "")).strip()
        if not repo:
            repo = os.environ.get("OPERON_PROTEINMPNN_PATH", "").strip()
        if not repo:
            raise StepError(
                "antibody_cdr_redesign: proteinmpnn_path is required; point it at the "
                "official ProteinMPNN checkout"
            )
        repo_path = Path(repo)
        runner = repo_path / "protein_mpnn_run.py"
        if not runner.is_file():
            raise StepError(
                f"antibody_cdr_redesign: '{repo}' must contain protein_mpnn_run.py"
            )
        weights_text = str(params.get("weights_path", "")).strip()
        weights_path = (
            Path(weights_text) if weights_text else repo_path / "vanilla_model_weights"
        )
        if not weights_path.is_dir():
            raise StepError(
                f"antibody_cdr_redesign: weights_path '{weights_path}' is not a directory"
            )
        model_name = str(params.get("model_name", "v_48_020"))
        if model_name not in MODELS:
            raise StepError(
                f"antibody_cdr_redesign: model_name must be one of {list(MODELS)}"
            )
        chain = str(params.get("chain", "A")).strip().upper()
        if not chain:
            raise StepError("antibody_cdr_redesign: chain must name one chain")
        num_sequences = int(params.get("num_seq_per_target", 8))
        if num_sequences < 1:
            raise StepError(
                "antibody_cdr_redesign: num_seq_per_target must be positive"
            )
        sampling_temp = str(params.get("sampling_temp", "0.1")).strip() or "0.1"
        seed = int(params.get("seed", 1))
        if seed < 0:
            raise StepError("antibody_cdr_redesign: seed must not be negative")
        device = str(params.get("device", "cpu"))
        if device not in {"cpu", "cuda"}:
            raise StepError("antibody_cdr_redesign: device must be 'cpu' or 'cuda'")
        timeout = float(params.get("timeout", 1800.0))
        if timeout <= 0:
            raise StepError("antibody_cdr_redesign: timeout must be positive")
        output = str(params.get("output", "designs"))

        sequence, numbers = chain_sequence(structure_path, chain)
        cdr_residues, positions = cdr_positions("".join(sequence))
        payload = fixed_payload(structure_path, chain, positions, numbers)

        out_dir = Path(tempfile.mkdtemp(prefix="operon-cdr-redesign-"))
        fixed_jsonl = out_dir / "fixed_positions.jsonl"
        fixed_jsonl.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        started = time.monotonic()
        try:
            command = [
                _python(params),
                runner.as_posix(),
                "--pdb_path", structure_path.as_posix(),
                "--out_folder", out_dir.as_posix(),
                "--num_seq_per_target", str(num_sequences),
                "--sampling_temp", sampling_temp,
                "--seed", str(seed),
                "--path_to_model_weights", weights_path.as_posix(),
                "--model_name", model_name,
                "--suppress_print", "1",
                "--pdb_path_chains", chain,
                "--fixed_positions_jsonl", fixed_jsonl.as_posix(),
            ]
            environment = dict(os.environ)
            if device == "cpu":
                environment["CUDA_VISIBLE_DEVICES"] = ""
            else:
                environment.pop("CUDA_VISIBLE_DEVICES", None)
            completed = subprocess.run(
                command,
                cwd=repo_path,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
            )
            if completed.returncode != 0:
                tail = (completed.stderr or completed.stdout or "").strip()[-800:]
                raise StepError(
                    f"antibody_cdr_redesign: protein_mpnn_run.py failed with exit code "
                    f"{completed.returncode}: {tail}"
                )
            fasta = out_dir / "seqs" / f"{structure_path.stem}.fa"
            if not fasta.is_file():
                raise StepError(
                    f"antibody_cdr_redesign: the designer produced no FASTA at {fasta}"
                )
            designs = parse_design_fasta(fasta)
            if not designs:
                raise StepError(
                    "antibody_cdr_redesign: the designer FASTA has no generated designs"
                )
            for index, record in enumerate(designs, start=1):
                designed = record["sequence"]
                for position in positions:
                    if designed[position - 1] != sequence[position - 1]:
                        raise StepError(
                            f"antibody_cdr_redesign: design {index} changed fixed CDR "
                            f"residue {position} ({sequence[position - 1]} -> "
                            f"{designed[position - 1]})"
                        )
            data = np.asarray(
                [
                    [
                        float(record["score"]),
                        float(record["global_score"]),
                        float(record["seq_recovery"]),
                    ]
                    for record in designs
                ],
                dtype=np.float32,
            )
            ctx[output] = Form(
                data=data,
                dims=["design", "statistic"],
                labels={
                    "design": {
                        f"design_{record['sample']}": index
                        for index, record in enumerate(designs)
                    },
                    "statistic": {
                        "score": 0,
                        "global_score": 1,
                        "seq_recovery": 2,
                    },
                },
                info={
                    "missing_code": np.nan,
                    "sequences": [record["sequence"] for record in designs],
                    "cdr_sequences": dict(zip(("CDR1", "CDR2", "CDR3"), cdr_residues)),
                    "chain": chain,
                    "fixed_positions": payload[structure_path.stem][chain],
                    "native_sequence": "".join(sequence),
                    "model_name": model_name,
                    "sampling_temp": sampling_temp,
                    "seed": seed,
                    "device": device,
                },
            )
            elapsed = time.monotonic() - started
            self._export_data = {
                "chain": chain,
                "native_sequence": "".join(sequence),
                "cdr_sequences": dict(zip(("CDR1", "CDR2", "CDR3"), cdr_residues)),
                "fixed_positions": payload[structure_path.stem][chain],
                "n_designs": len(designs),
                "sequences": [record["sequence"] for record in designs],
                "elapsed_seconds": round(elapsed, 3),
            }
            print(
                f"[antibody_cdr_redesign] {len(designs)} designs from "
                f"{structure_path.name} ({chain}, {len(positions)} fixed CDR residues, "
                f"{elapsed:.1f}s)"
            )
        except subprocess.TimeoutExpired as exc:
            raise StepError(
                f"antibody_cdr_redesign: the designer timed out after {timeout:.0f}s"
            ) from exc
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


def _python(params: dict) -> str:
    executable = str(params.get("python_executable", "")).strip()
    if executable:
        return executable
    return sys.executable
