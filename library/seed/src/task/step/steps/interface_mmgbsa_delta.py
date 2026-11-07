"""Single-point MM/GBSA binding-energy estimate with force-term decomposition."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step import Step
from src.task.step.steps.structure_openmm_energy import write_pdb

_TERMS = ("bonded", "nonbonded", "gb", "other")


def parse_chains(text: str, role: str) -> tuple[str, ...]:
    names = tuple(part.strip().upper() for part in str(text).replace(";", ",").split(",") if part.strip())
    if not names:
        raise StepError(f"interface_mmgbsa_delta: {role} must name at least one chain")
    return names


def classify_force(name: str) -> str:
    if name in ("HarmonicBondForce", "HarmonicAngleForce", "PeriodicTorsionForce", "RBTorsionForce", "CMAPTorsionForce"):
        return "bonded"
    if name in ("NonbondedForce", "CustomNonbondedForce"):
        return "nonbonded"
    if name in ("CustomGBForce", "GBSAOBCForce"):
        return "gb"
    return "other"


def term_energies(system, context) -> dict[str, float]:
    """Return the potential energy split by force class for one context."""

    import openmm

    total = context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(openmm.unit.kilojoule_per_mole)
    terms = {name: 0.0 for name in _TERMS}
    for index, force in enumerate(system.getForces()):
        energy = context.getState(getEnergy=True, groups={index}).getPotentialEnergy().value_in_unit(
            openmm.unit.kilojoule_per_mole
        )
        terms[classify_force(force.__class__.__name__)] += energy
    return {"total": total, **terms}


def _systems(fixer, forcefield, keep_chains):
    from openmm.app import HBonds, Modeller, NoCutoff

    model = Modeller(fixer.topology, fixer.positions)
    drop = [atom for atom in model.topology.atoms() if atom.residue.chain.id not in keep_chains]
    model.delete(drop)
    system = forcefield.createSystem(model.topology, nonbondedMethod=NoCutoff, constraints=HBonds)
    for index, force in enumerate(system.getForces()):
        force.setForceGroup(index)
    return system, model.positions


def mmgbsa_terms(pdb_path: Path, *, forcefield_name: str, implicit: str, ph: float, binder: tuple[str, ...], target: tuple[str, ...]) -> dict:
    from openmm import Context, LangevinMiddleIntegrator, Platform, unit
    from openmm.app import ForceField
    from pdbfixer import PDBFixer

    fixer = PDBFixer(filename=str(pdb_path))
    fixer.findMissingResidues()
    fixer.findNonstandardResidues()
    fixer.replaceNonstandardResidues()
    fixer.findMissingAtoms()
    fixer.addMissingAtoms()
    fixer.addMissingHydrogens(ph)
    present = {chain.id for chain in fixer.topology.chains()}
    unknown = [name for name in (*binder, *target) if name not in present]
    if unknown:
        raise StepError(f"interface_mmgbsa_delta: chain(s) {unknown} are not in the structure; found {sorted(present)}")
    forcefield = ForceField(forcefield_name, implicit)

    def evaluate(chains):
        system, positions = _systems(fixer, forcefield, set(chains))
        integrator = LangevinMiddleIntegrator(300 * unit.kelvin, 1 / unit.picosecond, 0.002 * unit.picoseconds)
        context = Context(system, integrator, Platform.getPlatformByName("CPU"))
        context.setPositions(positions)
        return term_energies(system, context), system.getNumParticles()

    complex_terms, n_complex = evaluate((*binder, *target))
    binder_terms, n_binder = evaluate(binder)
    target_terms, n_target = evaluate(target)
    return {
        "complex": complex_terms,
        "binder": binder_terms,
        "target": target_terms,
        "n_complex": n_complex,
        "n_binder": n_binder,
        "n_target": n_target,
    }


class InterfaceMmgbsaDeltaStep(Step):
    provider = "operon-core"
    parameters_file = "interface_mmgbsa_delta.InterfaceMmgbsaDeltaStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "interface_mmgbsa_delta",
        "version": "1.0.0",
        "kind": "operator",
        "title": "MM/GBSA binding energy",
        "description": "Single-point OpenMM MM/GBSA binding-energy estimate with bonded, nonbonded and GB term decomposition.",
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
        binder = parse_chains(params.get("binder_chains", ""), "binder_chains")
        target = parse_chains(params.get("target_chains", ""), "target_chains")
        overlap = set(binder) & set(target)
        if overlap:
            raise StepError(f"interface_mmgbsa_delta: chain(s) {sorted(overlap)} are in both sides")
        form = inputs[0]
        if form.data.size == 0:
            raise StepError("interface_mmgbsa_delta: the structure form is empty")
        ph = float(params.get("ph", 7.0))
        if not 0.0 < ph < 14.0:
            raise StepError("interface_mmgbsa_delta: ph must be between 0 and 14")
        workdir = Path(tempfile.mkdtemp(prefix="mmgbsa_"))
        pdb_path = workdir / "complex.pdb"
        atom_count = write_pdb(form, str(params.get("atom_dim", "atom")), str(params.get("field_dim", "field")), pdb_path)
        result = mmgbsa_terms(
            pdb_path,
            forcefield_name=str(params.get("forcefield", "amber14-all.xml")),
            implicit=str(params.get("implicit_model", "implicit/gbn2.xml")),
            ph=ph,
            binder=binder,
            target=target,
        )
        rows = []
        for term in (*_TERMS, "total"):
            complex_e = result["complex"][term]
            binder_e = result["binder"][term]
            target_e = result["target"][term]
            rows.append([complex_e, binder_e, target_e, complex_e - binder_e - target_e])
        data = np.array(rows, dtype=np.float32)
        term_dim = str(params.get("term_dim", "term"))
        labels = {name: index for index, name in enumerate((*_TERMS, "total"))}
        info = {
            "n_atoms": atom_count,
            "n_complex": result["n_complex"],
            "n_binder": result["n_binder"],
            "n_target": result["n_target"],
            "binder_chains": list(binder),
            "target_chains": list(target),
            "delta_total_kj": result["complex"]["total"] - result["binder"]["total"] - result["target"]["total"],
            "delta_vdw_electrostatics_kj": result["complex"]["nonbonded"] - result["binder"]["nonbonded"] - result["target"]["nonbonded"],
            "delta_gb_kj": result["complex"]["gb"] - result["binder"]["gb"] - result["target"]["gb"],
            "forcefield": str(params.get("forcefield", "amber14-all.xml")),
            "implicit_model": str(params.get("implicit_model", "implicit/gbn2.xml")),
            "ph": ph,
        }
        output = Form(
            data=data,
            dims=[term_dim, "statistic"],
            labels={term_dim: labels, "statistic": {"complex_kj": 0, "binder_kj": 1, "target_kj": 2, "delta_kj": 3}},
            info={"missing_code": np.nan, **info},
        )
        ctx[str(params.get("output", "energy"))] = output
        self._export_summary = {
            "dims": list(output.dims),
            "labels": {name: dict(mapping) for name, mapping in output.labels.items()},
            "info": info,
        }
