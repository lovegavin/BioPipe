"""Per-position native recovery of ProteinMPNN sampled designs."""

from __future__ import annotations

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
from .proteinmpnn_design import MODELS

AA_ORDER = "ACDEFGHIKLMNPQRSTVWY"
_STATISTICS = ("recovery", "dominant_frequency", "n_observed")


def read_records(path: Path) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    header: str | None = None
    sequence: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(">"):
            if header is not None:
                records.append((header, "".join(sequence).replace("/", "")))
            header = line[1:].strip()
            sequence = []
        elif header is not None:
            sequence.append(line.strip())
    if header is not None:
        records.append((header, "".join(sequence).replace("/", "")))
    if not records:
        raise StepError(f"proteinmpnn_native_recovery_scan: no FASTA records in '{path}'")
    return records


def recovery_rows(native: str, designs: list[str]) -> list[dict]:
    if not designs:
        raise StepError("proteinmpnn_native_recovery_scan: the designer produced no generated designs")
    for design in designs:
        if len(design) != len(native):
            raise StepError(
                f"proteinmpnn_native_recovery_scan: design length {len(design)} does not match the native "
                f"length {len(native)}"
            )
        for index, residue in enumerate(design):
            if residue not in AA_ORDER:
                raise StepError(
                    f"proteinmpnn_native_recovery_scan: design contains the non-standard residue '{residue}' "
                    f"at position {index + 1}"
                )
    total = len(designs)
    rows: list[dict] = []
    for index, wild_type in enumerate(native):
        counts: dict[str, int] = {}
        for design in designs:
            counts[design[index]] = counts.get(design[index], 0) + 1
        native_count = counts.get(wild_type, 0)
        substitutions = sorted(
            ((count, residue) for residue, count in counts.items() if residue != wild_type),
            reverse=True,
        )
        best = substitutions[0] if substitutions else (0, "")
        rows.append(
            {
                "position": index + 1,
                "recovery": native_count / total,
                "dominant_frequency": best[0] / total,
                "n_observed": float(total),
                "consensus": max(counts.items(), key=lambda item: (item[1], item[0]))[0],
                "dominant_substitution": best[1],
                "counts": counts,
            }
        )
    return rows


class ProteinmpnnNativeRecoveryScanStep(Step):
    """Report per-position native recovery across ProteinMPNN designs."""

    provider = "operon-core"
    parameters_file = "proteinmpnn_native_recovery_scan.ProteinmpnnNativeRecoveryScanStep.parameters.json"

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (200 * 1024 * 1024, 0)

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_native_recovery_scan",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ProteinMPNN Native Recovery Scan",
        "description": "Per-position native recovery and dominant substitution of sampled designs.",
        "category": "Machine Learning",
        "icon": "ArrowsDownUp",
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

    def run(self, ctx: Context, inputs: list[Form]) -> None:
        params = ctx.step_params
        structure = Path(str(params.get("structure_path") or "")).expanduser()
        repo = Path(str(params.get("proteinmpnn_path") or os.environ.get("OPERON_PROTEINMPNN_PATH") or "")).expanduser()
        model = str(params.get("model_name") or "v_48_020")
        chains = str(params.get("chains") or "")
        count = int(params.get("num_seq_per_target", 16))
        temperature = str(params.get("sampling_temp", "0.1"))
        seed = int(params.get("seed", 1))
        device = str(params.get("device") or "cpu")
        timeout = int(params.get("timeout", 3600))
        position_dim = str(params.get("position_dim") or "position")
        out_name = str(params.get("output", "recovery"))

        if not structure.is_file():
            raise StepError(f"proteinmpnn_native_recovery_scan: structure_path '{structure}' does not exist")
        runner = repo / "protein_mpnn_run.py"
        if not runner.is_file():
            raise StepError(
                f"proteinmpnn_native_recovery_scan: proteinmpnn_path '{repo}' does not contain protein_mpnn_run.py"
            )
        if model not in MODELS:
            raise StepError(f"proteinmpnn_native_recovery_scan: model_name must be one of {list(MODELS)}, got '{model}'")
        if not 2 <= count <= 500:
            raise StepError("proteinmpnn_native_recovery_scan: num_seq_per_target must be between 2 and 500")
        if not 0.0 < float(temperature) <= 2.0:
            raise StepError("proteinmpnn_native_recovery_scan: sampling_temp must be in (0, 2]")
        if seed < 0:
            raise StepError("proteinmpnn_native_recovery_scan: seed must not be negative")
        if device not in {"cpu", "cuda"}:
            raise StepError("proteinmpnn_native_recovery_scan: device must be 'cpu' or 'cuda'")
        weights = Path(str(params.get("weights_path") or repo / "vanilla_model_weights")).expanduser()
        if not weights.is_dir():
            raise StepError(f"proteinmpnn_native_recovery_scan: weights_path '{weights}' is not a directory")
        python = str(params.get("python_executable") or "") or sys.executable

        started = time.time()
        work = Path(tempfile.mkdtemp(prefix="operon-native-recovery-"))
        try:
            out_dir = work / "out"
            out_dir.mkdir()
            env = dict(os.environ)
            env["CUDA_VISIBLE_DEVICES"] = "" if device == "cpu" else env.get("CUDA_VISIBLE_DEVICES", "")
            command = [
                python,
                "protein_mpnn_run.py",
                "--pdb_path", structure.as_posix(),
                "--out_folder", out_dir.as_posix(),
                "--num_seq_per_target", str(count),
                "--sampling_temp", temperature,
                "--seed", str(seed),
                "--path_to_model_weights", weights.as_posix(),
                "--model_name", model,
                "--suppress_print", "1",
            ]
            if chains:
                command += ["--pdb_path_chains", chains]
            run = subprocess.run(
                command, cwd=str(repo), env=env, capture_output=True, text=True, timeout=timeout
            )
            if run.returncode != 0:
                tail = (run.stderr or run.stdout or "").strip().splitlines()[-3:]
                raise StepError(
                    f"proteinmpnn_native_recovery_scan: the designer failed with exit code {run.returncode}: "
                    + " | ".join(tail)
                )
            fasta = out_dir / "seqs" / f"{structure.stem}.fa"
            if not fasta.is_file():
                raise StepError(f"proteinmpnn_native_recovery_scan: the designer produced no FASTA at '{fasta}'")
            records = read_records(fasta)
        except subprocess.TimeoutExpired as exc:
            raise StepError(f"proteinmpnn_native_recovery_scan: the designer timed out after {timeout} s") from exc
        finally:
            shutil.rmtree(work, ignore_errors=True)

        native = records[0][1]
        designs = [sequence for _, sequence in records[1:]]
        rows = recovery_rows(native, designs)
        matrix = np.asarray(
            [[row["recovery"], row["dominant_frequency"], row["n_observed"]] for row in rows],
            dtype=np.float32,
        )
        labels = [str(row["position"]) for row in rows]
        out = Form(
            data=matrix,
            dims=[position_dim, "statistic"],
            labels={
                position_dim: {name: index for index, name in enumerate(labels)},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "native_sequence": native,
                "consensus": "".join(row["consensus"] for row in rows),
                "substitutions": [row["dominant_substitution"] for row in rows],
                "counts": [row["counts"] for row in rows],
                "model_name": model,
                "num_samples": len(designs),
                "sampling_temp": float(temperature),
                "seed": seed,
                "chains": chains,
                "structure_path": str(structure),
                "aa_order": AA_ORDER,
                "elapsed_seconds": round(time.time() - started, 3),
            },
        )
        out.validate()
        ctx[out_name] = out
        mean_recovery = float(np.mean(matrix[:, 0])) if len(matrix) else float("nan")
        self._export_data = {
            "num_samples": len(designs),
            "length": len(native),
            "mean_recovery": round(mean_recovery, 6),
            "native_sequence": native,
            "consensus": "".join(row["consensus"] for row in rows),
            "model_name": model,
        }
        print(
            f"[proteinmpnn_native_recovery_scan] {len(designs)} designs, length {len(native)}, "
            f"mean recovery {mean_recovery:.3f}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
