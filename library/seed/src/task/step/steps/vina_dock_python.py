"""vina_dock_python: AutoDock Vina through its official Python bindings."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import decode_column
from src.task.step.steps._native_results import output_directory, remember_native, result_file

_AD4 = {
    "C": "A",
    "N": "N",
    "O": "OA",
    "S": "SA",
    "P": "P",
    "F": "F",
    "CL": "Cl",
    "BR": "Br",
    "I": "I",
    "H": "H",
    "SE": "Se",
    "ZN": "Zn",
    "MG": "Mg",
    "CA": "Ca",
    "FE": "Fe",
    "MN": "Mn",
    "NA": "Na",
    "K": "K",
}


def ad4_type(element: str) -> str:
    """Map an element symbol to an AutoDock 4 atom type."""

    symbol = str(element).strip().upper()
    if not symbol:
        raise StepError("vina_dock_python: an atom has no element symbol")
    return _AD4.get(symbol, symbol.title())


def receptor_pdbqt(form: Form, field_dim: str = "field") -> str:
    """Convert a protein Form into a rigid PDBQT receptor block."""

    names = decode_column(form, field_dim, "atom_name")
    resnames = decode_column(form, field_dim, "resname")
    chains = decode_column(form, field_dim, "chain")
    numbers = decode_column(form, field_dim, "residue_number")
    elements = decode_column(form, field_dim, "element")
    lines = []
    serial = 1
    for row in range(form.data.shape[0]):
        element = str(elements[row]).strip()
        if element.upper() == "H":
            continue
        x, y, z = (float(value) for value in form.data[row, :3])
        atom_type = ad4_type(element)
        name = str(names[row])[:4]
        lines.append(
            f"ATOM  {serial:5d} {name:<4s} {str(resnames[row])[:3]:>3s} {str(chains[row])[:1]}"
            f"{int(float(numbers[row])):4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00     0.000 {atom_type:<2s}"
        )
        serial += 1
    if not lines:
        raise StepError("vina_dock_python: the receptor carries no heavy atom")
    lines.append("END")
    return "\n".join(lines) + "\n"


def parse_ligand_box(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Return the ligand centroid and coordinate range from a PDBQT file."""

    if not Path(path).is_file():
        raise StepError(f"vina_dock_python: ligand {path} is not a file")
    coordinates = []
    for line in Path(path).read_text().splitlines():
        if line.startswith(("ATOM", "HETATM")):
            coordinates.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
    if not coordinates:
        raise StepError(f"vina_dock_python: ligand {path} carries no atom record")
    array = np.asarray(coordinates)
    return array.mean(axis=0), array.max(axis=0) - array.min(axis=0)


def dock(
    receptor_text: str,
    ligand_path: Path,
    *,
    center: tuple[float, float, float] | None = None,
    size: tuple[float, float, float] = (20.0, 20.0, 20.0),
    exhaustiveness: int = 8,
    num_modes: int = 9,
    seed: int = 0,
    cpu: int = 1,
    scoring: str = "vina",
    flex_path: Path | None = None,
    workdir: Path | None = None,
) -> dict:
    """Run the official Vina engine and return the pose energies."""

    try:
        from vina import Vina
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise StepError("vina_dock_python: the 'vina' package is required; install it with 'python -m pip install vina'") from exc
    workdir = Path(workdir or tempfile.mkdtemp(prefix="vina_"))
    workdir.mkdir(parents=True, exist_ok=True)
    receptor_file = workdir / "receptor.pdbqt"
    receptor_file.write_text(receptor_text)
    ligand_centroid, ligand_extent = parse_ligand_box(Path(ligand_path))
    if center is None:
        centre = tuple(float(value) for value in ligand_centroid)
    else:
        centre = tuple(float(value) for value in center)
    box = tuple(float(value) for value in size)
    engine = Vina(sf_name=scoring, cpu=int(cpu), seed=int(seed), verbosity=0)
    if flex_path is not None:
        engine.set_receptor(str(receptor_file), str(Path(flex_path)))
    else:
        engine.set_receptor(str(receptor_file))
    engine.set_ligand_from_file(str(ligand_path))
    engine.compute_vina_maps(center=[round(value, 3) for value in centre], box_size=[round(value, 3) for value in box])
    engine.dock(exhaustiveness=int(exhaustiveness), n_poses=int(num_modes))
    energies = np.asarray(engine.energies(n_poses=int(num_modes)), dtype=float)
    if energies.ndim == 1:
        energies = energies.reshape(1, -1)
    pose_file = workdir / "poses.pdbqt"
    engine.write_poses(str(pose_file), n_poses=int(num_modes), overwrite=True)
    return {
        "energies": energies,
        "center": centre,
        "size": box,
        "ligand_extent": ligand_extent,
        "pose_file": str(pose_file),
        "receptor_file": str(receptor_file),
    }


_STATISTICS = ("total", "inter", "intra", "torsion", "intra_best")


class VinaDockPythonStep(Step):
    provider = "operon-core"
    parameters_file = "vina_dock_python.VinaDockPythonStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "vina_dock_python",
        "version": "1.0.0",
        "kind": "operator",
        "title": "AutoDock Vina 对接 (Python 绑定)",
        "description": (
            "Dock a prepared ligand PDBQT into a protein receptor with the official AutoDock "
            "Vina Python engine and report the per-pose scoring terms."
        ),
        "category": "Docking",
        "icon": "Flask",
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
        "dependencies": ["vina>=1.2"],
        "dependency_imports": ["vina"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        if not isinstance(form, Form) or form.data.size == 0:
            raise StepError("vina_dock_python: the receptor form is empty")
        ligand_text = str(params.get("ligand_path", "")).strip()
        if not ligand_text:
            raise StepError("vina_dock_python: ligand_path is required")
        ligand_path = Path(ligand_text).expanduser()
        if not ligand_path.is_file():
            raise StepError(f"vina_dock_python: ligand_path {ligand_path} is not a file")
        if ligand_path.suffix.lower() != ".pdbqt":
            raise StepError("vina_dock_python: ligand_path must be a .pdbqt file; prepare it with ligand_pdbqt_prepare")
        auto_center = [float(params.get(key, 0.0)) for key in ("center_x", "center_y", "center_z")]
        center = None if not any(auto_center) else tuple(auto_center)
        size = tuple(float(params.get(key, 20.0)) for key in ("size_x", "size_y", "size_z"))
        field_dim = str(params.get("field_dim", "field"))
        reaction = receptor_pdbqt(form, field_dim)
        flex_text = str(params.get("flex_path", "")).strip()
        flex_path = None
        if flex_text:
            flex_path = Path(flex_text).expanduser()
            if not flex_path.is_file():
                raise StepError(f"vina_dock_python: flex_path {flex_path} is not a file")
        result = dock(
            reaction,
            ligand_path,
            center=center,
            size=size,
            exhaustiveness=int(params.get("exhaustiveness", 8)),
            num_modes=int(params.get("num_modes", 9)),
            seed=int(params.get("seed", 42)),
            cpu=int(params.get("cpu", 1)),
            scoring=str(params.get("scoring", "vina")),
            flex_path=flex_path,
            workdir=Path(tempfile.mkdtemp(prefix="vina_")),
        )
        energies = result["energies"]
        directory = output_directory(ctx, "vina")
        native_pose = directory / "poses.pdbqt"
        shutil.copyfile(result["pose_file"], native_pose)
        pose_dim = str(params.get("pose_dim", "pose"))
        out_name = str(params.get("output", "docking"))
        columns = _STATISTICS[: energies.shape[1]]
        ctx[out_name] = Form(
            data=energies.astype(np.float32),
            dims=[pose_dim, "statistic"],
            labels={
                pose_dim: {f"pose{index + 1}": index for index in range(energies.shape[0])},
                "statistic": {name: index for index, name in enumerate(columns)},
            },
            info={
                "missing_code": np.nan,
                "n_poses": int(energies.shape[0]),
                "best_affinity": float(energies[0, 0]),
                "center": [float(value) for value in result["center"]],
                "size": [float(value) for value in result["size"]],
                "ligand_path": str(ligand_path),
                "flex_path": str(flex_path) if flex_path is not None else "",
                "pose_file": str(native_pose),
                "receptor_file": result["receptor_file"],
                "scoring": str(params.get("scoring", "vina")),
            },
        )
        result_files = [result_file("poses", native_pose, "pdbqt", "Vina docking poses")]
        remember_native(ctx, out_name, result_files)
        self._export_data = {
            "poses": [
                {"pose": f"pose{index + 1}", "total": float(row[0]), "terms": [float(value) for value in row]}
                for index, row in enumerate(energies)
            ],
            "best_affinity": float(energies[0, 0]),
            "pose_file": str(native_pose),
            "result_files": result_files,
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
