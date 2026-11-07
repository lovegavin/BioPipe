"""boltz_complex_confidence: Boltz-2 complex prediction with confidence parsing."""

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
from src.core.forms import Form
from src.reader import read_source
from src.task.step.base import Step
from src.task.step.steps._protein_common import column_index, residue_labels
from src.task.step.steps._sequence_common import decode_sequences
from src.task.step.steps._native_results import output_directory, remember_native, result_file

_YAML = """version: 1
sequences:
  - protein:
      id: {chain}
      sequence: {sequence}
      msa: empty
"""


def write_yaml(path: Path, chain: str, sequence: str) -> None:
    """Write a minimal Boltz complex specification."""

    path.write_text(_YAML.format(chain=chain, sequence=sequence))


def complex_yaml(chains: list[tuple[str, str]]) -> str:
    """Build one YAML document listing every chain once."""

    body = "version: 1\nsequences:\n"
    for chain, sequence in chains:
        body += "  - protein:\n"
        body += f"      id: {chain}\n"
        body += f"      sequence: {sequence}\n"
        body += "      msa: empty\n"
    return body


def boltz_command(binary: str, yaml_path: Path, out_dir: Path, *, model: str, device: str, sampling_steps: int, diffusion_samples: int, cache_dir: str = "") -> list[str]:
    """Build the Boltz prediction command."""

    launcher = [sys.executable, binary] if binary.lower().endswith(".py") else [binary]
    command = [
        *launcher,
        "predict",
        str(yaml_path),
        "--out_dir",
        str(out_dir),
        "--model",
        model,
        "--accelerator",
        "cpu" if device == "cpu" else "gpu",
        "--output_format",
        "pdb",
        "--sampling_steps",
        str(sampling_steps),
        "--diffusion_samples",
        str(diffusion_samples),
        "--num_workers",
        "1",
        "--no_kernels",
    ]
    if cache_dir:
        command.extend(["--cache", cache_dir])
    return command


def run_boltz(binary: str, yaml_path: Path, out_dir: Path, *, model: str, device: str, sampling_steps: int, diffusion_samples: int, cache_dir: str = "", timeout: int = 3600) -> None:
    """Run Boltz and surface a readable error on failure."""

    command = boltz_command(binary, yaml_path, out_dir, model=model, device=device, sampling_steps=sampling_steps, diffusion_samples=diffusion_samples, cache_dir=cache_dir)
    env = dict(os.environ)
    env["CUDA_VISIBLE_DEVICES"] = "" if device == "cpu" else env.get("CUDA_VISIBLE_DEVICES", "0")
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired as exc:
        raise StepError(f"boltz_complex_confidence: Boltz timed out after {timeout} s") from exc
    except FileNotFoundError as exc:
        raise StepError("boltz_complex_confidence: the Boltz executable was not found; install it with 'python -m pip install boltz'") from exc
    if completed.returncode != 0:
        tail = " ".join((completed.stderr or completed.stdout or "").strip().splitlines()[-3:])
        raise StepError(f"boltz_complex_confidence: Boltz failed with exit code {completed.returncode}: {tail[:400]}")


def find_outputs(out_dir: Path) -> tuple[Path, Path | None]:
    """Locate the first prediction PDB and confidence JSON."""

    pdbs = sorted(out_dir.rglob("*_model_0.pdb"))
    if not pdbs:
        raise StepError(f"boltz_complex_confidence: no prediction PDB under {out_dir}")
    json_path = pdbs[0].with_name(pdbs[0].name.replace("_model_0.pdb", "_confidence_model_0.json"))
    if not json_path.is_file():
        candidates = sorted(pdbs[0].parent.glob("confidence_*.json"))
        json_path = candidates[0] if candidates else None
    return pdbs[0], json_path


def parse_confidence(path: Path) -> dict:
    """Read the confidence JSON into plain floats."""

    data = json.loads(Path(path).read_text())
    pair = data.get("pair_chains_iptm") or {}
    first = pair.get("0", {})
    chain_pair = first.get("1", first.get("0", 0.0))
    return {
        "confidence_score": float(data.get("confidence_score", 0.0)),
        "ptm": float(data.get("ptm", 0.0)),
        "iptm": float(data.get("iptm", 0.0)),
        "complex_plddt": float(data.get("complex_plddt", 0.0)),
        "complex_iplddt": float(data.get("complex_iplddt", 0.0)),
        "complex_pde": float(data.get("complex_pde", 0.0)),
        "chain_pair_iptm": float(chain_pair),
    }


def interface_rows(pdb_path: Path, *, cutoff: float = 8.0) -> tuple[list[str], list[str]]:
    """Return per-residue labels and a cross-chain interface mask."""

    form = read_source(pdb_path, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"})
    labels = residue_labels(form, "field")
    chain = np.array([str(label).split(":")[0] for label in labels])
    elements = np.array([str(value) for value in form.data[:, column_index(form, "field", "element")]])
    coords = np.array([[value for value in form.data[row][[column_index(form, "field", key) for key in ("x", "y", "z")]]] for row in range(form.data.shape[0])], dtype=float)
    heavy = elements != "H"
    first = chain == "A"
    second = chain != "A"
    order = list(dict.fromkeys(labels))
    is_interface = {label: False for label in order}
    for i in np.where(heavy & first)[0]:
        distances = np.linalg.norm(coords[heavy & second] - coords[i], axis=1)
        if distances.size and distances.min() <= cutoff:
            is_interface[labels[i]] = True
            nearest = np.where(heavy & second)[0][int(distances.argmin())]
            is_interface[labels[nearest]] = True
    return order, [bool(is_interface[label]) for label in order]


def plddt_from_pdb(pdb_path: Path) -> np.ndarray:
    """Read per-atom B-factors (pLDDT) from a predicted PDB."""

    values = []
    for line in Path(pdb_path).read_text().splitlines():
        if line.startswith(("ATOM", "HETATM")):
            values.append(float(line[60:66]))
    return np.asarray(values, dtype=float)


def summarise(pdb_path: Path, confidence: dict, *, cutoff: float) -> tuple[list[str], np.ndarray, list[bool], dict]:
    """Combine confidence fields with per-residue interface annotation."""

    order, interface = interface_rows(pdb_path, cutoff=cutoff)
    bfactors = plddt_from_pdb(pdb_path)
    per_residue = {}
    index = 0
    labels = residue_labels(read_source(pdb_path, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"}), "field")
    for label, bfactor in zip(labels, bfactors[: len(labels)]):
        per_residue.setdefault(label, []).append(bfactor)
    mean_plddt = np.array([float(np.mean(per_residue[label])) if label in per_residue else np.nan for label in order])
    interface_values = [value for value, flag in zip(mean_plddt, interface) if flag and np.isfinite(value)]
    summary = dict(confidence)
    summary["n_residues"] = len(order)
    summary["n_interface"] = int(sum(interface))
    summary["mean_interface_plddt"] = float(np.mean(interface_values)) if interface_values else 0.0
    summary["mean_plddt"] = float(np.nanmean(mean_plddt)) if np.isfinite(mean_plddt).any() else 0.0
    return order, mean_plddt, interface, summary


class BoltzComplexConfidenceStep(Step):
    provider = "operon-core"
    parameters_file = "boltz_complex_confidence.BoltzComplexConfidenceStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "boltz_complex_confidence",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Boltz complex prediction confidence",
        "description": "Predict a two-chain protein complex with Boltz and report per-residue confidence plus interface confidence.",
        "category": "Machine Learning",
        "icon": "ShareNetwork",
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
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory", "environment": "boltz"},
        "dependencies": [],
        "dependency_imports": ["boltz"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        sequences = decode_sequences(inputs[0], params.get("sequence_dim", "sequence"), params.get("position_dim", "position"))
        if len(sequences) != 2:
            raise StepError(f"boltz_complex_confidence: expected exactly two sequences (chains A and B), got {len(sequences)}")
        binary = str(params.get("boltz_path") or "boltz")
        resolved = shutil.which(binary) or (binary if Path(binary).is_file() else "")
        if not resolved:
            raise StepError("boltz_complex_confidence: 'boltz' was not found on PATH; install it with 'python -m pip install boltz'")
        device = str(params.get("device", "cpu"))
        if device not in ("cpu", "cuda"):
            raise StepError("boltz_complex_confidence: device must be 'cpu' or 'cuda'")
        workdir = Path(tempfile.mkdtemp(prefix="boltz_cx_"))
        yaml_path = workdir / "complex.yaml"
        yaml_path.write_text(complex_yaml([("A", sequences[0]), ("B", sequences[1])]))
        out_dir = workdir / "out"
        run_boltz(
            resolved,
            yaml_path,
            out_dir,
            model=str(params.get("model", "boltz2")),
            device=device,
            sampling_steps=int(params.get("sampling_steps", 50)),
            diffusion_samples=int(params.get("diffusion_samples", 1)),
            cache_dir=str(params.get("cache_dir", "") or ""),
            timeout=int(params.get("timeout_seconds", 3600)),
        )
        pdb_path, json_path = find_outputs(out_dir)
        directory = output_directory(ctx, "boltz_complex")
        native_pdb = directory / "prediction.pdb"
        shutil.copyfile(pdb_path, native_pdb)
        pdb_path = native_pdb
        confidence = parse_confidence(json_path) if json_path is not None else {"confidence_score": 0.0, "ptm": 0.0, "iptm": 0.0, "complex_plddt": 0.0, "complex_iplddt": 0.0, "complex_pde": 0.0, "chain_pair_iptm": 0.0}
        cutoff = float(params.get("interface_cutoff", 8.0))
        order, mean_plddt, interface, summary = summarise(pdb_path, confidence, cutoff=cutoff)

        report_dim = str(params.get("report_dim", "residue"))
        labels = {report_dim: {label: index for index, label in enumerate(order)}}
        data = np.array([[value, 1.0 if flag else 0.0] for value, flag in zip(mean_plddt, interface)], dtype=np.float32)
        out = params.get("output", "confidence")
        info = {
            "missing_code": np.nan,
            "chains": ["A", "B"],
            "sequences": sequences,
            "model": str(params.get("model", "boltz2")),
            "interface_cutoff": cutoff,
            **summary,
        }
        ctx[out] = Form(
            data=data,
            dims=[report_dim, "statistic"],
            labels={**labels, "statistic": {"plddt": 0, "is_interface": 1}},
            info=info,
        )
        result_files = [result_file("structure", pdb_path, "pdb", "Boltz complex prediction")]
        remember_native(ctx, str(out), result_files)
        self._export_data = {
            "output": out,
            "result_files": result_files,
            "iptm": float(summary.get("chain_pair_iptm", 0.0)),
            "n_interface": int(summary.get("n_interface", 0)),
            "mean_interface_plddt": float(summary.get("mean_interface_plddt", 0.0)),
        }
        return ctx[out]

    def export(self, ctx):
        return getattr(self, "_export_data", {})
