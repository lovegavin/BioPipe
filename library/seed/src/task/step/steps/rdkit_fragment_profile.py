"""Fragment profiles from BRICS or RECAP decomposition."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._rdkit_common import build_molecules, molecule_labels, parse_smiles_text


def clean_fragment(smiles: str) -> str:
    """Return a canonical fragment SMILES with attachment dummies removed."""
    from rdkit import Chem

    text = str(smiles)
    molecule = Chem.MolFromSmiles(text)
    if molecule is None:
        return text
    editable = Chem.RWMol(molecule)
    dummies = [atom.GetIdx() for atom in editable.GetAtoms() if atom.GetAtomicNum() == 0]
    for index in reversed(dummies):
        editable.RemoveAtom(index)
    try:
        cleaned = editable.GetMol()
        Chem.SanitizeMol(cleaned)
        canonical = Chem.MolToSmiles(cleaned)
    except Exception:
        return text
    return canonical or text


def brics_fragments(molecule) -> list[str]:
    """Distinct BRICS fragments of a molecule, dummies stripped and canonicalised."""
    from rdkit.Chem import BRICS

    try:
        raw = BRICS.BRICSDecompose(molecule, minFragmentSize=2)
    except Exception as error:  # pragma: no cover - RDKit failure path
        raise StepError(f"rdkit_fragment_profile: BRICS decomposition failed: {error}") from error
    return sorted({clean_fragment(item) for item in raw})


def recap_fragments(molecule) -> list[str]:
    """Distinct RECAP fragments of a molecule, dummies stripped and canonicalised."""
    from rdkit.Chem import Recap

    try:
        hierarchy = Recap.RecapDecompose(molecule)
    except Exception as error:  # pragma: no cover - RDKit failure path
        raise StepError(f"rdkit_fragment_profile: RECAP decomposition failed: {error}") from error
    collected: set[str] = set()
    stack = list(hierarchy.GetAllChildren().values())
    while stack:
        node = stack.pop()
        smiles = getattr(node, "smiles", None)
        if smiles:
            collected.add(clean_fragment(smiles))
        stack.extend(getattr(node, "children", {}).values())
    return sorted(collected)


class RdkitFragmentProfileStep(Step):
    """Count BRICS/RECAP fragments per molecule and build a fragment matrix."""

    provider = "operon-core"

    parameters_file = "rdkit_fragment_profile.RdkitFragmentProfileStep.parameters.json"


    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rdkit_fragment_profile",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Fragment profile",
        "description": (
            "Decompose molecules with BRICS or RECAP and report which canonical fragments occur, "
            "as a molecule-by-fragment presence matrix with per-molecule fragment counts."
        ),
        "category": "Machine Learning",
        "icon": "GridNine",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {
            "memory_modes": ["full"],
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24", "rdkit>=2022.9"],
        "dependency_imports": ["rdkit"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        text = str(params.get("smiles", ""))
        method = str(params.get("method", "brics"))
        molecule_dim = str(params.get("molecule_dim", "molecule"))
        fragment_dim = str(params.get("fragment_dim", "fragment"))
        output = str(params.get("output", "fragments"))

        if method not in {"brics", "recap"}:
            raise StepError(
                "rdkit_fragment_profile: method must be 'brics' or 'recap', "
                f"got {method!r}"
            )
        if molecule_dim == fragment_dim:
            raise StepError(
                "rdkit_fragment_profile: molecule_dim and fragment_dim must differ"
            )
        names = parse_smiles_text(text, "rdkit_fragment_profile")
        molecules = build_molecules(text, "rdkit_fragment_profile")
        if not molecules:
            raise StepError("rdkit_fragment_profile: no molecule could be built")

        decompose = brics_fragments if method == "brics" else recap_fragments
        per_molecule: list[list[str]] = []
        vocabulary: set[str] = set()
        for name, molecule in molecules:
            try:
                fragments = decompose(molecule)
            except StepError as error:
                raise StepError(f"rdkit_fragment_profile: molecule {name!r}: {error}") from error
            per_molecule.append(fragments)
            vocabulary.update(fragments)

        ordered = sorted(vocabulary)
        position = {fragment: index for index, fragment in enumerate(ordered)}
        data = np.zeros((len(molecules), len(ordered)), dtype=np.float32)
        for row, fragments in enumerate(per_molecule):
            for fragment in fragments:
                data[row, position[fragment]] = 1.0

        labels = {
            molecule_dim: molecule_labels([name for name, _ in molecules], molecule_dim),
            fragment_dim: {fragment: index for index, fragment in enumerate(ordered)},
        }
        info = {
            "missing_code": np.nan,
            "method": method,
            "fragments": ordered,
            "molecule_fragments": {
                name: fragments for (name, _), fragments in zip(molecules, per_molecule)
            },
            "n_molecules": len(molecules),
            "n_fragments": len(ordered),
            "fragment_counts": [len(fragments) for fragments in per_molecule],
        }
        out = Form(data=data, dims=[molecule_dim, fragment_dim], labels=labels, info=info)
        out.validate()
        ctx[output] = out
        self._export_data = {
            "n_molecules": len(molecules),
            "n_fragments": len(ordered),
            "fragment_counts": info["fragment_counts"],
            "method": method,
            "fragments": ordered,
            "molecules": info["molecule_fragments"],
        }
        print(
            f"[rdkit_fragment_profile] method={method} molecules={len(molecules)} "
            f"fragments={len(ordered)}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})


__all__ = ["RdkitFragmentProfileStep", "brics_fragments", "clean_fragment", "recap_fragments"]
