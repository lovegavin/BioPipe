"""ProteinMPNN score-only evaluation of structure/sequence pairs."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

MODELS = ("v_48_002", "v_48_010", "v_48_020", "v_48_030")
STATISTICS = ("mean_nll", "global_nll", "nll_std", "n_residues")


def parse_fasta(path: Path) -> list[tuple[str, str]]:
    """Read a ProteinMPNN scoring FASTA into (name, sequence) pairs.

    Chain separators (``/``) are removed exactly as the official
    ``parse_fasta(..., omit=["/"])`` helper does.
    """
    records: list[tuple[str, str]] = []
    name: str | None = None
    chunks: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            if name is not None:
                records.append((name, "".join(chunks)))
            header = line[1:].strip()
            name = header.split()[0] if header else f"sequence_{len(records) + 1}"
            chunks = []
        elif name is None:
            raise StepError(
                "proteinmpnn_score: fasta_path must start with a '>' header "
                f"before the sequence, got {line!r}"
            )
        else:
            chunks.append(line.replace("/", ""))
    if name is not None:
        records.append((name, "".join(chunks)))
    if not records:
        raise StepError("proteinmpnn_score: fasta_path contains no records")
    for record_name, sequence in records:
        if not sequence:
            raise StepError(
                f"proteinmpnn_score: FASTA record '{record_name}' is empty"
            )
    names = [record_name for record_name, _ in records]
    if len(names) != len(set(names)):
        raise StepError(
            "proteinmpnn_score: FASTA record names must be unique so the rows "
            "keep their identity"
        )
    return records


def score_files(out_dir: Path, structure: Path, count: int) -> list[Path]:
    """Return the expected ``score_only`` npz files for ``count`` sequences."""
    folder = out_dir / "score_only"
    files = [folder / f"{structure.stem}_fasta_{index}.npz" for index in range(1, count + 1)]
    if count == 1:
        # The official runner appends .npz through numpy.savez.
        single = files[0]
        if not single.is_file():
            fallback = folder / f"{structure.stem}_fasta_1"
            if fallback.is_file():
                files[0] = fallback
    return files


def summarize(npz: Path) -> tuple[float, float, float, int]:
    """Return (mean_nll, global_nll, nll_std, n_residues) from a score npz."""
    with np.load(npz, allow_pickle=True) as archive:
        scores = np.asarray(archive["score"], dtype=np.float64).ravel()
        globals_ = np.asarray(archive["global_score"], dtype=np.float64).ravel()
        sequence = str(archive["seq_str"]) if "seq_str" in archive else ""
    if scores.size == 0:
        raise StepError(f"proteinmpnn_score: '{npz}' holds no scores")
    return (
        float(scores.mean()),
        float(globals_.mean()) if globals_.size else float("nan"),
        float(scores.std()),
        int(len(sequence)),
    )


class ProteinmpnnScoreStep(Step):
    provider = 'operon-core'
    """ProteinMPNN negative log-likelihood for a structure/sequence pair."""
    parameters_file = 'proteinmpnn_score.ProteinmpnnScoreStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'proteinmpnn_score',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'ProteinMPNN sequence score',
     'category': 'Machine Learning',
     'icon': 'Brain',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True,
                                         'info': {'missing_code': {'type': ['number', 'null']}}}}},
     'resources': {'memory_modes': ['full'],
                   'supports_cuda': True,
                   'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.24'],
     'dependency_imports': [],
     'inputs_arity': 0,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Score a structure/sequence pair with the official ProteinMPNN runner in --score_only mode; returns mean and global negative log-likelihood per sequence.'}

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        structure_path = Path(
            str(params.get("structure_path", "") or "").strip()
        ).expanduser()
        fasta_path = Path(
            str(params.get("fasta_path", "") or "").strip()
        ).expanduser()
        proteinmpnn_path = Path(
            str(params.get("proteinmpnn_path", "") or "").strip()
            or os.environ.get("OPERON_PROTEINMPNN_PATH", "")
        ).expanduser()
        weights_text = str(params.get("weights_path", "") or "").strip()
        python_executable = str(params.get("python_executable", "") or "").strip()
        model_name = str(params.get("model_name", "v_48_020") or "v_48_020").strip()
        chains = str(params.get("chains", "") or "").strip()
        seed = int(params.get("seed", 1))
        device = str(params.get("device", "cpu") or "cpu").strip().lower()
        timeout = float(params.get("timeout_seconds", 1800.0))
        out_name = params.get("output", self.name)

        if not structure_path.is_file():
            raise StepError(
                f"proteinmpnn_score: structure_path '{structure_path}' is not a "
                "file"
            )
        if structure_path.suffix.lower() not in (".pdb", ".ent"):
            raise StepError(
                "proteinmpnn_score: structure_path must be a .pdb file "
                "(ProteinMPNN needs atom names)"
            )
        if not fasta_path.is_file():
            raise StepError(
                f"proteinmpnn_score: fasta_path '{fasta_path}' is not a file"
            )
        if not proteinmpnn_path.is_dir():
            raise StepError(
                f"proteinmpnn_score: proteinmpnn_path '{proteinmpnn_path}' is "
                "not a directory (set OPERON_PROTEINMPNN_PATH or the "
                "proteinmpnn_path parameter)"
            )
        runner = proteinmpnn_path / "protein_mpnn_run.py"
        if not runner.is_file():
            raise StepError(
                f"proteinmpnn_score: '{runner}' does not exist; point "
                "proteinmpnn_path at the official ProteinMPNN checkout"
            )
        if model_name not in MODELS:
            raise StepError(
                f"proteinmpnn_score: model_name must be one of {list(MODELS)}"
            )
        weights_path = (
            Path(weights_text).expanduser()
            if weights_text
            else proteinmpnn_path / "vanilla_model_weights"
        )
        weight_file = weights_path / f"{model_name}.pt"
        if not weight_file.is_file():
            raise StepError(
                f"proteinmpnn_score: weights '{weight_file}' not found; set "
                "weights_path to the directory holding v_48_*.pt"
            )
        if device not in ("cpu", "cuda"):
            raise StepError("proteinmpnn_score: device must be 'cpu' or 'cuda'")

        records = parse_fasta(fasta_path)
        command_python = python_executable or sys.executable
        out_dir = Path(tempfile.mkdtemp(prefix="operon-mpnn-score-"))
        started = time.monotonic()
        try:
            command = [
                command_python,
                runner.as_posix(),
                "--pdb_path", structure_path.as_posix(),
                "--path_to_fasta", fasta_path.as_posix(),
                "--out_folder", out_dir.as_posix(),
                "--score_only", "1",
                "--seed", str(seed),
                "--path_to_model_weights", weights_path.as_posix(),
                "--model_name", model_name,
                "--suppress_print", "1",
            ]
            if chains:
                command.extend(["--pdb_path_chains", chains])
            environment = dict(os.environ)
            if device == "cpu":
                environment["CUDA_VISIBLE_DEVICES"] = ""
            else:
                environment.pop("CUDA_VISIBLE_DEVICES", None)
            completed = subprocess.run(
                command,
                cwd=str(proteinmpnn_path),
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if completed.returncode != 0:
                tail = (completed.stderr or completed.stdout or "").strip()
                raise StepError(
                    "proteinmpnn_score: protein_mpnn_run.py failed with exit "
                    f"code {completed.returncode}: {tail[-800:]}"
                )
            files = score_files(out_dir, structure_path, len(records))
            missing = [path.name for path in files if not path.is_file()]
            if missing:
                raise StepError(
                    "proteinmpnn_score: the runner produced no score file(s) "
                    f"{missing}; stdout tail: "
                    f"{(completed.stdout or '').strip()[-400:]}"
                )
            rows = [list(summarize(path)) for path in files]
            elapsed = time.monotonic() - started
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)

        data = np.asarray(rows, dtype=np.float32)
        out = Form(
            data=data,
            dims=["sequence", "statistic"],
            labels={
                "sequence": {
                    name: position
                    for position, (name, _) in enumerate(records)
                },
                "statistic": {
                    name: position for position, name in enumerate(STATISTICS)
                },
            },
            info={
                "missing_code": np.nan,
                "sequences": [sequence for _, sequence in records],
                "structure_path": str(structure_path),
                "model_name": model_name,
                "chains": chains or "all",
                "device": device,
                "elapsed_seconds": round(elapsed, 3),
                "metric": "negative_log_likelihood",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_sequences": len(records),
            "mean_nll": float(data[:, 0].mean()),
            "model_name": model_name,
            "structure_path": str(structure_path),
            "elapsed_seconds": round(elapsed, 3),
        }
        print(
            f"[proteinmpnn_score] {len(records)} sequence(s) from "
            f"{structure_path.name} ({model_name}, {device}, {elapsed:.1f}s)"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
