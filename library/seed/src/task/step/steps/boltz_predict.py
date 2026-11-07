"""Boltz-2 co-folding prediction wrapper."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._native_results import output_directory, remember_native, result_file


import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_YAML_PROTEIN = "version: 1\nsequences:\n  - protein:\n      id: {chain}\n      sequence: {sequence}\n"
_YAML_LIGAND = "  - ligand:\n      id: {chain}\n      smiles: \"{smiles}\"\n"


def write_yaml(path: Path, sequence: str, *, chain: str = "A", ligand_smiles: str = "", ligand_chain: str = "B", affinity: bool = False, msa_mode: str = "server") -> None:
    """Write a Boltz-2 input YAML for one protein and an optional ligand."""

    clean = "".join(residue for residue in str(sequence).upper() if residue.isalpha())
    if not clean:
        raise StepError("boltz_predict: the protein sequence is empty")
    body = _YAML_PROTEIN.format(chain=chain, sequence=clean)
    if msa_mode == "empty":
        body += "      msa: empty\n"
    if ligand_smiles:
        body += _YAML_LIGAND.format(chain=ligand_chain, smiles=str(ligand_smiles).strip())
    if affinity:
        if not ligand_smiles:
            raise StepError("boltz_predict: affinity requires a ligand_smiles")
        body += f"properties:\n  - affinity:\n      binder: {ligand_chain}\n"
    path.write_text(body)


def boltz_command(
    binary: str,
    yaml_path: Path,
    out_dir: Path,
    *,
    model: str = "boltz2",
    use_msa_server: bool = True,
    device: str = "cpu",
    output_format: str = "pdb",
    sampling_steps: int = 200,
    diffusion_samples: int = 1,
    num_workers: int = 1,
    no_kernels: bool = False,
    extra: str = "",
) -> list[str]:
    """Build the official `boltz predict` invocation."""

    accelerator = "gpu" if str(device).lower() in {"cuda", "gpu"} else "cpu"
    command = [
        binary,
        "predict",
        str(yaml_path),
        "--out_dir",
        str(out_dir),
        "--model",
        model,
        "--accelerator",
        accelerator,
        "--output_format",
        output_format,
        "--sampling_steps",
        str(sampling_steps),
        "--diffusion_samples",
        str(diffusion_samples),
        "--num_workers",
        str(num_workers),
    ]
    if use_msa_server:
        command.append("--use_msa_server")
    if no_kernels:
        command.append("--no_kernels")
    if extra.strip():
        command.extend(extra.split())
    return command


def find_outputs(out_dir: Path) -> dict:
    """Locate the first prediction structure and confidence JSON."""

    pdbs = sorted(out_dir.rglob("*.pdb"))
    jsons = sorted(out_dir.rglob("confidence_*.json"))
    affinities = sorted(out_dir.rglob("affinity_*.json"))
    if not pdbs:
        raise StepError(f"boltz_predict: no predicted structure under {out_dir}")
    if not jsons:
        raise StepError(f"boltz_predict: no confidence JSON under {out_dir}")
    return {"pdb": pdbs[0], "confidence": jsons[0], "affinity": affinities[0] if affinities else None}


def parse_confidence(path: Path) -> dict:
    payload = json.loads(path.read_text())
    def first(*keys):
        for key in keys:
            for holder in (payload, payload.get("confidence", {}) if isinstance(payload.get("confidence"), dict) else {}):
                if isinstance(holder, dict) and key in holder:
                    return float(holder[key])
        return float("nan")
    return {
        "confidence_score": first("confidence_score"),
        "ptm": first("ptm"),
        "iptm": first("iptm"),
        "complex_plddt": first("complex_plddt"),
        "complex_iplddt": first("complex_iplddt"),
    }


def parse_affinity(path: Path | None) -> dict:
    if path is None:
        return {"affinity_pred_value": float("nan"), "affinity_probability_binary": float("nan")}
    payload = json.loads(path.read_text())
    return {
        "affinity_pred_value": float(payload.get("affinity_pred_value", payload.get("affinity", {}).get("affinity_pred_value", "nan"))),
        "affinity_probability_binary": float(payload.get("affinity_probability_binary", payload.get("affinity", {}).get("affinity_probability_binary", "nan"))),
    }


class BoltzPredictStep(Step):
    provider = "operon-core"
    parameters_file = "boltz_predict.BoltzPredictStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "boltz_predict",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Boltz co-folding prediction",
        "category": "Machine Learning",
        "icon": "Brain",
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}], "labels": [], "parallel": [], "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
            "outputs": [],
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory", "environment": "boltz"},
        "inputs_arity": 1,
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        from src.task.step.steps._sequence_common import decode_sequences

        sequences = decode_sequences(inputs[0], params["sequence_dim"], params["position_dim"])
        if len(sequences) != 1:
            raise StepError(f"boltz_predict: expected exactly one protein sequence, got {len(sequences)}")
        binary = str(params.get("boltz_path") or "boltz")
        resolved = shutil.which(binary) or (binary if Path(binary).is_file() else "")
        if not resolved:
            raise StepError("boltz_predict: 'boltz' was not found on PATH; install it with 'python -m pip install boltz' and download the weights")
        workdir = Path(tempfile.mkdtemp(prefix="boltz_"))
        yaml_path = workdir / "input.yaml"
        msa_mode = str(params.get("msa_mode", "server"))
        write_yaml(
            yaml_path,
            sequences[0],
            chain=str(params.get("protein_chain", "A")),
            ligand_smiles=str(params.get("ligand_smiles", "")),
            ligand_chain=str(params.get("ligand_chain", "B")),
            affinity=bool(params.get("affinity", False)),
            msa_mode=msa_mode,
        )
        out_dir = workdir / "out"
        command = boltz_command(
            resolved,
            yaml_path,
            out_dir,
            model=str(params.get("model", "boltz2")),
            use_msa_server=bool(params.get("use_msa_server", True)) and msa_mode == "server",
            device=str(params.get("device", "cpu")),
            output_format=str(params.get("output_format", "pdb")),
            sampling_steps=int(params.get("sampling_steps", 200)),
            diffusion_samples=int(params.get("diffusion_samples", 1)),
            num_workers=int(params.get("num_workers", 1)),
            no_kernels=bool(params.get("no_kernels", False)),
            extra=str(params.get("extra_args", "")),
        )
        cache_dir = str(params.get("cache_dir", "") or "")
        if cache_dir:
            command.extend(["--cache", cache_dir])
        if str(resolved).lower().endswith(".py"):
            command = [sys.executable] + command
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=int(params.get("timeout_seconds", 3600)), env={**__import__("os").environ, "PYTHONUNBUFFERED": "1"})
        except subprocess.TimeoutExpired:
            raise StepError(f"boltz_predict: Boltz timed out after {params.get('timeout_seconds', 3600)} s") from None
        if completed.returncode != 0:
            tail = ((completed.stderr or completed.stdout).strip().splitlines() or [""])[-1]
            raise StepError(f"boltz_predict: Boltz failed with exit code {completed.returncode}: {tail}")
        outputs = find_outputs(out_dir)
        directory = output_directory(ctx, "boltz")
        pdb_path = directory / "prediction.pdb"
        shutil.copyfile(outputs["pdb"], pdb_path)
        outputs["pdb"] = pdb_path
        confidence = parse_confidence(outputs["confidence"])
        affinity = parse_affinity(outputs["affinity"])
        values = [confidence["confidence_score"], confidence["ptm"], confidence["iptm"], confidence["complex_plddt"], affinity["affinity_pred_value"], affinity["affinity_probability_binary"]]
        data = np.asarray([values], dtype=np.float32)
        out_name = str(params.get("output", "structure"))
        ctx[out_name] = Form(
            data=data,
            dims=["model", "statistic"],
            labels={"model": {"model_0": 0}, "statistic": {"confidence_score": 0, "ptm": 1, "iptm": 2, "complex_plddt": 3, "affinity_pred_value": 4, "affinity_probability_binary": 5}},
            info={"missing_code": np.nan, "pdb": str(outputs["pdb"]), "confidence_json": str(outputs["confidence"]), "affinity_json": str(outputs["affinity"]) if outputs["affinity"] else "", "model": str(params.get("model", "boltz2")), "ligand": bool(params.get("ligand_smiles", "")), "sequence": sequences[0]},
        )
        result_files = [result_file("structure", pdb_path, "pdb", "Boltz prediction")]
        remember_native(ctx, out_name, result_files)
        self._export_data = {"pdb": str(outputs["pdb"]), "confidence": confidence, "result_files": result_files}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
