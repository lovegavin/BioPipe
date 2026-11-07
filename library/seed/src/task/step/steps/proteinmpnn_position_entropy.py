"""Per-position amino-acid entropy from ProteinMPNN sampled designs."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step
from .proteinmpnn_design import MODELS

AA_ORDER = "ACDEFGHIKLMNPQRSTVWY"
_STATISTICS = ("entropy_bits", "recovery", "max_frequency", "n_observed")


def read_fasta(path: Path) -> list[tuple[str, str]]:
    """Read plain FASTA records (header, sequence)."""
    records: list[tuple[str, str]] = []
    header: str | None = None
    sequence: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(">"):
            if header is not None:
                records.append((header, "".join(sequence)))
            header = line[1:].strip()
            sequence = []
        elif header is not None:
            sequence.append(line.strip())
    if header is not None:
        records.append((header, "".join(sequence)))
    return records


def split_designs(records: list[tuple[str, str]]) -> tuple[str, list[str]]:
    """Split designer FASTA records into (native sequence, generated designs)."""
    if len(records) < 2:
        raise StepError(
            "proteinmpnn_position_entropy: the designer FASTA has no generated designs"
        )
    native = records[0][1]
    designs = [sequence for _, sequence in records[1:]]
    if not native:
        raise StepError(
            "proteinmpnn_position_entropy: the designer FASTA has no native sequence"
        )
    if not designs:
        raise StepError(
            "proteinmpnn_position_entropy: the designer FASTA has no generated designs"
        )
    return native, designs


def position_entropy(designs: list[str], native: str) -> list[dict]:
    """Summarise per-position amino-acid distributions of sampled designs."""
    if not designs:
        raise StepError("proteinmpnn_position_entropy: no designs were generated")
    lengths = {len(sequence) for sequence in designs}
    if lengths != {len(native)}:
        raise StepError(
            "proteinmpnn_position_entropy: every design must match the native "
            f"length {len(native)}, got {sorted(lengths)}"
        )
    rows: list[dict] = []
    for position in range(len(native)):
        counts = np.zeros(20, dtype=np.float64)
        for sequence in designs:
            residue = sequence[position]
            if residue not in AA_ORDER:
                raise StepError(
                    f"proteinmpnn_position_entropy: design residue '{residue}' at "
                    f"position {position + 1} is not a standard amino acid"
                )
            counts[AA_ORDER.index(residue)] += 1.0
        total = float(counts.sum())
        probabilities = counts / total
        nonzero = probabilities[probabilities > 0.0]
        entropy = float(-np.sum(nonzero * np.log2(nonzero)))
        best = int(np.argmax(probabilities))
        rows.append(
            {
                "position": position + 1,
                "entropy_bits": entropy,
                "recovery": float(probabilities[AA_ORDER.find(native[position])]),
                "max_frequency": float(probabilities[best]),
                "n_observed": int(total),
                "consensus": AA_ORDER[best],
            }
        )
    return rows


def designer_command(
    repo: Path, structure: Path, out_dir: Path, params: dict
) -> list[str]:
    """Build the official ProteinMPNN command for a sampling run."""
    executable = params.get("python_executable") or sys.executable
    command = [
        executable,
        "protein_mpnn_run.py",
        "--pdb_path",
        structure.as_posix(),
        "--out_folder",
        out_dir.as_posix(),
        "--num_seq_per_target",
        str(params["num_seq_per_target"]),
        "--sampling_temp",
        str(params["sampling_temp"]),
        "--seed",
        str(params["seed"]),
        "--suppress_print",
        "1",
        "--model_name",
        params["model_name"],
    ]
    weights = params.get("weights_path") or ""
    if weights:
        command += ["--path_to_model_weights", Path(weights).resolve().as_posix()]
    chains = params.get("chains") or ""
    if chains:
        command += ["--pdb_path_chains", chains]
    return command


def run_designer(repo: Path, structure: Path, out_dir: Path, params: dict) -> None:
    command = designer_command(repo, structure, out_dir, params)
    env = dict(os.environ)
    if params["device"] == "cpu":
        env["CUDA_VISIBLE_DEVICES"] = ""
    try:
        completed = subprocess.run(
            command,
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=int(params["timeout"]),
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise StepError(
            "proteinmpnn_position_entropy: the designer timed out after "
            f"{params['timeout']} s"
        ) from exc
    except OSError as exc:
        raise StepError(
            f"proteinmpnn_position_entropy: cannot start the designer: {exc}"
        ) from exc
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-6:]
        message = " | ".join(line.strip() for line in tail if line.strip())
        raise StepError(
            "proteinmpnn_position_entropy: the designer failed with exit code "
            f"{completed.returncode}: {message or 'no diagnostic output'}"
        )


class ProteinmpnnPositionEntropyStep(Step):
    provider = "operon-core"
    parameters_file = (
        "proteinmpnn_position_entropy.ProteinmpnnPositionEntropyStep.parameters.json"
    )
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_position_entropy",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ProteinMPNN position entropy",
        "category": "Machine Learning",
        "icon": "ArrowsDownUp",
        "description": (
            "Sample ProteinMPNN designs for a structure and summarise the "
            "per-position amino-acid entropy and native recovery."
        ),
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "version": 1,
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info": {"missing_code": {"type": ["number", "null"]}},
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": True,
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list) -> None:
        params = ctx.step_params
        structure = Path(str(params.get("structure_path") or "")).expanduser()
        if not structure.is_file():
            raise StepError(
                "proteinmpnn_position_entropy: structure_path must point at an existing PDB file"
            )
        repo = Path(str(params.get("proteinmpnn_path") or "")).expanduser()
        if not (repo / "protein_mpnn_run.py").is_file():
            raise StepError(
                "proteinmpnn_position_entropy: proteinmpnn_path must contain protein_mpnn_run.py"
            )
        model_name = str(params.get("model_name") or "v_48_020")
        if model_name not in MODELS:
            raise StepError(
                f"proteinmpnn_position_entropy: model_name must be one of {list(MODELS)}"
            )
        device = str(params.get("device") or "cpu")
        if device not in {"cpu", "cuda"}:
            raise StepError("proteinmpnn_position_entropy: device must be 'cpu' or 'cuda'")
        raw_samples = params.get("num_seq_per_target")
        num_samples = 4 if raw_samples is None else int(raw_samples)
        if num_samples < 2:
            raise StepError(
                "proteinmpnn_position_entropy: num_seq_per_target must be at least 2 "
                "to estimate an entropy"
            )
        raw_temperature = params.get("sampling_temp")
        temperature = 0.1 if raw_temperature is None else float(raw_temperature)
        if not 0.0 < temperature <= 1.0:
            raise StepError(
                "proteinmpnn_position_entropy: sampling_temp must be in (0, 1]"
            )
        seed = int(params["seed"]) if params.get("seed") is not None else 1
        if seed < 0:
            raise StepError("proteinmpnn_position_entropy: seed must not be negative")
        raw_timeout = params.get("timeout")
        timeout = 1800 if raw_timeout is None else int(raw_timeout)
        out_name = params["output"]
        with tempfile.TemporaryDirectory(prefix="operon-mpnn-entropy-") as tmp:
            out_dir = Path(tmp)
            run_designer(
                repo,
                structure,
                out_dir,
                {
                    "python_executable": params.get("python_executable") or "",
                    "weights_path": params.get("weights_path") or "",
                    "num_seq_per_target": num_samples,
                    "sampling_temp": temperature,
                    "seed": seed,
                    "model_name": model_name,
                    "chains": params.get("chains") or "",
                    "device": device,
                    "timeout": timeout,
                },
            )
            fasta = out_dir / "seqs" / f"{structure.stem}.fa"
            if not fasta.is_file():
                raise StepError(
                    "proteinmpnn_position_entropy: the designer produced no FASTA at "
                    f"'{fasta}'"
                )
            native, designs = split_designs(read_fasta(fasta))
        rows = position_entropy(designs, native)
        data = np.asarray(
            [[row[name] for name in _STATISTICS] for row in rows], dtype=np.float32
        )
        if not np.isfinite(data).all():
            raise StepError(
                "proteinmpnn_position_entropy: the entropy table contains non-finite values"
            )
        mean_entropy = float(np.mean(data[:, 0]))
        labels = {
            "position": {str(index + 1): index for index in range(len(native))},
            "statistic": {name: index for index, name in enumerate(_STATISTICS)},
        }
        form = Form(
            data=data,
            dims=["position", "statistic"],
            labels=labels,
            info={
                "missing_code": np.nan,
                "native_sequence": native,
                "consensus": [row["consensus"] for row in rows],
                "mean_entropy_bits": mean_entropy,
                "model_name": model_name,
                "num_samples": len(designs),
                "sampling_temp": temperature,
                "seed": seed,
                "chains": str(params.get("chains") or ""),
            },
        )
        form.validate()
        ctx[out_name] = form
        self._export_data = {
            "positions": len(native),
            "num_samples": len(designs),
            "model_name": model_name,
            "mean_entropy_bits": mean_entropy,
            "min_entropy_bits": float(data[:, 0].min()),
            "max_entropy_bits": float(data[:, 0].max()),
            "consensus": [row["consensus"] for row in rows],
        }
        print(
            f"[proteinmpnn_position_entropy] {len(native)} positions x "
            f"{len(designs)} designs, mean entropy {mean_entropy:.3f} bits"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
