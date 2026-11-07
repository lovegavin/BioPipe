"""structure_dockq: CAPRI DockQ quality score for a protein-protein model."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.reader import read_source
from src.task.step.base import Step
from src.task.step.steps._protein_common import decode_column, residue_labels
from src.task.step.steps.structure_rmsd import kabsch

BACKBONE = {"N", "CA", "C", "O"}
STATISTICS = ("fnat", "irmsd", "lrmsd", "dockq")


def interface_score(fnat: float, irmsd: float, lrmsd: float) -> float:
    """CAPRI DockQ combination of Fnat, interface and ligand RMSD."""

    return (
        fnat
        + 1.0 / (1.0 + (irmsd / 1.5) ** 2)
        + 1.0 / (1.0 + (lrmsd / 8.5) ** 2)
    ) / 3.0


class AtomTable:
    """Light wrapper around the decoded columns of an atom form."""

    def __init__(self, form: Form, field_dim: str):
        self.coordinates = np.asarray(form.data[:, :3], dtype=float)
        self.chains = np.asarray([str(value) for value in decode_column(form, field_dim, "chain")])
        self.residues = np.asarray([str(value) for value in residue_labels(form, field_dim)])
        self.names = np.asarray([str(value).strip().upper() for value in decode_column(form, field_dim, "atom_name")])
        elements = decode_column(form, field_dim, "element")
        self.elements = np.asarray([str(value).strip().upper() for value in elements]) if elements is not None else np.array(["C"] * len(self.chains))


def _heavy(table: AtomTable, mask: np.ndarray) -> np.ndarray:
    return mask & np.asarray([element not in ("H",) for element in table.elements])


def native_contacts(receptor: AtomTable, ligand: AtomTable, cutoff: float) -> set[tuple[str, str]]:
    """Residue pairs closer than ``cutoff`` between receptor and ligand atoms."""

    from scipy.spatial import cKDTree

    receptor_heavy = _heavy(receptor, np.ones(len(receptor.chains), dtype=bool))
    ligand_heavy = _heavy(ligand, np.ones(len(ligand.chains), dtype=bool))
    tree = cKDTree(receptor.coordinates[receptor_heavy])
    pairs = tree.query_ball_tree(cKDTree(ligand.coordinates[ligand_heavy]), cutoff)
    receptor_residues = receptor.residues[receptor_heavy]
    ligand_residues = ligand.residues[ligand_heavy]
    contacts = set()
    for receptor_index, ligand_indices in enumerate(pairs):
        for ligand_index in ligand_indices:
            contacts.add((receptor_residues[receptor_index], ligand_residues[ligand_index]))
    return contacts


def interface_residues(receptor: AtomTable, ligand: AtomTable, cutoff: float) -> set[str]:
    """Residues on either side within ``cutoff`` of the partner."""

    from scipy.spatial import cKDTree

    tree_ligand = cKDTree(ligand.coordinates)
    tree_receptor = cKDTree(receptor.coordinates)
    receptor_hits = tree_ligand.query_ball_point(receptor.coordinates, cutoff)
    ligand_hits = tree_receptor.query_ball_point(ligand.coordinates, cutoff)
    residues = {receptor.residues[index] for index, hits in enumerate(receptor_hits) if hits}
    residues |= {ligand.residues[index] for index, hits in enumerate(ligand_hits) if hits}
    return residues


def backbone_rmsd(model: AtomTable, native: AtomTable, residues: set[str] | None = None) -> float:
    """Superpose matching backbone atoms and return the RMSD."""

    model_indices = {}
    native_indices = {}
    for index in range(len(model.chains)):
        if model.names[index] not in BACKBONE:
            continue
        if residues is not None and model.residues[index] not in residues:
            continue
        model_indices[(model.residues[index], model.names[index])] = index
    for index in range(len(native.chains)):
        if native.names[index] not in BACKBONE:
            continue
        if residues is not None and native.residues[index] not in residues:
            continue
        native_indices[(native.residues[index], native.names[index])] = index
    shared = sorted(set(model_indices) & set(native_indices))
    if len(shared) < 3:
        raise StepError("structure_dockq: fewer than three shared backbone atoms for the superposition")
    first = np.asarray([model.coordinates[model_indices[key]] for key in shared])
    second = np.asarray([native.coordinates[native_indices[key]] for key in shared])
    _rotation, _translation, rmsd = kabsch(first, second)
    return float(rmsd)


def split_sides(table: AtomTable, receptor_chains: set[str], ligand_chains: set[str]) -> tuple[AtomTable, AtomTable]:
    """Return two AtomTables restricted to the requested chains."""

    def subset(chains: set[str], label: str) -> AtomTable:
        mask = np.asarray([chain in chains for chain in table.chains])
        if not mask.any():
            raise StepError(f"structure_dockq: no atoms were found for the {label} chains {sorted(chains)}")
        view = AtomTable.__new__(AtomTable)
        view.coordinates = table.coordinates[mask]
        view.chains = table.chains[mask]
        view.residues = table.residues[mask]
        view.names = table.names[mask]
        view.elements = table.elements[mask]
        return view

    return subset(receptor_chains, "receptor"), subset(ligand_chains, "ligand")


def dockq_score(
    model: AtomTable,
    native: AtomTable,
    *,
    receptor_chains: set[str],
    ligand_chains: set[str],
    contact_cutoff: float = 5.0,
    interface_cutoff: float = 10.0,
) -> dict:
    """Compute Fnat, iRMSD, LRMSD and DockQ for a two-sided complex."""

    model_receptor, model_ligand = split_sides(model, receptor_chains, ligand_chains)
    native_receptor, native_ligand = split_sides(native, receptor_chains, ligand_chains)
    native_pairs = native_contacts(native_receptor, native_ligand, contact_cutoff)
    model_pairs = native_contacts(model_receptor, model_ligand, contact_cutoff)
    if not native_pairs:
        raise StepError("structure_dockq: the native structure has no receptor-ligand contacts at the cutoff")
    fnat = len(native_pairs & model_pairs) / len(native_pairs)
    interface = interface_residues(native_receptor, native_ligand, interface_cutoff)
    irmsd = backbone_rmsd(model, native, interface)
    receptor_only = {residue for residue in {r for r in model.residues} | {r for r in native.residues} if residue.split(":")[0] in receptor_chains}
    del receptor_only
    # ligand RMSD: superpose receptor backbone (all receptor residues), then measure ligand backbone
    lrmsd = _ligand_rmsd(model, native, receptor_chains, ligand_chains)
    return {
        "fnat": float(fnat),
        "irmsd": float(irmsd),
        "lrmsd": float(lrmsd),
        "dockq": float(interface_score(fnat, irmsd, lrmsd)),
        "n_native_contacts": len(native_pairs),
        "n_interface_residues": len(interface),
    }


def _ligand_rmsd(model: AtomTable, native: AtomTable, receptor_chains: set[str], ligand_chains: set[str]) -> float:
    """Superpose receptor backbone, then return the ligand backbone RMSD."""

    receptor_model = np.asarray([i for i in range(len(model.chains)) if model.names[i] in BACKBONE and model.chains[i] in receptor_chains])
    receptor_native = np.asarray([i for i in range(len(native.chains)) if native.names[i] in BACKBONE and native.chains[i] in receptor_chains])
    model_keys = {(model.residues[i], model.names[i]): i for i in receptor_model}
    native_keys = {(native.residues[i], native.names[i]): i for i in receptor_native}
    shared = sorted(set(model_keys) & set(native_keys))
    if len(shared) < 3:
        raise StepError("structure_dockq: fewer than three shared receptor backbone atoms")
    first = np.asarray([model.coordinates[model_keys[key]] for key in shared])
    second = np.asarray([native.coordinates[native_keys[key]] for key in shared])
    rotation, translation, _ = kabsch(first, second)
    ligand_model = np.asarray([i for i in range(len(model.chains)) if model.names[i] in BACKBONE and model.chains[i] in ligand_chains])
    ligand_native = np.asarray([i for i in range(len(native.chains)) if native.names[i] in BACKBONE and native.chains[i] in ligand_chains])
    model_keys = {(model.residues[i], model.names[i]): i for i in ligand_model}
    native_keys = {(native.residues[i], native.names[i]): i for i in ligand_native}
    shared = sorted(set(model_keys) & set(native_keys))
    if len(shared) < 3:
        raise StepError("structure_dockq: fewer than three shared ligand backbone atoms")
    moved = (rotation @ np.asarray([model.coordinates[model_keys[key]] for key in shared]).T).T + translation
    target = np.asarray([native.coordinates[native_keys[key]] for key in shared])
    return float(np.sqrt(np.mean(np.sum((moved - target) ** 2, axis=1))))


class StructureDockqStep(Step):
    provider = "operon-core"
    parameters_file = "structure_dockq.StructureDockqStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_dockq",
        "version": "1.0.0",
        "kind": "operator",
        "title": "DockQ 复合物质量评分",
        "description": (
            "Compute the CAPRI DockQ score for a protein-protein model against a "
            "native complex: native contact fraction, interface RMSD, ligand RMSD "
            "and their combination."
        ),
        "category": "Structure",
        "icon": "Intersect",
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
            raise StepError("structure_dockq: the model form is empty")
        reference = str(params.get("native_path", "")).strip()
        if not reference:
            raise StepError("structure_dockq: native_path is required")
        path = Path(reference).expanduser()
        if not path.is_file():
            raise StepError(f"structure_dockq: native_path {path} is not a file")
        field_dim = str(params.get("field_dim", "field"))
        receptor = {chain.strip() for chain in str(params.get("receptor_chains", "")).split(",") if chain.strip()}
        ligand = {chain.strip() for chain in str(params.get("ligand_chains", "")).split(",") if chain.strip()}
        if not receptor or not ligand:
            raise StepError("structure_dockq: receptor_chains and ligand_chains are required")
        native_form = read_source(str(path), ["atom", "field"], {"atom": "auto", "field": "builtin"})
        model = AtomTable(form, field_dim)
        native = AtomTable(native_form, field_dim)
        result = dockq_score(
            model,
            native,
            receptor_chains=receptor,
            ligand_chains=ligand,
            contact_cutoff=float(params.get("contact_cutoff", 5.0)),
            interface_cutoff=float(params.get("interface_cutoff", 10.0)),
        )
        output_dim = str(params.get("model_dim", "complex"))
        out_name = str(params.get("output", "dockq"))
        ctx[out_name] = Form(
            data=np.asarray([[result[name] for name in STATISTICS]], dtype=np.float32),
            dims=[output_dim, "statistic"],
            labels={output_dim: {str(params.get("model_label", "model")): 0}, "statistic": {name: index for index, name in enumerate(STATISTICS)}},
            info={
                "missing_code": np.nan,
                **result,
                "receptor_chains": sorted(receptor),
                "ligand_chains": sorted(ligand),
            },
        )
        self._export_data = {"result": result}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
