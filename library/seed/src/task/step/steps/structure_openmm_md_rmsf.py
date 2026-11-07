"""structure_openmm_md_rmsf: short OpenMM MD with per-residue RMSF."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import decode_column, residue_labels, residue_order

BACKBONE = {"N", "CA", "C", "O", "OXT"}
STATISTICS = ("rmsf_nm", "mean_rg_nm")


def write_pdb(form: Form, path: Path) -> None:
    """Write a fixed-column PDB from the atom Form."""

    names = decode_column(form, "field", "atom_name")
    resnames = decode_column(form, "field", "resname")
    chains = decode_column(form, "field", "chain")
    numbers = decode_column(form, "field", "residue_number")
    elements = decode_column(form, "field", "element")
    lines = []
    previous = None
    serial = 1
    for row in range(form.data.shape[0]):
        chain = str(chains[row])
        if previous is not None and chain != previous:
            lines.append("TER")
        previous = chain
        x, y, z = (float(value) for value in form.data[row, :3])
        name = str(names[row])[:4]
        lines.append(
            f"ATOM  {serial:5d} {name:<4s} {str(resnames[row])[:3]:>3s} {chain[:1]}{int(float(numbers[row])):4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {str(elements[row])[:2]:>2s}"
        )
        serial += 1
    lines.append("TER")
    lines.append("END")
    path.write_text("\n".join(lines) + "\n")


def prepare(pdb_path: Path, *, ph: float = 7.0):
    """Repair the structure and add hydrogens with PDBFixer."""

    try:
        from pdbfixer import PDBFixer
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise StepError("structure_openmm_md_rmsf: pdbfixer is required; install it with 'python -m pip install pdbfixer'") from exc
    fixer = PDBFixer(filename=str(pdb_path))
    fixer.findMissingResidues()
    fixer.findNonstandardResidues()
    fixer.replaceNonstandardResidues()
    fixer.removeHeterogens(keepWater=False)
    fixer.findMissingAtoms()
    fixer.addMissingAtoms()
    fixer.addMissingHydrogens(float(ph))
    return fixer


def build_simulation(topology, positions, *, temperature: float = 300.0, timestep_fs: float = 2.0, platform: str = "CPU"):
    """Build a minimised GB-Neck2 simulation for the prepared system."""

    try:
        import openmm
        from openmm import unit
        from openmm.app import HBonds, NoCutoff
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise StepError("structure_openmm_md_rmsf: openmm is required; install it with 'python -m pip install openmm'") from exc
    forcefield = openmm.app.ForceField("amber14-all.xml", "implicit/gbn2.xml")
    system = forcefield.createSystem(topology, nonbondedMethod=NoCutoff, constraints=HBonds)
    integrator = openmm.LangevinMiddleIntegrator(float(temperature) * unit.kelvin, 1.0 / unit.picosecond, float(timestep_fs) * unit.femtoseconds)
    simulation = openmm.app.Simulation(topology, system, integrator, openmm.Platform.getPlatformByName(platform))
    simulation.context.setPositions(positions)
    simulation.minimizeEnergy(maxIterations=100)
    simulation.context.setVelocitiesToTemperature(float(temperature) * unit.kelvin)
    return simulation


def rmsf_from_frames(frames: np.ndarray) -> np.ndarray:
    """Per-atom RMSF in nm after Kabsch alignment to the first frame."""

    reference = frames[0]
    aligned = np.empty_like(frames)
    for index, frame in enumerate(frames):
        mobile_centred = frame - frame.mean(axis=0)
        reference_centred = reference - reference.mean(axis=0)
        covariance = mobile_centred.T @ reference_centred
        u, _s, vt = np.linalg.svd(covariance)
        rotation = u @ vt
        if np.linalg.det(rotation) < 0:
            u = u.copy()
            u[:, -1] *= -1
            rotation = u @ vt
        aligned[index] = mobile_centred @ rotation
    deviations = aligned - aligned.mean(axis=0)
    return np.sqrt((deviations ** 2).sum(axis=-1).mean(axis=0))


def radius_of_gyration(frames: np.ndarray) -> np.ndarray:
    centred = frames - frames.mean(axis=1, keepdims=True)
    return np.sqrt((centred ** 2).sum(axis=-1).mean(axis=1))


def simulate(
    pdb_path: Path,
    *,
    chains: str = "",
    temperature: float = 300.0,
    timestep_fs: float = 2.0,
    steps: int = 5000,
    report_interval: int = 50,
    platform: str = "CPU",
    workdir: Path | None = None,
) -> dict:
    """Run a short MD and return RMSF, Rg and the collected frames."""

    try:
        from openmm import unit
    except ImportError as exc:  # pragma: no cover
        raise StepError("structure_openmm_md_rmsf: openmm is required; install it with 'python -m pip install openmm'") from exc
    workdir = Path(workdir or tempfile.mkdtemp(prefix="openmm_md_"))
    workdir.mkdir(parents=True, exist_ok=True)
    fixer = prepare(pdb_path)
    topology = fixer.topology
    positions = fixer.positions
    wanted = [name.strip() for name in str(chains).replace(";", ",").split(",") if name.strip()]
    if wanted:
        from openmm.app import Modeller

        delete = [chain for chain in topology.chains() if chain.id not in wanted]
        if delete:
            modeller = Modeller(topology, positions)
            modeller.delete(delete)
            topology = modeller.topology
            positions = modeller.positions
    selected = []
    for index, atom in enumerate(topology.atoms()):
        chain = atom.residue.chain.id
        if wanted and chain not in wanted:
            continue
        if atom.name == "CA":
            selected.append(index)
    if len(selected) < 3:
        raise StepError("structure_openmm_md_rmsf: fewer than three C-alpha atoms remain after chain selection")
    prepared = workdir / "prepared.pdb"
    with open(prepared, "w") as handle:
        from openmm.app import PDBFile

        PDBFile.writeFile(topology, positions, handle)
    simulation = build_simulation(topology, positions, temperature=temperature, timestep_fs=timestep_fs, platform=platform)
    frames = []
    step = 0
    numerator = 0
    while step < steps:
        chunk = min(report_interval, steps - step)
        simulation.step(chunk)
        step += chunk
        state = simulation.context.getState(getPositions=True)
        positions = np.asarray(state.getPositions().value_in_unit(unit.nanometer))
        frames.append(positions[selected])
    coordinates = np.asarray(frames)
    rmsf = rmsf_from_frames(coordinates)
    rg = radius_of_gyration(coordinates)
    trajectory = workdir / "frames.npy"
    np.save(trajectory, coordinates)
    labels = []
    residues = []
    atoms_by_index = {atom.index: atom for atom in topology.atoms()}
    for index in selected:
        residue = atoms_by_index[index].residue
        residues.append(residue)
        labels.append(f"{residue.chain.id}:{residue.name}:{residue.id}")
    return {
        "rmsf": rmsf,
        "labels": labels,
        "residues": residues,
        "n_frames": len(frames),
        "mean_rg_nm": float(np.mean(rg)),
        "max_rg_nm": float(np.max(rg)),
        "min_rg_nm": float(np.min(rg)),
        "temperature": float(temperature),
        "steps": int(steps),
        "timestep_fs": float(timestep_fs),
        "trajectory": str(trajectory),
        "prepared_pdb": str(prepared),
        "ca_indices": selected,
    }


class StructureOpenmmMdRmsfStep(Step):
    provider = "operon-core"
    parameters_file = "structure_openmm_md_rmsf.StructureOpenmmMdRmsfStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_openmm_md_rmsf",
        "version": "1.0.0",
        "kind": "operator",
        "title": "短程 OpenMM MD 与残基柔性 (RMSF)",
        "description": (
            "Run a short implicit-solvent molecular dynamics simulation with OpenMM and "
            "report the per-residue C-alpha root mean square fluctuation and radius of "
            "gyration."
        ),
        "category": "Structure",
        "icon": "Waves",
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
        "dependencies": ["openmm>=8.0", "pdbfixer>=1.9"],
        "dependency_imports": ["openmm", "pdbfixer"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        if not isinstance(form, Form) or form.data.size == 0:
            raise StepError("structure_openmm_md_rmsf: the structure form is empty")
        chains = str(params.get("chains", "")).strip()
        if chains:
            present = {str(value) for value in decode_column(form, "field", "chain")}
            missing = [name for name in chains.replace(";", ",").split(",") if name.strip() and name.strip() not in present]
            if missing:
                raise StepError(f"structure_openmm_md_rmsf: chain(s) {', '.join(missing)} are not in the structure")
        workdir = Path(tempfile.mkdtemp(prefix="openmm_md_"))
        pdb_path = workdir / "model.pdb"
        write_pdb(form, pdb_path)
        result = simulate(
            pdb_path,
            chains=chains,
            temperature=float(params.get("temperature", 300.0)),
            timestep_fs=float(params.get("timestep_fs", 2.0)),
            steps=int(params.get("steps", 5000)),
            report_interval=int(params.get("report_interval", 50)),
            platform=str(params.get("platform", "CPU")),
            workdir=workdir,
        )
        values = np.asarray([[value, result["mean_rg_nm"]] for value in result["rmsf"]], dtype=np.float32)
        out_dim = str(params.get("residue_dim", "residue"))
        out_name = str(params.get("output", "flexibility"))
        ctx[out_name] = Form(
            data=values,
            dims=[out_dim, "statistic"],
            labels={
                out_dim: {label: index for index, label in enumerate(result["labels"])},
                "statistic": {"rmsf_nm": 0, "mean_rg_nm": 1},
            },
            info={
                "missing_code": np.nan,
                "mean_rmsf_nm": float(np.mean(result["rmsf"])),
                "max_rmsf_nm": float(np.max(result["rmsf"])),
                "n_residues": len(result["labels"]),
                "n_frames": result["n_frames"],
                "temperature_k": result["temperature"],
                "steps": result["steps"],
                "timestep_fs": result["timestep_fs"],
                "trajectory": result["trajectory"],
                "prepared_pdb": result["prepared_pdb"],
                "ca_indices": result["ca_indices"],
            },
        )
        self._export_data = {
            "rows": [
                {"residue": label, "rmsf_nm": float(rmsf)}
                for label, rmsf in zip(result["labels"], result["rmsf"])
            ],
            "mean_rmsf_nm": float(np.mean(result["rmsf"])),
            "mean_rg_nm": result["mean_rg_nm"],
            "trajectory": result["trajectory"],
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
