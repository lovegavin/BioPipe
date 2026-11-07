"""Dock several ligands against one receptor with AutoDock Vina."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._native_results import output_directory, remember_native, result_file

from .vina_dock import docking_command, ligand_centroid, parse_vina_log

_STATISTICS = ("best_affinity", "rmsd_lb", "rmsd_ub", "n_modes")


def split_paths(text: str) -> list[str]:
    """Split a comma, semicolon or newline separated path list."""

    cleaned = str(text or "").replace(";", ",").replace("\n", ",")
    return [part.strip() for part in cleaned.split(",") if part.strip()]


def unique_labels(paths: list[Path]) -> list[str]:
    """Build unique labels from ligand file stems."""

    seen: dict[str, int] = {}
    labels: list[str] = []
    for path in paths:
        stem = path.stem
        count = seen.get(stem, 0) + 1
        seen[stem] = count
        labels.append(stem if count == 1 else f"{stem}#{count}")
    return labels


def _first(value) -> float:
    """Return the first mode of a possibly list-valued log field."""

    if isinstance(value, (list, tuple)):
        return float(value[0]) if value else float("nan")
    return float(value)


def run_ligand(
    binary: str,
    receptor: Path,
    ligand: Path,
    out_dir: Path,
    params: dict,
    center: tuple[float, float, float],
    *,
    timeout: int,
    operator: str = "vina_dock_batch",
    tag: str | None = None,
) -> dict:
    """Dock one ligand and return the parsed score table."""

    stem = tag or ligand.stem
    out_path = out_dir / f"{stem}_out.pdbqt"
    log_path = out_dir / f"{stem}_vina.log"
    command = docking_command(params, binary, receptor, ligand, out_path, center)
    if binary.lower().endswith(".py"):
        # A script runner cannot be executed directly on Windows.
        command = [sys.executable] + command
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as error:
        raise StepError(f"{operator}: '{binary}' was not found on PATH") from error
    except subprocess.TimeoutExpired as error:
        raise StepError(f"{operator}: vina timed out after {timeout} s") from error
    log_path.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-3:]
        raise StepError(
            f"{operator}: vina failed with exit code {completed.returncode}: "
            + " | ".join(tail)
        )
    if not out_path.is_file() or out_path.stat().st_size == 0:
        raise StepError(f"{operator}: vina produced no pose file for {ligand}")
    parsed = parse_vina_log(completed.stdout)
    if not parsed.get("affinities"):
        raise StepError(f"{operator}: vina reported no binding mode for {ligand}")
    return {
        "ligand": ligand.stem,
        "best_affinity": float(parsed["best_affinity"]),
        "rmsd_lb": _first(parsed["rmsd_lb"]),
        "rmsd_ub": _first(parsed["rmsd_ub"]),
        "n_modes": len(parsed["affinities"]),
        "out_path": str(out_path),
        "log_path": str(log_path),
    }


class VinaDockBatchStep(Step):
    """Dock a list of PDBQT ligands and rank their best affinities."""

    provider = "operon-core"
    parameters_file = "vina_dock_batch.VinaDockBatchStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "vina_dock_batch",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Batch docking",
        "description": (
            "Run AutoDock Vina for every listed PDBQT ligand against one receptor "
            "and report the best affinity, RMSD bounds and mode count per ligand."
        ),
        "category": "Machine Learning",
        "icon": "Flask",
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
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        receptor_text = str(params.get("receptor_path") or "").strip()
        ligand_text = str(params.get("ligand_paths") or "").strip()
        binary = str(params.get("vina_path") or "vina").strip() or "vina"
        timeout = int(params.get("timeout_seconds") or 600)
        out_name = params.get("output", self.name)

        if not receptor_text:
            raise StepError("vina_dock_batch: receptor_path is required")
        receptor = Path(receptor_text).expanduser()
        if not receptor.is_file():
            raise StepError(f"vina_dock_batch: receptor_path {receptor} is not a file")
        if receptor.suffix.lower() != ".pdbqt":
            raise StepError("vina_dock_batch: receptor_path must name a .pdbqt file")
        ligand_files = [Path(item).expanduser() for item in split_paths(ligand_text)]
        if not ligand_files:
            raise StepError("vina_dock_batch: ligand_paths must list at least one PDBQT file")
        for ligand in ligand_files:
            if not ligand.is_file():
                raise StepError(f"vina_dock_batch: ligand {ligand} is not a file")
            if ligand.suffix.lower() != ".pdbqt":
                raise StepError(f"vina_dock_batch: ligand {ligand} is not a .pdbqt file")
        if timeout < 1:
            raise StepError("vina_dock_batch: timeout_seconds must be at least 1")

        explicit = [params.get(key) for key in ("center_x", "center_y", "center_z")]
        if all(value is not None for value in explicit):
            center = tuple(float(value) for value in explicit)
        else:
            vectors = np.asarray([ligand_centroid(path) for path in ligand_files])
            center = tuple(float(value) for value in vectors.mean(axis=0))
        out_dir = Path(ctx.task_dir) / "docking"
        out_dir.mkdir(parents=True, exist_ok=True)
        labels = unique_labels(ligand_files)
        records = [
            run_ligand(
                binary,
                receptor,
                ligand,
                out_dir,
                params,
                center,
                timeout=timeout,
                tag=label,
            )
            for ligand, label in zip(ligand_files, labels)
        ]
        directory = output_directory(ctx, "vina_batch")
        native_poses = []
        for record in records:
            target = directory / Path(record["out_path"]).name
            shutil.copyfile(record["out_path"], target)
            record["out_path"] = str(target)
            native_poses.append(target)
        data = np.asarray(
            [
                (
                    record["best_affinity"],
                    record["rmsd_lb"],
                    record["rmsd_ub"],
                    float(record["n_modes"]),
                )
                for record in records
            ],
            dtype=np.float32,
        )
        form_out = Form(
            data=data,
            dims=["ligand", "statistic"],
            labels={
                "ligand": {label: index for index, label in enumerate(labels)},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "receptor_path": str(receptor),
                "ligands": [str(path) for path in ligand_files],
                "center": list(center),
                "poses": {label: record["out_path"] for label, record in zip(labels, records)},
                "logs": {label: record["log_path"] for label, record in zip(labels, records)},
                "best_ligand": labels[int(np.argmin(data[:, 0]))],
                "best_affinity": float(np.min(data[:, 0])),
            },
        )
        result_files = [result_file(f"poses_{index + 1}", path, "pdbqt", f"Docking poses {index + 1}") for index, path in enumerate(native_poses)]
        remember_native(ctx, str(out_name), result_files)
        ctx[out_name] = form_out
        self._export_data = {
            "n_ligands": len(records),
            "best_affinity": float(np.min(data[:, 0])),
            "receptor_path": str(receptor),
            "ligands": [str(path) for path in ligand_files],
            "result_files": result_files,
        }
        print(
            f"[{self.name}] docked {len(records)} ligand(s), best "
            f"{np.min(data[:, 0]):.2f} kcal/mol"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
