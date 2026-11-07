"""Maximum common substructure across a molecule set."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from ._rdkit_common import build_molecules


def mcs_parameters(
    atom_compare: str,
    bond_compare: str,
    ring_matches_ring_only: bool,
    complete_rings_only: bool,
    timeout: int,
):
    """Build RDKit MCSParameters from operator settings."""

    from rdkit.Chem import rdFMCS

    atom_table = {
        "any": rdFMCS.AtomCompare.CompareAny,
        "elements": rdFMCS.AtomCompare.CompareElements,
    }
    bond_table = {
        "any": rdFMCS.BondCompare.CompareAny,
        "strict": rdFMCS.BondCompare.CompareOrder,
    }
    params = rdFMCS.MCSParameters()
    params.AtomTyper = atom_table[atom_compare]
    params.BondTyper = bond_table[bond_compare]
    params.BondCompareParameters.RingMatchesRingOnly = ring_matches_ring_only
    params.BondCompareParameters.CompleteRingsOnly = complete_rings_only
    params.Timeout = int(timeout)
    return params


def count_matches(molecule, query) -> tuple[int, int]:
    """Return (matched atoms, number of distinct substructure matches)."""

    if query is None or query.GetNumAtoms() == 0:
        return 0, 0
    matches = molecule.GetSubstructMatches(query, uniquify=True)
    if not matches:
        return 0, 0
    return int(len(matches[0])), int(len(matches))


class RdkitMcsStep(Step):
    """Maximum common substructure across a set of molecules."""

    provider = 'operon-core'
    parameters_file = 'rdkit_mcs.RdkitMcsStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'rdkit_mcs',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Maximum common substructure',
        'description': (
            'Parse a set of SMILES and report the maximum common substructure '
            '(RDKit rdFMCS) with per-molecule matched and unmatched heavy atom '
            'counts.'
        ),
        'category': 'Machine Learning',
        'icon': 'GridNine',
        'contracts': {
            'version': 1,
            'inputs': [],
            'output': {
                'mode': 'declare',
                'schema': {
                    'ndim': 2,
                    'numeric': True,
                    'info_open': True,
                    'axis_info_open': True,
                },
            },
        },
        'resources': {
            'memory_modes': ['full'],
            'supports_cuda': False,
            'estimate': 'estimate_memory',
        },
        'dependencies': ['numpy>=1.24', 'rdkit>=2022.9'],
        'dependency_imports': ['rdkit'],
        'inputs_arity': 0,
        'outputs': [],
        'output_parameter': 'output',
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        molecule_dim = str(params.get("molecule_dim", "molecule")).strip() or "molecule"
        atom_compare = str(params.get("atom_compare", "elements")).strip().lower()
        bond_compare = str(params.get("bond_compare", "strict")).strip().lower()
        ring_only = bool(params.get("ring_matches_ring_only", True))
        complete_rings_only = bool(params.get("complete_rings_only", False))
        timeout = int(params.get("timeout_seconds", 30))
        out_name = params.get("output", self.name)

        if atom_compare not in ("any", "elements"):
            raise StepError("rdkit_mcs: atom_compare must be 'any' or 'elements'")
        if bond_compare not in ("any", "strict"):
            raise StepError("rdkit_mcs: bond_compare must be 'any' or 'strict'")
        if not 1 <= timeout <= 600:
            raise StepError("rdkit_mcs: timeout_seconds must be between 1 and 600")

        molecules = build_molecules(params.get("smiles", ""), "rdkit_mcs")
        if len(molecules) < 2:
            raise StepError("rdkit_mcs: at least two molecules are required")

        from rdkit import Chem
        from rdkit.Chem import rdFMCS

        mols = [molecule for _name, molecule in molecules]
        search = mcs_parameters(
            atom_compare, bond_compare, ring_only, complete_rings_only, timeout
        )
        result = rdFMCS.FindMCS(mols, search)
        if result.canceled:
            raise StepError(
                f"rdkit_mcs: the MCS search timed out after {timeout} seconds"
            )
        if result.numAtoms == 0:
            raise StepError(
                "rdkit_mcs: the molecules share no common substructure; "
                "relax atom_compare/bond_compare or ring constraints"
            )
        query = Chem.MolFromSmarts(result.smartsString)

        rows = []
        details = []
        for name, molecule in molecules:
            matched, matches = count_matches(molecule, query)
            heavy = int(molecule.GetNumHeavyAtoms())
            rows.append([float(matched), float(max(heavy - matched, 0))])
            details.append(
                {
                    "name": name,
                    "smiles": Chem.MolToSmiles(molecule),
                    "heavy_atoms": heavy,
                    "matched_atoms": matched,
                    "unmatched_atoms": max(heavy - matched, 0),
                    "n_matches": matches,
                }
            )

        label_list = [name for name, _molecule in molecules]
        form_out = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[molecule_dim, "statistic"],
            labels={
                molecule_dim: {label: index for index, label in enumerate(label_list)},
                "statistic": {"matched_atoms": 0, "unmatched_atoms": 1},
            },
            info={
                "missing_code": np.nan,
                "mcs_smarts": result.smartsString,
                "mcs_num_atoms": int(result.numAtoms),
                "mcs_num_bonds": int(result.numBonds),
                "atom_compare": atom_compare,
                "bond_compare": bond_compare,
                "ring_matches_ring_only": ring_only,
                "complete_rings_only": complete_rings_only,
                "timeout_seconds": timeout,
                "n_molecules": len(label_list),
                "molecules": details,
            },
        )
        ctx[out_name] = form_out
        self._export_data = {
            "n_molecules": len(label_list),
            "mcs_smarts": result.smartsString,
            "mcs_num_atoms": int(result.numAtoms),
            "mcs_num_bonds": int(result.numBonds),
            "mean_matched_atoms": round(float(np.mean([row[0] for row in rows])), 4),
        }
        print(
            f"[{self.name}] MCS of {len(label_list)} molecules: "
            f"{result.numAtoms} atoms / {result.numBonds} bonds"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
