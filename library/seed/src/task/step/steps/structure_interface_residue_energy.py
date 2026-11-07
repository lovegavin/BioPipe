"""structure_interface_residue_energy: per-residue interface energy decomposition."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step

COULOMB = 138.935456  # kJ nm / (mol e^2)


def pair_energy(qi: float, qj: float, si: float, sj: float, ei: float, ej: float, distance_nm: float) -> tuple[float, float]:
    """Return the Coulomb and Lennard-Jones pair energies in kJ/mol (OpenMM convention)."""

    if distance_nm <= 0:
        raise StepError("structure_interface_residue_energy: a pair distance is zero")
    coulomb = COULOMB * qi * qj / distance_nm
    sigma = 0.5 * (si + sj)
    epsilon = float(np.sqrt(max(ei, 0.0) * max(ej, 0.0)))
    ratio = sigma / distance_nm
    lj = 4.0 * epsilon * (ratio ** 12 - ratio ** 6)
    return float(coulomb), float(lj)


def prepare_structure(path: Path | str) -> dict:
    """Repair a structure with PDBFixer and extract Amber14 non-bonded parameters."""

    try:
        import openmm
        from openmm import unit
        from openmm.app import ForceField, NoCutoff, PDBFile
        from pdbfixer import PDBFixer
    except ImportError:
        raise StepError(
            "structure_interface_residue_energy: OpenMM and PDBFixer are required; "
            "install them with 'python -m pip install openmm pdbfixer'"
        ) from None
    source = Path(path).expanduser()
    if not source.is_file():
        raise StepError(f"structure_interface_residue_energy: structure_path {source} is not a file")
    fixer = PDBFixer(filename=str(source))
    fixer.findMissingResidues()
    fixer.findNonstandardResidues()
    fixer.replaceNonstandardResidues()
    fixer.removeHeterogens(False)
    fixer.findMissingAtoms()
    fixer.addMissingAtoms()
    fixer.addMissingHydrogens(7.0)
    system = ForceField("amber14-all.xml").createSystem(fixer.topology, nonbondedMethod=NoCutoff, constraints=None)
    nonbonded = [force for force in system.getForces() if force.__class__.__name__ == "NonbondedForce"][0]
    count = system.getNumParticles()
    charges = []
    sigma = []
    epsilon = []
    for index in range(count):
        charge, sigma_i, epsilon_i = nonbonded.getParticleParameters(index)
        charges.append(charge.value_in_unit(unit.elementary_charge))
        sigma.append(sigma_i.value_in_unit(unit.nanometer))
        epsilon.append(epsilon_i.value_in_unit(unit.kilojoule_per_mole))
    exceptions = set()
    for index in range(nonbonded.getNumExceptions()):
        a, b, _charge, _sigma, _epsilon = nonbonded.getExceptionParameters(index)
        exceptions.add((min(a, b), max(a, b)))
    positions = np.asarray(fixer.positions.value_in_unit(unit.nanometer), dtype=float)
    labels = []
    chains = []
    for atom in fixer.topology.atoms():
        residue = atom.residue
        labels.append(f"{residue.chain.id}:{residue.name}:{residue.id}")
        chains.append(residue.chain.id)
    if positions.shape[0] != count or len(labels) != count:
        raise StepError("structure_interface_residue_energy: repaired atom counts are inconsistent")
    return {
        "positions": positions,
        "charges": np.asarray(charges),
        "sigma": np.asarray(sigma),
        "epsilon": np.asarray(epsilon),
        "exceptions": exceptions,
        "labels": labels,
        "chains": chains,
    }


def interaction_arrays(data: dict, side_a: np.ndarray, side_b: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Vectorised Coulomb and LJ energies for all cross-side atom pairs."""

    positions = data["positions"]
    delta = positions[side_b][None, :, :] - positions[side_a][:, None, :]
    distance = np.sqrt(np.einsum("ijk,ijk->ij", delta, delta))
    sigma = 0.5 * (data["sigma"][side_a][:, None] + data["sigma"][side_b][None, :])
    epsilon = np.sqrt(np.clip(data["epsilon"][side_a][:, None] * data["epsilon"][side_b][None, :], 0.0, None))
    ratio = sigma / np.clip(distance, 1e-9, None)
    coulomb = COULOMB * data["charges"][side_a][:, None] * data["charges"][side_b][None, :] / np.clip(distance, 1e-9, None)
    lj = 4.0 * epsilon * (ratio ** 12 - ratio ** 6)
    mask = np.ones_like(distance, dtype=bool)
    for i_local, i in enumerate(side_a):
        for j_local, j in enumerate(side_b):
            if (min(int(i), int(j)), max(int(i), int(j))) in data["exceptions"]:
                mask[i_local, j_local] = False
    coulomb = np.where(mask, coulomb, 0.0)
    lj = np.where(mask, lj, 0.0)
    return coulomb, lj, mask, distance


class StructureInterfaceResidueEnergyStep(Step):
    provider = "operon-core"
    parameters_file = "structure_interface_residue_energy.StructureInterfaceResidueEnergyStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_interface_residue_energy",
        "version": "1.0.0",
        "kind": "operator",
        "title": "界面残基能量分解",
        "description": (
            "Decompose the vacuum Coulomb + Lennard-Jones interaction energy of a "
            "protein-protein interface into per-residue contributions, with an exact "
            "sum identity against the side totals."
        ),
        "category": "Structure",
        "icon": "ChartBar",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": [],
        "dependency_imports": ["openmm"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        data = prepare_structure(str(params.get("structure_path", "")))
        binder = set(str(params.get("binder_chains", "") or ""))
        target = set(str(params.get("target_chains", "") or ""))
        if not binder or not target:
            raise StepError("structure_interface_residue_energy: binder_chains and target_chains are required")
        if binder & target:
            raise StepError("structure_interface_residue_energy: binder_chains and target_chains overlap")
        chains = data["chains"]
        side_a = np.array([index for index, chain in enumerate(chains) if chain in binder], dtype=int)
        side_b = np.array([index for index, chain in enumerate(chains) if chain in target], dtype=int)
        if side_a.size == 0 or side_b.size == 0:
            raise StepError(f"structure_interface_residue_energy: the structure carries chains {sorted(set(chains))}")
        coulomb, lj, mask, distance = interaction_arrays(data, side_a, side_b)
        labels = np.asarray(data["labels"])
        contributions: dict[str, list[float]] = {}
        for i_local, i in enumerate(side_a):
            row = labels[side_a[i_local]]
            for j_local, j in enumerate(side_b):
                if not mask[i_local, j_local]:
                    continue
                for label in (labels[i], labels[j]):
                    entry = contributions.setdefault(str(label), [0.0, 0.0, 0])
                    entry[0] += float(coulomb[i_local, j_local]) / 2.0
                    entry[1] += float(lj[i_local, j_local]) / 2.0
                    entry[2] += 1
        rows = []
        names = {}
        for label, (c_term, l_term, count) in sorted(contributions.items(), key=lambda item: item[1][0] + item[1][1]):
            names[str(label)] = len(rows)
            rows.append([c_term, l_term, c_term + l_term, float(count)])
        if not rows:
            raise StepError("structure_interface_residue_energy: no cross-chain atom pair survives the exclusion mask")
        out = str(params.get("output", "energies"))
        ctx[out] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["residue", "statistic"],
            labels={"residue": names, "statistic": {"coulomb_kj": 0, "lj_kj": 1, "total_kj": 2, "n_contacts": 3}},
            info={
                "total_coulomb_kj": float(coulomb.sum()),
                "total_lj_kj": float(lj.sum()),
                "total_interaction_kj": float(coulomb.sum() + lj.sum()),
                "decomposed_total_kj": float(sum(row[2] for row in rows)),
                "n_residues": len(rows),
                "n_contacts": int(mask.sum()),
                "binder_chains": sorted(binder),
                "target_chains": sorted(target),
                "structure_path": str(Path(str(params.get("structure_path", ""))).expanduser()),
            },
        )
        self._export_data = {
            "total_coulomb_kj": float(coulomb.sum()),
            "total_lj_kj": float(lj.sum()),
            "total_interaction_kj": float(coulomb.sum() + lj.sum()),
            "decomposed_total_kj": float(sum(row[2] for row in rows)),
            "n_residues": len(rows),
            "n_contacts": int(mask.sum()),
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
