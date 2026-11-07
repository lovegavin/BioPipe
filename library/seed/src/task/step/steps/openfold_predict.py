"""openfold_predict: OpenFold (AlphaFold-2) structure prediction."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.reader import read_source
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences
from src.task.step.steps._native_results import output_directory, remember_native, result_file


def write_fasta(path: Path, sequence: str, header: str = "query") -> None:
    """Write a single-sequence FASTA file."""

    path.write_text(f">{header}\n{sequence}\n")


def write_alignment(directory: Path, sequence: str, tag: str = "query") -> Path:
    """Write a single-sequence A3M alignment (no homologous hits)."""

    folder = directory / tag
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "uniref90_hits.a3m"
    target.write_text(f">{tag}\n{sequence}\n")
    return folder


def openfold_command(
    python_executable: str,
    run_script: Path,
    fasta_dir: Path,
    template_dir: Path,
    align_dir: Path,
    out_dir: Path,
    *,
    params: Path,
    preset: str = "model_1_ptm",
    device: str = "cpu",
    skip_relaxation: bool = True,
) -> list[str]:
    """Build the official run_pretrained_openfold.py command line."""

    command = [
        python_executable or sys.executable,
        run_script.as_posix(),
        fasta_dir.as_posix(),
        template_dir.as_posix(),
        "--use_precomputed_alignments",
        align_dir.as_posix(),
        "--output_dir",
        out_dir.as_posix(),
        "--config_preset",
        preset,
        "--openfold_checkpoint_path",
        params.as_posix(),
        "--model_device",
        device,
    ]
    if skip_relaxation:
        command.append("--skip_relaxation")
    return command


def find_prediction(out_dir: Path) -> Path:
    """Locate the newest unrelaxed prediction PDB."""

    candidates = sorted(out_dir.rglob("*_unrelaxed.pdb"), key=lambda item: item.stat().st_mtime)
    if not candidates:
        raise StepError(f"openfold_predict: no prediction PDB was written under {out_dir}")
    return candidates[-1]


class OpenfoldPredictStep(Step):
    provider = "operon-core"
    parameters_file = "openfold_predict.OpenfoldPredictStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "openfold_predict",
        "version": "1.0.0",
        "kind": "operator",
        "title": "OpenFold 结构预测",
        "description": (
            "Run OpenFold (AlphaFold-2 weights) inference for one protein sequence "
            "with precomputed single-sequence alignments and return the predicted "
            "structure with pLDDT statistics."
        ),
        "category": "Machine Learning",
        "icon": "Brain",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["torch"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        sequences = decode_sequences(inputs[0], str(params.get("sequence_dim", "sequence")), str(params.get("position_dim", "position")))
        if len(sequences) != 1:
            raise StepError(f"openfold_predict: expected exactly one sequence, got {len(sequences)}")
        sequence = sequences[0].replace("X", "").strip().upper()
        if len(sequence) < 10:
            raise StepError("openfold_predict: the sequence must hold at least 10 residues")
        repo = Path(str(params.get("openfold_path", ""))).expanduser()
        script = repo / "run_pretrained_openfold.py"
        if not script.is_file():
            raise StepError("openfold_predict: openfold_path must point at an OpenFold checkout containing run_pretrained_openfold.py")
        weights = Path(str(params.get("params_path", ""))).expanduser()
        if not weights.is_file():
            raise StepError(f"openfold_predict: params_path {weights} is not a file")

        workdir = Path(tempfile.mkdtemp(prefix="openfold_"))
        fasta_dir = workdir / "fasta"
        fasta_dir.mkdir()
        write_fasta(fasta_dir / "query.fasta", sequence)
        align_dir = workdir / "align"
        template_dir = workdir / "templates"
        out_dir = workdir / "out"
        template_dir.mkdir(parents=True)
        (template_dir / "dummy.cif").write_text("data_dummy\n")
        align_source = str(params.get("alignment_dir", "")).strip()
        if align_source:
            align_dir = Path(align_source).expanduser()
            if not align_dir.is_dir():
                raise StepError(f"openfold_predict: alignment_dir {align_dir} is not a directory")
            source_label = "provided"
        else:
            write_alignment(align_dir, sequence)
            source_label = "single_sequence"
        template_source = str(params.get("template_dir", "")).strip()
        if template_source:
            template_dir = Path(template_source).expanduser()
            if not template_dir.is_dir():
                raise StepError(f"openfold_predict: template_dir {template_dir} is not a directory")

        command = openfold_command(
            str(params.get("python_executable", "")),
            script,
            fasta_dir,
            template_dir,
            align_dir,
            out_dir,
            params=weights,
            preset=str(params.get("config_preset", "model_1_ptm")),
            device=str(params.get("device", "cpu")),
            skip_relaxation=bool(params.get("skip_relaxation", True)),
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = str(repo) + ((os.pathsep + env["PYTHONPATH"]) if env.get("PYTHONPATH") else "")
        if str(params.get("device", "cpu")) == "cpu":
            env["CUDA_VISIBLE_DEVICES"] = ""
        timeout = int(params.get("timeout_seconds", 3600))
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env)
        except subprocess.TimeoutExpired as exc:
            raise StepError(f"openfold_predict: inference timed out after {timeout} s") from exc
        except FileNotFoundError as exc:
            raise StepError(f"openfold_predict: the Python interpreter was not found: {exc}") from exc
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-6:]
            raise StepError("openfold_predict: inference failed with exit code " + str(completed.returncode) + ": " + " | ".join(tail))

        prediction = find_prediction(out_dir)
        directory = output_directory(ctx, "openfold")
        native_pdb = directory / "prediction.pdb"
        shutil.copyfile(prediction, native_pdb)
        prediction = native_pdb
        form = read_source(str(prediction), ["atom", "field"], {"atom": "auto", "field": "builtin"})
        fields = form.labels.get("field", {})
        plddt = np.zeros(0)
        if "bfactor" in fields:
            plddt = np.asarray(form.data[:, fields["bfactor"]], dtype=np.float64)
        plddt = plddt[np.isfinite(plddt)]
        out_name = str(params.get("output", "structure"))
        form.info.update({"plddt_mean": (float(plddt.mean()) if plddt.size else 0.0), "model": "openfold", "config_preset": str(params.get("config_preset", "model_1_ptm"))})
        result_files = [result_file("structure", prediction, "pdb", "OpenFold prediction")]
        remember_native(ctx, out_name, result_files)
        ctx[out_name] = form
        self._export_data = {
            "result_files": result_files,
            "plddt_mean": float(plddt.mean()) if plddt.size else 0.0,
            "plddt_min": float(plddt.min()) if plddt.size else 0.0,
            "plddt_max": float(plddt.max()) if plddt.size else 0.0,
            "prediction": prediction.as_posix(),
            "sequence": sequence,
            "n_atoms": int(form.data.shape[0]),
            "config_preset": str(params.get("config_preset", "model_1_ptm")),
            "alignment": source_label,
            "params_path": weights.as_posix(),
            "openfold_path": repo.as_posix(),
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
