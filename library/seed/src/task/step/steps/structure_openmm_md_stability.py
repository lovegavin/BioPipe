"""structure_openmm_md_stability: short implicit-solvent MD with drift statistics."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import decode_column
from src.task.step.steps.structure_openmm_energy import write_pdb
from src.task.step.steps.structure_rmsd import kabsch

STATISTICS = ("time_ps", "temperature_k", "potential_energy_kj", "rmsd_angstrom", "radius_of_gyration_angstrom")


def _load_openmm():
    try:
        import openmm
        from openmm import LangevinMiddleIntegrator, LocalEnergyMinimizer, Platform, unit
        from openmm.app import ForceField, HBonds, NoCutoff
        from pdbfixer import PDBFixer
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise StepError(
            "structure_openmm_md_stability: openmm and pdbfixer are required; install them with "
            "'python -m pip install openmm pdbfixer'"
        ) from exc
    return openmm, unit, LangevinMiddleIntegrator, LocalEnergyMinimizer, Platform, ForceField, HBonds, NoCutoff, PDBFixer


def radius_of_gyration(positions: np.ndarray) -> float:
    """Return the radius of gyration in Angstrom for an (n, 3) array in Angstrom."""

    centred = positions - positions.mean(axis=0)
    return float(np.sqrt((centred ** 2).sum(axis=1).mean()))


def temperature_from_kinetic(kinetic_kj: float, degrees_of_freedom: int) -> float:
    """Convert a kinetic energy in kJ/mol to a temperature in kelvin."""

    gas = 0.008314462618
    return float(2.0 * kinetic_kj / (degrees_of_freedom * gas))


def without_water(form: Form, atom_dim: str, field_dim: str) -> Form:
    """Drop water rows so the force field sees only the solute."""

    resnames = decode_column(form, field_dim, "resname")
    keep = np.asarray([str(name).strip().upper() not in {"HOH", "WAT", "DOD"} for name in resnames])
    if keep.all() or not keep.any():
        return form
    data = np.asarray(form.data, dtype=np.float64)[keep]
    atom_labels = {f"atom{index}": index for index in range(data.shape[0])}
    labels = dict(form.labels)
    labels[atom_dim] = atom_labels
    return Form(data=data.astype(np.float32), dims=list(form.dims), labels=labels, info=dict(form.info))


def drift_rows(frames: list[dict]) -> list[dict]:
    """Flatten per-frame statistics into table rows."""

    rows = []
    for frame in frames:
        rows.append({name: float(frame[name]) for name in STATISTICS})
    return rows


def drift_summary(rows: list[dict], *, seed: int | None = None) -> dict:
    """Summarise a short trajectory: temperature and geometry drift."""

    if not rows:
        return {"n_frames": 0, "mean_temperature_k": 0.0, "rmsd_final_angstrom": 0.0, "rg_change_angstrom": 0.0}
    temperatures = np.asarray([row["temperature_k"] for row in rows], dtype=float)
    radii = np.asarray([row["radius_of_gyration_angstrom"] for row in rows], dtype=float)
    return {
        "n_frames": len(rows),
        "mean_temperature_k": float(temperatures.mean()),
        "rmsd_final_angstrom": float(rows[-1]["rmsd_angstrom"]),
        "rg_change_angstrom": float(radii[-1] - radii[0]),
        "seed": seed,
    }


def md_run(
    pdb_path: Path,
    *,
    ph: float = 7.0,
    temperature: float = 300.0,
    friction: float = 1.0,
    step_size_fs: float = 2.0,
    steps: int = 500,
    sample_every: int = 50,
    minimize_iterations: int = 500,
    equilibrate_steps: int = 500,
    seed: int = 0,
    forcefield_files: tuple[str, ...] = ("amber14-all.xml", "implicit/gbn2.xml"),
) -> dict:
    """Minimise, then run a short Langevin trajectory and sample drift statistics."""

    openmm, unit, LangevinMiddleIntegrator, LocalEnergyMinimizer, Platform, ForceField, HBonds, NoCutoff, PDBFixer = _load_openmm()

    fixer = PDBFixer(filename=str(pdb_path))
    fixer.findMissingResidues()
    fixer.findNonstandardResidues()
    fixer.replaceNonstandardResidues()
    fixer.removeHeterogens(True)
    fixer.findMissingAtoms()
    fixer.addMissingAtoms()
    fixer.addMissingHydrogens(ph)

    forcefield = ForceField(*forcefield_files)
    system = forcefield.createSystem(fixer.topology, nonbondedMethod=NoCutoff, constraints=HBonds)
    integrator = LangevinMiddleIntegrator(
        temperature * unit.kelvin, friction / unit.picosecond, step_size_fs * 0.001 * unit.picoseconds
    )
    integrator.setRandomNumberSeed(seed)
    context = openmm.Context(system, integrator, Platform.getPlatformByName("CPU"))
    context.setPositions(fixer.positions)
    LocalEnergyMinimizer.minimize(context, 10.0, minimize_iterations)
    context.setVelocitiesToTemperature(temperature * unit.kelvin, seed)
    if equilibrate_steps:
        integrator.step(int(equilibrate_steps))

    def sample(step_index: int) -> dict:
        state = context.getState(getPositions=True, getEnergy=True)
        positions = np.asarray(state.getPositions().value_in_unit(unit.angstrom), dtype=float)
        potential = float(state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole))
        kinetic = float(state.getKineticEnergy().value_in_unit(unit.kilojoule_per_mole))
        reference = reference_positions
        _rotation, _translation, rmsd = kabsch(positions, reference)
        dof = 3 * system.getNumParticles() - system.getNumConstraints()
        return {
            "step": step_index,
            "time_ps": step_index * step_size_fs * 0.001,
            "temperature_k": temperature_from_kinetic(kinetic, dof),
            "potential_energy_kj": potential,
            "rmsd_angstrom": float(rmsd),
            "radius_of_gyration_angstrom": radius_of_gyration(positions),
        }

    reference_positions = np.asarray(context.getState(getPositions=True).getPositions().value_in_unit(unit.angstrom), dtype=float)
    frames = [sample(0)]
    for step in range(1, steps + 1):
        integrator.step(1)
        if step % sample_every == 0 or step == steps:
            frames.append(sample(step))

    summary = drift_summary(frames, seed=seed)
    summary.update(
        {
            "n_particles": system.getNumParticles(),
            "n_forces": system.getNumForces(),
            "temperature": temperature,
            "steps": steps,
            "step_size_fs": step_size_fs,
        }
    )
    return {"frames": frames, "summary": summary}


class StructureOpenmmMdStabilityStep(Step):
    provider = "operon-core"
    parameters_file = "structure_openmm_md_stability.StructureOpenmmMdStabilityStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_openmm_md_stability",
        "version": "1.0.0",
        "kind": "operator",
        "title": "OpenMM 短程分子动力学稳定性",
        "description": (
            "Minimise an implicit-solvent system with OpenMM and run a short Langevin "
            "trajectory, reporting temperature, potential energy, RMSD and radius of "
            "gyration per sampled frame."
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
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": False,
                },
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["openmm", "pdbfixer"],
        "dependency_imports": ["openmm", "pdbfixer"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        if not isinstance(form, Form) or form.data.size == 0:
            raise StepError("structure_openmm_md_stability: the structure form is empty")
        atom_dim = str(params.get("atom_dim", "atom"))
        field_dim = str(params.get("field_dim", "field"))
        if bool(params.get("remove_water", True)):
            form = without_water(form, atom_dim, field_dim)
        with tempfile.TemporaryDirectory(prefix="operon_md_") as folder:
            path = Path(folder) / "input.pdb"
            write_pdb(form, atom_dim, field_dim, path)
            result = md_run(
                path,
                ph=float(params.get("ph", 7.0)),
                temperature=float(params.get("temperature", 300.0)),
                friction=float(params.get("friction", 1.0)),
                step_size_fs=float(params.get("step_size_fs", 2.0)),
                steps=int(params.get("steps", 500)),
                sample_every=int(params.get("sample_every", 50)),
                minimize_iterations=int(params.get("minimize_iterations", 500)),
                equilibrate_steps=int(params.get("equilibrate_steps", 500)),
                seed=int(params.get("seed", 0)),
                forcefield_files=tuple(str(params.get("forcefield", "amber14-all.xml,implicit/gbn2.xml")).split(",")),
            )
        rows = drift_rows(result["frames"])
        data = np.zeros((len(rows), len(STATISTICS)), dtype=np.float32)
        for index, row in enumerate(rows):
            for column_index, name in enumerate(STATISTICS):
                data[index, column_index] = row[name]
        out_name = str(params.get("output", "frames"))
        ctx[out_name] = Form(
            data=data,
            dims=[str(params.get("frame_dim", "frame")), "statistic"],
            labels={
                str(params.get("frame_dim", "frame")): {f"frame{index}": index for index in range(len(rows))},
                "statistic": {name: index for index, name in enumerate(STATISTICS)},
            },
            info={"missing_code": np.nan, **result["summary"], "statistics": list(STATISTICS)},
        )
        self._export_data = {"rows": rows, "summary": result["summary"], "statistics": list(STATISTICS)}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
