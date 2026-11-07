"""structure_pocket_detect: fpocket cavity detection wrapper."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import decode_column

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
_FIELDS = {
    "score": "Score",
    "druggability": "Druggability Score",
    "n_spheres": "Number of Alpha Spheres",
    "volume": "Volume",
    "mean_radius": "Mean alpha sphere radius",
    "hydrophobicity": "Hydrophobicity score",
    "sasa": "Total SASA",
}


def parse_info(text: str) -> list[dict]:
    """Parse the fpocket ``*_info.txt`` pocket summary."""

    pockets = []
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        match = re.match(r"^Pocket\s+(\d+)\s*:", stripped)
        if match:
            if current is not None:
                pockets.append(current)
            current = {"index": int(match.group(1))}
            continue
        if current is None:
            continue
        if stripped.startswith("Volume score"):
            continue
        for key, label in _FIELDS.items():
            if stripped.startswith((label + " ", label + "\t", label + " :")):
                values = _NUMBER.findall(stripped[len(label):])
                if values:
                    current[key] = float(values[0].rstrip("."))
                break
    if current is not None:
        pockets.append(current)
    return pockets


def pocket_residues(path: Path) -> tuple[int, float, float, float]:
    """Return residue count and atom centroid for one pocket file."""

    residues = set()
    coordinates = []
    for line in path.read_text().splitlines():
        if line.startswith(("ATOM", "HETATM")):
            residues.add((line[21], line[22:27].strip(), line[17:20].strip()))
            coordinates.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
    if not coordinates:
        return 0, float("nan"), float("nan"), float("nan")
    array = np.asarray(coordinates)
    centre = array.mean(axis=0)
    return len(residues), float(centre[0]), float(centre[1]), float(centre[2])


def run_fpocket(
    pdb_text: str,
    *,
    binary: str = "fpocket",
    workdir: Path | None = None,
    timeout: int = 1800,
) -> dict:
    """Run fpocket and collect its pockets."""

    resolved = binary if Path(binary).is_file() else None
    if resolved is None:
        from shutil import which

        resolved = which(binary)
    if resolved is None:
        raise StepError(f"structure_pocket_detect: '{binary}' was not found on PATH")
    workdir = Path(workdir or tempfile.mkdtemp(prefix="fpocket_"))
    workdir.mkdir(parents=True, exist_ok=True)
    pdb_path = workdir / "model.pdb"
    pdb_path.write_text(pdb_text)
    prefix = workdir / "fpocket"
    launcher = [sys.executable, str(resolved)] if str(resolved).lower().endswith(".py") else [str(resolved)]
    command = launcher + ["-f", str(pdb_path), "-o", str(prefix)]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise StepError(f"structure_pocket_detect: fpocket timed out after {timeout} s") from exc
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-3:]
        raise StepError("structure_pocket_detect: fpocket failed with exit code "
                        f"{completed.returncode}: {' | '.join(tail)}")
    candidates = sorted(workdir.rglob("*_info.txt"))
    if not candidates:
        raise StepError("structure_pocket_detect: fpocket produced no *_info.txt file")
    info_path = candidates[-1]
    pockets = parse_info(info_path.read_text())
    pocket_dir = info_path.parent / "pockets"
    for pocket in pockets:
        path = pocket_dir / f"pocket{pocket['index']}_atm.pdb"
        if path.is_file():
            count, cx, cy, cz = pocket_residues(path)
            pocket.update({"n_residues": count, "centre_x": cx, "centre_y": cy, "centre_z": cz})
    return {"pockets": pockets, "info_path": str(info_path), "out_dir": str(info_path.parent)}


class StructurePocketDetectStep(Step):
    provider = "operon-core"
    parameters_file = "structure_pocket_detect.StructurePocketDetectStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_pocket_detect",
        "version": "1.0.0",
        "kind": "operator",
        "title": "fpocket 口袋检测",
        "description": (
            "Detect surface pockets with the fpocket alpha-sphere method and report the "
            "pocket score, druggability, volume, alpha-sphere radius, lining residue "
            "count and centroid for every pocket that passes the filters."
        ),
        "category": "Structure",
        "icon": "Cube",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "atom_dim"}, {"param": "field_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": [],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        if not isinstance(form, Form) or form.data.size == 0:
            raise StepError("structure_pocket_detect: the structure form is empty")
        field_dim = str(params.get("field_dim", "field"))
        resnames = decode_column(form, field_dim, "resname")
        chains = decode_column(form, field_dim, "chain")
        numbers = decode_column(form, field_dim, "residue_number")
        names = decode_column(form, field_dim, "atom_name")
        elements = decode_column(form, field_dim, "element")
        heavy = np.asarray([str(value).strip().upper() != "H" for value in elements])
        if not heavy.any():
            raise StepError("structure_pocket_detect: the structure form carries no heavy atoms")
        lines = []
        serial = 1
        for row in range(form.data.shape[0]):
            if not heavy[row]:
                continue
            x, y, z = (float(value) for value in form.data[row, :3])
            lines.append(
                f"ATOM  {serial:5d} {str(names[row])[:4]:<4s} {str(resnames[row])[:3]:>3s} "
                f"{str(chains[row])[:1]}{int(float(numbers[row])):4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {str(elements[row])[:2]:>2s}"
            )
            serial += 1
        lines.append("END")
        result = run_fpocket(
            "\n".join(lines) + "\n",
            binary=str(params.get("fpocket_path", "fpocket")),
            workdir=Path(tempfile.mkdtemp(prefix="fpocket_")),
            timeout=int(params.get("timeout_seconds", 1800)),
        )
        pockets = result["pockets"]
        min_score = float(params.get("min_score", 0.0))
        min_druggability = float(params.get("min_druggability", 0.0))
        kept = [
            pocket
            for pocket in pockets
            if float(pocket.get("score", 0.0)) >= min_score
            and float(pocket.get("druggability", 0.0)) >= min_druggability
        ]
        kept.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
        max_pockets = int(params.get("max_pockets", 0))
        if max_pockets > 0:
            kept = kept[:max_pockets]
        if not kept:
            raise StepError("structure_pocket_detect: fpocket found no pocket above the requested thresholds")
        statistics = ("score", "druggability", "volume", "n_spheres", "mean_radius", "n_residues", "centre_x", "centre_y", "centre_z")
        values = np.asarray(
            [[float(pocket.get(stat, 0.0)) for stat in statistics] for pocket in kept],
            dtype=np.float32,
        )
        pocket_dim = str(params.get("pocket_dim", "pocket"))
        out_name = str(params.get("output", "pockets"))
        ctx[out_name] = Form(
            data=values,
            dims=[pocket_dim, "statistic"],
            labels={pocket_dim: {f"pocket{pocket['index']}": index for index, pocket in enumerate(kept)},
                    "statistic": {stat: index for index, stat in enumerate(statistics)}},
            info={
                "missing_code": np.nan,
                "n_pockets": len(kept),
                "n_detected": len(pockets),
                "best_score": float(kept[0].get("score", 0.0)),
                "best_druggability": float(kept[0].get("druggability", 0.0)),
                "min_score": min_score,
                "min_druggability": min_druggability,
                "info_path": result["info_path"],
            },
        )
        self._export_data = {"pockets": kept, "n_detected": len(pockets), "info_path": result["info_path"]}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
