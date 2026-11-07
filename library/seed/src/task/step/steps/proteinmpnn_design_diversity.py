"""Diversity of ProteinMPNN designs: pairwise identity and clusters."""

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

MODELS = ("v_48_002", "v_48_010", "v_48_020", "v_48_030")


def pairwise_identities(sequences: list[str]) -> np.ndarray:
    """Fraction of identical positions for every design pair (symmetric, diagonal 1)."""

    if len(sequences) < 2:
        raise StepError("proteinmpnn_design_diversity: at least two designs are required")
    length = len(sequences[0])
    for design in sequences:
        if len(design) != length:
            raise StepError(
                "proteinmpnn_design_diversity: every design must match the native length "
                f"{length}, got {len(design)}"
            )
        if any(letter not in "ACDEFGHIKLMNPQRSTVWY" for letter in design):
            raise StepError(
                "proteinmpnn_design_diversity: designs must contain only standard amino acids"
            )
    count = len(sequences)
    identities = np.eye(count, dtype=np.float64)
    for left in range(count):
        for right in range(left + 1, count):
            matches = sum(1 for a, b in zip(sequences[left], sequences[right]) if a == b)
            identities[left, right] = identities[right, left] = matches / length
    return identities


def cluster_ids(identities: np.ndarray, threshold: float) -> list[int]:
    """Single-linkage clusters at the identity threshold (0-based, first-appearance order)."""

    count = len(identities)
    parent = list(range(count))

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[max(root_left, root_right)] = min(root_left, root_right)

    for left in range(count):
        for right in range(left + 1, count):
            if identities[left, right] >= threshold:
                union(left, right)
    roots = [find(index) for index in range(count)]
    order: dict[int, int] = {}
    return [order.setdefault(root, len(order)) for root in roots]


def diversity_rows(sequences: list[str], identities: np.ndarray, threshold: float) -> list[dict]:
    """Per-design mean/min identity, nearest neighbour and cluster membership."""

    clusters = cluster_ids(identities, threshold)
    count = len(sequences)
    rows: list[dict] = []
    for index in range(count):
        others = np.delete(identities[index], index)
        nearest = int(np.argmax(others)) if count > 1 else -1
        nearest_index = nearest + (1 if nearest >= index else 0) if nearest >= 0 else -1
        rows.append(
            {
                "mean_identity": float(others.mean()) if len(others) else 1.0,
                "min_identity": float(others.min()) if len(others) else 1.0,
                "nearest_identity": float(others.max()) if len(others) else 1.0,
                "nearest": f"design{nearest_index + 1:02d}" if nearest_index >= 0 else "",
                "cluster": clusters[index],
            }
        )
    return rows


def run_designer(params: dict, structure: Path, chain: str) -> list[str]:
    """Run the official ProteinMPNN runner and return the generated design sequences."""

    from src.task.step.steps.proteinmpnn_design import parse_design_fasta

    repo = Path(str(params.get("proteinmpnn_path") or "")).expanduser()
    runner = repo / "protein_mpnn_run.py"
    if not runner.is_file():
        raise StepError(
            f"proteinmpnn_design_diversity: {runner} does not exist; point proteinmpnn_path at the "
            "official ProteinMPNN checkout"
        )
    weights_text = str(params.get("weights_path") or "").strip()
    if weights_text:
        weights = Path(weights_text).expanduser()
    else:
        candidate = repo / "vanilla_model_weights"
        weights = candidate if candidate.is_dir() else None
    if weights is not None and not weights.exists():
        raise StepError(f"proteinmpnn_design_diversity: weights_path {weights} does not exist")

    model_name = str(params.get("model_name") or "v_48_020")
    count = int(params.get("num_seq_per_target") if params.get("num_seq_per_target") is not None else 16)
    temperature = str(params.get("sampling_temp") or "0.1")
    seed = int(params.get("seed") if params.get("seed") is not None else 1)
    device = str(params.get("device") or "cpu")
    timeout = int(params.get("timeout") if params.get("timeout") is not None else 1800)

    if model_name not in MODELS:
        raise StepError(
            f"proteinmpnn_design_diversity: model_name must be one of {', '.join(MODELS)}"
        )
    if count < 2:
        raise StepError("proteinmpnn_design_diversity: num_seq_per_target must be at least 2")
    if device not in {"cpu", "cuda"}:
        raise StepError("proteinmpnn_design_diversity: device must be 'cpu' or 'cuda'")

    python = str(params.get("python_executable") or "") or sys.executable
    out_dir = Path(tempfile.mkdtemp(prefix="operon-mpnn-diversity-"))
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
    ]
    if weights is not None:
        command.extend(["--path_to_model_weights", weights.as_posix()])
    if chain:
        command.extend(["--pdb_path_chains", chain])

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
                "proteinmpnn_design_diversity: the designer failed with exit code "
                f"{completed.returncode}: {' | '.join(tail)}"
            )
        fasta = out_dir / "seqs" / f"{structure.stem}.fa"
        if not fasta.is_file():
            raise StepError(f"proteinmpnn_design_diversity: the designer produced no FASTA at {fasta}")
        designs = parse_design_fasta(fasta)
    except subprocess.TimeoutExpired as error:
        raise StepError(
            f"proteinmpnn_design_diversity: the designer timed out after {timeout} s"
        ) from error
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)

    sequences = [str(record["sequence"]) for record in designs]
    if not sequences:
        raise StepError("proteinmpnn_design_diversity: the designer produced no designs")
    return sequences


class ProteinmpnnDesignDiversityStep(Step):
    """Pairwise identity and single-linkage clusters across ProteinMPNN designs."""

    provider = "operon-core"

    parameters_file = "proteinmpnn_design_diversity.ProteinmpnnDesignDiversityStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_design_diversity",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ProteinMPNN design diversity",
        "description": (
            "Run the official ProteinMPNN runner and quantify how diverse the sampled designs are: "
            "per-design mean/min/nearest identity and a single-linkage cluster identifier at an "
            "identity threshold."
        ),
        "category": "Machine Learning",
        "icon": "Stack",
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
            raise StepError("proteinmpnn_design_diversity: structure_path is required")
        structure = Path(structure_text).expanduser()
        if not structure.is_file():
            raise StepError(f"proteinmpnn_design_diversity: structure_path {structure} is not a file")
        threshold = float(
            params.get("identity_threshold") if params.get("identity_threshold") is not None else 0.9
        )
        if not 0.0 < threshold <= 1.0:
            raise StepError(
                "proteinmpnn_design_diversity: identity_threshold must be in (0, 1]"
            )
        design_dim = str(params.get("design_dim") or "design")
        out_name = str(params.get("output") or "diversity")

        sequences = run_designer(params, structure, str(params.get("chains") or ""))
        identities = pairwise_identities(sequences)
        rows = diversity_rows(sequences, identities, threshold)
        labels = [f"design{index + 1:02d}" for index in range(len(sequences))]

        data = np.asarray(
            [
                [row["mean_identity"], row["min_identity"], row["nearest_identity"], row["cluster"]]
                for row in rows
            ],
            dtype=np.float32,
        )
        out = Form(
            data=data,
            dims=[design_dim, "statistic"],
            labels={
                design_dim: {label: index for index, label in enumerate(labels)},
                "statistic": {
                    "mean_identity": 0,
                    "min_identity": 1,
                    "nearest_identity": 2,
                    "cluster": 3,
                },
            },
            info={
                "missing_code": float("nan"),
                "identity_threshold": threshold,
                "n_designs": len(sequences),
                "sequences": sequences,
                "nearest": [row["nearest"] for row in rows],
                "pairwise_identity": identities.astype(np.float32).tolist(),
                "mean_pairwise_identity": float(identities[np.triu_indices(len(sequences), 1)].mean()),
                "clusters": {label: float(row["cluster"]) for label, row in zip(labels, rows)},
            },
        )
        out.validate()
        ctx[out_name] = out
        clusters = sorted({row["cluster"] for row in rows})
        self._export_data = {
            "n_designs": len(sequences),
            "identity_threshold": threshold,
            "n_clusters": len(clusters),
            "mean_pairwise_identity": round(float(identities[np.triu_indices(len(sequences), 1)].mean()), 6),
            "min_pairwise_identity": round(float(identities[np.triu_indices(len(sequences), 1)].min()), 6),
            "sequences": sequences,
        }
        print(
            f"[proteinmpnn_design_diversity] {len(sequences)} designs, {len(clusters)} clusters, "
            f"mean pairwise identity {identities[np.triu_indices(len(sequences), 1)].mean():.4f}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
