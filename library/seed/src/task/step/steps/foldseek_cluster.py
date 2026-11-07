"""foldseek_cluster: structural clustering with Foldseek."""

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
from src.task.step.base import Step

_SUFFIXES = (".pdb", ".cif", ".ent", ".mmcif")


def collect_structures(directory: str, paths: str = "") -> list[Path]:
    """Collect structure files from an explicit list or a directory."""

    items: list[Path] = []
    if paths.strip():
        items = [Path(part.strip()).expanduser() for part in paths.replace(";", ",").split(",") if part.strip()]
    elif directory.strip():
        root = Path(directory).expanduser()
        if not root.is_dir():
            raise StepError(f"foldseek_cluster: structure_dir {root} is not a directory")
        items = sorted(path for path in root.iterdir() if path.suffix.lower() in _SUFFIXES and path.is_file())
    if not items:
        raise StepError("foldseek_cluster: no structure file was found; set structure_dir or structure_paths")
    for item in items:
        if not item.is_file():
            raise StepError(f"foldseek_cluster: {item} is not a file")
    if len(items) < 2:
        raise StepError("foldseek_cluster: at least two structures are required for clustering")
    return items


def _binary(name: str) -> list[str]:
    return [sys.executable, name] if name.lower().endswith(".py") else [name]


def run_cluster(binary: str, structures: list[Path], *, tmscore_threshold: float, coverage: float, timeout: int = 600) -> list[tuple[str, str]]:
    """Create a database, cluster it and return representative/member pairs."""

    workdir = Path(tempfile.mkdtemp(prefix="foldseek_cluster_"))
    inputs = workdir / "inputs"
    inputs.mkdir()
    for index, path in enumerate(structures):
        shutil.copyfile(path, inputs / f"{index:04d}_{path.name}")
    database = workdir / "db"
    cluster = workdir / "clu"
    tsv = workdir / "clusters.tsv"
    env = dict(os.environ)
    commands = [
        _binary(binary) + ["createdb", str(inputs), str(database)],
        _binary(binary)
        + ["cluster", str(database), str(cluster), str(workdir / "tmp"), "--tmscore-threshold", f"{tmscore_threshold:.4f}", "--cov-mode", "0", "-c", f"{coverage:.4f}"],
        _binary(binary) + ["createtsv", str(database), str(database), str(cluster), str(tsv)],
    ]
    for command in commands:
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env)
        except FileNotFoundError as exc:
            raise StepError("foldseek_cluster: the Foldseek executable was not found; set foldseek_path to its location") from exc
        except subprocess.TimeoutExpired as exc:
            raise StepError(f"foldseek_cluster: Foldseek timed out after {timeout} s") from exc
        if completed.returncode != 0:
            tail = " ".join((completed.stderr or completed.stdout or "").strip().splitlines()[-2:])
            raise StepError(f"foldseek_cluster: Foldseek failed with exit code {completed.returncode}: {tail[:300]}")
    if not tsv.is_file():
        raise StepError("foldseek_cluster: Foldseek wrote no cluster table")
    pairs: list[tuple[str, str]] = []
    for line in tsv.read_text().splitlines():
        fields = line.split("\t")
        if len(fields) < 2:
            continue
        pairs.append((fields[0], fields[1]))
    if not pairs:
        raise StepError("foldseek_cluster: Foldseek returned no cluster assignment")
    return pairs


def _original_name(member: str) -> str:
    """Strip the numeric input prefix added for stable ordering."""

    name = member.rstrip("/").split("/")[-1]
    if name[:4].isdigit() and "_" in name:
        return name.split("_", 1)[1]
    return name


def cluster_rows(pairs: list[tuple[str, str]]) -> tuple[list[str], np.ndarray, dict]:
    """Aggregate representative/member pairs into per-structure rows."""

    members: dict[str, list[str]] = {}
    for representative, member in pairs:
        members.setdefault(_original_name(representative), []).append(_original_name(member))
    order = sorted(members)
    sizes = {name: len(members[name]) for name in order}
    rows = []
    for cluster_id, name in enumerate(order, start=1):
        for member in members[name]:
            rows.append([float(cluster_id), float(sizes[name]), 1.0 if member == name else 0.0])
    info = {
        "n_structures": int(sum(sizes.values())),
        "n_clusters": len(order),
        "cluster_sizes": sizes,
        "representatives": order,
    }
    return order, np.asarray(rows, dtype=np.float32), info


class FoldseekClusterStep(Step):
    provider = "operon-core"
    parameters_file = "foldseek_cluster.FoldseekClusterStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "foldseek_cluster",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Foldseek structural clustering",
        "description": "Cluster a directory of structures with Foldseek and report cluster membership, size and representatives.",
        "category": "Structure",
        "icon": "TreeStructure",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory",
                       "external_tools": ["foldseek"]},
        "dependencies": [],
        "dependency_imports": [],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        structures = collect_structures(str(params.get("structure_dir", "")), str(params.get("structure_paths", "")))
        binary = str(params.get("foldseek_path") or "foldseek")
        resolved = shutil.which(binary) or (binary if Path(binary).is_file() else "")
        if not resolved:
            raise StepError("foldseek_cluster: the Foldseek executable was not found; set foldseek_path to its location")
        threshold = float(params.get("tmscore_threshold", 0.6))
        if not 0.0 < threshold <= 1.0:
            raise StepError("foldseek_cluster: tmscore_threshold must be in (0, 1]")
        coverage = float(params.get("coverage", 0.8))
        if not 0.0 < coverage <= 1.0:
            raise StepError("foldseek_cluster: coverage must be in (0, 1]")
        pairs = run_cluster(resolved, structures, tmscore_threshold=threshold, coverage=coverage, timeout=int(params.get("timeout_seconds", 600)))
        order, data, summary = cluster_rows(pairs)
        labels: dict[str, int] = {}
        cursor = 0
        for name in order:
            for representative, member in pairs:
                if _original_name(representative) != name:
                    continue
                labels[_original_name(member)] = cursor
                cursor += 1
        out = params.get("output", "clusters")
        ctx[out] = Form(
            data=data,
            dims=["structure", "statistic"],
            labels={"structure": labels, "statistic": {"cluster_id": 0, "cluster_size": 1, "is_representative": 2}},
            info={
                "missing_code": np.nan,
                "tmscore_threshold": threshold,
                "coverage": coverage,
                **summary,
            },
        )
        self._export_data = {
            "output": out,
            "n_clusters": int(summary["n_clusters"]),
            "n_structures": int(summary["n_structures"]),
        }
        return ctx[out]

    def export(self, ctx):
        return getattr(self, "_export_data", {})
