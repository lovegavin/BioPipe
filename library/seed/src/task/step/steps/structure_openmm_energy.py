"""OpenMM potential energy and energy minimization for a protein structure."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step import Step
from src.task.step.steps._protein_common import column_index, decode_column

_REQUIRED = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element")


def structure_columns(form: Form, field_dim: str) -> None:
    missing = [name for name in _REQUIRED if column_index(form, field_dim, name) < 0]
    if missing:
        raise StepError(f"structure_openmm_energy: the structure form has no {missing} column(s)")


def write_pdb(form: Form, atom_dim: str, field_dim: str, path: Path) -> int:
    """Write a fixed-column PDB from the atom/form pair and return the atom count."""

    structure_columns(form, field_dim)
    data = np.asarray(form.data)
    indexes = {name: column_index(form, field_dim, name) for name in _REQUIRED}
    resnames = decode_column(form, field_dim, "resname")
    chains = decode_column(form, field_dim, "chain")
    atom_names = decode_column(form, field_dim, "atom_name")
    elements = decode_column(form, field_dim, "element")
    lines: list[str] = []
    previous_chain = None
    for atom in range(data.shape[0]):
        chain = str(chains[atom])
        if previous_chain is not None and chain != previous_chain:
            lines.append("TER")
        previous_chain = chain
        number = int(round(float(data[atom, indexes["residue_number"]])))
        lines.append(
            f"ATOM  {atom + 1:5d} {str(atom_names[atom])[:4]:<4s} {str(resnames[atom])[:3]:>3s} {chain[:1]}{number:4d}    "
            f"{float(data[atom, indexes['x']]):8.3f}{float(data[atom, indexes['y']]):8.3f}{float(data[atom, indexes['z']]):8.3f}"
            f"  1.00  0.00          {str(elements[atom])[:2]:>2s}"
        )
    lines.extend(["TER", "END"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return data.shape[0]


def _load_openmm():
    try:
        from openmm import unit, LangevinMiddleIntegrator, Platform, Context, LocalEnergyMinimizer
        from openmm.app import ForceField, HBonds, NoCutoff
        from pdbfixer import PDBFixer
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise StepError(
            "structure_openmm_energy: openmm and pdbfixer are required; install them with "
            "'python -m pip install openmm pdbfixer'"
        ) from exc
    return unit, LangevinMiddleIntegrator, Platform, Context, LocalEnergyMinimizer, ForceField, HBonds, NoCutoff, PDBFixer


def gradient_norm(context) -> float:
    forces = context.getState(getForces=True).getForces().value_in_unit_system(__import__("openmm").unit.md_unit_system)
    return float(np.sqrt((np.asarray(forces) ** 2).sum()))


def energy_terms(context) -> float:
    import openmm

    return float(context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(openmm.unit.kilojoule_per_mole))


def run_openmm(
    pdb_path: Path,
    *,
    forcefield_files: tuple[str, ...],
    ph: float,
    minimize: bool,
    max_iterations: int,
    tolerance: float,
) -> dict:
    unit, LangevinMiddleIntegrator, Platform, Context, LocalEnergyMinimizer, ForceField, HBonds, NoCutoff, PDBFixer = _load_openmm()

    fixer = PDBFixer(filename=str(pdb_path))
    fixer.findMissingResidues()
    fixer.findNonstandardResidues()
    fixer.replaceNonstandardResidues()
    fixer.removeHeterogens(True)
    fixer.findMissingAtoms()
    missing_atoms = sum(len(atoms) for atoms in fixer.missingAtoms.values())
    missing_terminals = len(fixer.missingTerminals)
    fixer.addMissingAtoms()
    fixer.addMissingHydrogens(ph)

    forcefield = ForceField(*forcefield_files)
    system = forcefield.createSystem(fixer.topology, nonbondedMethod=NoCutoff, constraints=HBonds)
    integrator = LangevinMiddleIntegrator(300 * unit.kelvin, 1 / unit.picosecond, 0.002 * unit.picoseconds)
    context = Context(system, integrator, Platform.getPlatformByName("CPU"))
    context.setPositions(fixer.positions)
    initial_energy = energy_terms(context)
    initial_gradient = gradient_norm(context)
    final_energy = initial_energy
    final_gradient = initial_gradient
    if minimize:
        LocalEnergyMinimizer.minimize(context, tolerance, max_iterations)
        final_energy = energy_terms(context)
        final_gradient = gradient_norm(context)
    return {
        "initial_energy": initial_energy,
        "final_energy": final_energy,
        "initial_gradient": initial_gradient,
        "final_gradient": final_gradient,
        "n_particles": system.getNumParticles(),
        "n_forces": system.getNumForces(),
        "missing_atoms": missing_atoms,
        "missing_terminals": missing_terminals,
    }


class StructureOpenmmEnergyStep(Step):
    provider = "operon-core"
    parameters_file = "structure_openmm_energy.StructureOpenmmEnergyStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_openmm_energy",
        "version": "1.0.0",
        "kind": "operator",
        "title": "OpenMM potential energy",
        "description": "Build an OpenMM system for a protein structure and report the potential energy, optionally minimized.",
        "category": "Structure",
        "icon": "BatteryFull",
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
            "outputs": [],
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": [],
        "dependency_imports": ["openmm", "pdbfixer"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim", "atom"))
        field_dim = str(params.get("field_dim", "field"))
        form = inputs[0]
        if form.data.size == 0:
            raise StepError("structure_openmm_energy: the structure form is empty")
        forcefield = str(params.get("forcefield", "amber14-all.xml"))
        implicit = str(params.get("implicit_model", "implicit/gbn2.xml"))
        ph = float(params.get("ph", 7.0))
        if not 0.0 < ph < 14.0:
            raise StepError("structure_openmm_energy: ph must be between 0 and 14")
        max_iterations = int(params.get("max_iterations", 300))
        if max_iterations < 1:
            raise StepError("structure_openmm_energy: max_iterations must be at least 1")
        tolerance = float(params.get("tolerance", 10.0))
        if tolerance <= 0:
            raise StepError("structure_openmm_energy: tolerance must be positive")
        minimize = bool(params.get("minimize", True))

        workdir = Path(tempfile.mkdtemp(prefix="openmm_"))
        pdb_path = workdir / "input.pdb"
        atom_count = write_pdb(form, atom_dim, field_dim, pdb_path)
        result = run_openmm(
            pdb_path,
            forcefield_files=(forcefield, implicit),
            ph=ph,
            minimize=minimize,
            max_iterations=max_iterations,
            tolerance=tolerance,
        )
        stage_dim = str(params.get("stage_dim", "stage"))
        stages = ["initial", "minimized"] if minimize else ["initial"]
        rows = [result["initial_energy"], result["final_energy"]][: len(stages)]
        gradients = [result["initial_gradient"], result["final_gradient"]][: len(stages)]
        data = np.array([[rows[i], gradients[i]] for i in range(len(rows))], dtype=np.float32)
        labels = {stages[i]: i for i in range(len(stages))}
        info = {
            "n_atoms": atom_count,
            "n_particles": result["n_particles"],
            "n_forces": result["n_forces"],
            "missing_atoms": result["missing_atoms"],
            "missing_terminals": result["missing_terminals"],
            "initial_energy": result["initial_energy"],
            "final_energy": result["final_energy"],
            "delta_energy": result["final_energy"] - result["initial_energy"],
            "forcefield": forcefield,
            "implicit_model": implicit,
            "ph": ph,
            "minimized": minimize,
        }
        output = Form(
            data=data,
            dims=[stage_dim, "statistic"],
            labels={stage_dim: labels, "statistic": {"potential_energy_kj": 0, "gradient_norm": 1}},
            info={"missing_code": np.nan, **info},
        )
        ctx[str(params.get("output", "energy"))] = output
        self._export_summary = {
            "dims": list(output.dims),
            "labels": {name: dict(mapping) for name, mapping in output.labels.items()},
            "info": info,
        }
