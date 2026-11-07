"""Backbone generation with the official RFdiffusion ``run_inference.py``."""

from __future__ import annotations

import re
import subprocess
import tempfile
import shutil
from operon.bytecode import io_path
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader import read_source
from src.task.step.base import Step
from src.task.step.steps._resources_common import require
from src.task.step.steps._native_results import output_directory, result_file, remember_native

_CONTOG = re.compile(r"^[A-Za-z0-9/,()\- ]*$")


def parse_contigs(text: str) -> str:
    """Validate an RFdiffusion contig expression and return it stripped."""

    value = (text or "").strip()
    if not value:
        raise StepError(
            "rfdiffusion_design: contigs is required, for example 'A1-100' or "
            "'50-80 A1-100,0'"
        )
    if not _CONTOG.match(value):
        raise StepError(
            f"rfdiffusion_design: contigs {value!r} contains characters RFdiffusion "
            "does not accept (letters, digits, '-', '/', ',', parentheses and spaces)"
        )
    if not re.search(r"\d", value):
        raise StepError(f"rfdiffusion_design: contigs {value!r} declares no residue range")
    return value


def design_paths(outdir: Path, stem: str = "design") -> list[Path]:
    """PDB files written by RFdiffusion, ordered by design index."""

    matches = sorted(outdir.glob(f"{stem}*.pdb")) or sorted(outdir.glob("*.pdb"))

    def index(path: Path) -> int:
        tail = path.stem[len(stem):] if path.stem.startswith(stem) else path.stem
        digits = re.findall(r"\d+", tail)
        return int(digits[-1]) if digits else 0

    return sorted(matches, key=index)


def design_command(
    params: dict,
    runner: Path,
    structure: Path | None,
    outdir: Path,
) -> list[str]:
    """Build the hydra command line for ``run_inference.py``."""

    command = [
        str(params.get("python_executable") or "python"),
        str(runner),
        f"inference.output_prefix={(outdir / 'design').as_posix()}",
        f"inference.num_designs={int(params.get('num_designs') or 1)}",
        f"contigmap.contigs=[{parse_contigs(str(params.get('contigs') or ''))}]",
        f"inference.device={params.get('device') or 'cpu'}",
    ]
    if structure is not None:
        command.append(f"inference.input_pdb={structure.as_posix()}")
    return command


def stack_designs(paths: list[Path]) -> tuple[np.ndarray, dict, dict]:
    """Stack the design tables into one ``[design, atom, field]`` array."""

    frames: list[np.ndarray] = []
    design_labels: dict[str, int] = {}
    atom_labels: dict[str, int] = {}
    field_labels: dict[str, int] = {}
    summary: list[dict] = []
    for index, path in enumerate(paths):
        form = read_source(path, ["atom", "field"], {"atom": "auto", "field": "builtin"})
        if not field_labels:
            field_labels = dict(form.labels["field"])
        elif dict(form.labels["field"]) != field_labels:
            raise StepError("rfdiffusion_design: the designs carry different field columns")
        ordered = sorted(form.labels["atom"].items(), key=lambda item: item[1])
        if not atom_labels:
            for position in range(len(ordered)):
                atom_labels[f"atom{position + 1}"] = position
        elif len(ordered) != len(atom_labels):
            raise StepError(
                f"rfdiffusion_design: design {index + 1} has {len(ordered)} atoms, "
                f"expected {len(atom_labels)}"
            )
        design_labels[f"design{index + 1}"] = index
        frames.append(np.asarray(form.data, dtype=np.float32))
        summary.append(
            {"index": index + 1, "path": path.name, "n_atoms": int(form.data.shape[0])}
        )
    data = (
        np.stack(frames, axis=0)
        if frames
        else np.zeros((0, 0, len(field_labels)), dtype=np.float32)
    )
    labels = {"design": design_labels, "atom": atom_labels, "field": field_labels}
    return data, labels, {"designs": summary, "n_atoms": int(data.shape[1]) if frames else 0}


class RfdiffusionDesignStep(Step):
    """Generate protein backbones with the official RFdiffusion runner."""

    provider = "operon-core"

    parameters_file = "rfdiffusion_design.RfdiffusionDesignStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rfdiffusion_design",
        "version": "1.0.0",
        "kind": "operator",
        "title": "RFdiffusion backbone design",
        "description": (
            "Run the official RFdiffusion run_inference.py for a contig expression and "
            "return the generated backbones as a [design, atom, field] all-atom table."
        ),
        "category": "Machine Learning",
        "icon": "ShareNetwork",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 3,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        del inputs
        params = ctx.step_params
        out_name = str(params.get("output") or "designs")
        structure_text = str(params.get("structure_path") or "").strip()
        structure: Path | None = None
        if structure_text:
            structure = Path(structure_text).expanduser().resolve()
            if not structure.is_file():
                raise StepError(
                    f"rfdiffusion_design: structure_path {structure} is not a file"
                )
        parse_contigs(str(params.get("contigs") or ""))

        root_text = str(params.get("rfdiffusion_path") or "").strip()
        root = str(Path(root_text).expanduser().resolve()) if root_text else None
        _, repo = require("rfdiffusion_design", "rfdiffusion", root)
        runner = repo / "scripts" / "run_inference.py"
        if not runner.is_file():
            raise StepError(f"rfdiffusion_design: {runner} is missing from the checkout")

        python = str(params.get("python_executable") or "python")
        timeout = int(params.get("timeout_seconds") or 3600)
        with tempfile.TemporaryDirectory(prefix="rfdiffusion_") as work:
            outdir = Path(work) / "out"
            outdir.mkdir(parents=True, exist_ok=True)
            command = design_command(params, runner, structure, outdir)
            try:
                completed = subprocess.run(
                    command,
                    cwd=repo,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=None,
                )
            except FileNotFoundError as exc:
                raise StepError(
                    f"rfdiffusion_design: interpreter {python!r} is not available"
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise StepError(
                    f"rfdiffusion_design: the designer timed out after {timeout} s"
                ) from exc
            if completed.returncode != 0:
                tail = (completed.stderr or completed.stdout or "").strip()[-1500:]
                raise StepError(
                    "rfdiffusion_design: the designer failed with exit code "
                    f"{completed.returncode}: {tail}"
                )
            paths = design_paths(outdir)
            if not paths:
                raise StepError(
                    f"rfdiffusion_design: the designer produced no PDB under {outdir}"
                )
            data, labels, extra = stack_designs(paths)
            saved_dir = output_directory(ctx, 'rfdiffusion')
            self._result_files = []
            for index, path in enumerate(paths, start=1):
                destination = saved_dir / path.name
                shutil.copyfile(io_path(path), io_path(destination))
                self._result_files.append(result_file(f'design-{index}', destination, 'pdb',
                                                       f'Backbone {index}'))
            remember_native(ctx, out_name, self._result_files)

        form = Form(
            data,
            dims=["design", "atom", "field"],
            labels=labels,
            info={
                "missing_code": np.nan,
                "n_designs": len(paths),
                "n_atoms": extra["n_atoms"],
                "designs": extra["designs"],
                "contigs": str(params.get("contigs") or ""),
                "rfdiffusion_path": str(repo),
            },
        )
        ctx[out_name] = form
        self._export_data = form

    def export(self, ctx) -> dict:
        form = self._export_data
        return {
            "operator": "rfdiffusion_design",
            "result_files": self._result_files,
            "n_designs": int(form.info["n_designs"]),
            "designs": form.info["designs"],
        }
