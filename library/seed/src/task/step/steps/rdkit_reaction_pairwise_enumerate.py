"""Pairwise reaction enumeration over two reactant libraries.

``rdkit_reaction_smarts_apply`` applies a one-component reaction to each
molecule.  Amide couplings, Suzuki couplings and reductive aminations need two
reactants, so this operator enumerates the cross product of two SMILES
libraries, deduplicates the products and records their size.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._rdkit_common import build_molecules

_STATISTICS = ("heavy_atoms", "molecular_weight", "n_pairs")
_OPERATOR = "rdkit_reaction_pairwise_enumerate"


def reaction_from_smarts(text: str):
    """Parse a two-component reaction SMARTS."""

    from rdkit.Chem import AllChem

    if not str(text or "").strip():
        raise StepError(f"{_OPERATOR}: reaction_smarts is required")
    try:
        reaction = AllChem.ReactionFromSmarts(str(text).strip())
    except Exception as error:  # noqa: BLE001 - RDKit raises bare exceptions
        raise StepError(
            f"{_OPERATOR}: cannot parse reaction_smarts {text!r}: {error}"
        ) from error
    if reaction is None:
        raise StepError(f"{_OPERATOR}: cannot parse reaction_smarts {text!r}")
    if reaction.GetNumReactantTemplates() < 2:
        raise StepError(
            f"{_OPERATOR}: reaction_smarts must declare two reactant templates "
            f"(found {reaction.GetNumReactantTemplates()}); use "
            "rdkit_reaction_smarts_apply for one-component reactions"
        )
    return reaction


def enumerate_pairs(
    reaction,
    library_a: list[tuple[str, object]],
    library_b: list[tuple[str, object]],
    *,
    max_products: int = 100,
    max_products_per_pair: int = 20,
    dedupe: bool = True,
):
    """Enumerate products over the ``library_a x library_b`` cross product."""

    from rdkit import Chem
    from rdkit.Chem import Descriptors

    products: list[dict] = []
    seen: set[str] = set()
    pairs = 0
    truncated = False
    for name_a, molecule_a in library_a:
        for name_b, molecule_b in library_b:
            pairs += 1
            outcomes = reaction.RunReactants((molecule_a, molecule_b))
            produced = 0
            for outcome in outcomes:
                for product in outcome:
                    if product is None:
                        continue
                    try:
                        Chem.SanitizeMol(product)
                    except Exception:  # noqa: BLE001 - drop invalid products
                        continue
                    smiles = Chem.MolToSmiles(product)
                    if not smiles or (dedupe and smiles in seen):
                        continue
                    seen.add(smiles)
                    products.append(
                        {
                            "smiles": smiles,
                            "reactant_a": name_a,
                            "reactant_b": name_b,
                            "heavy_atoms": float(product.GetNumHeavyAtoms()),
                            "molecular_weight": float(Descriptors.MolWt(product)),
                        }
                    )
                    produced += 1
                if produced >= max_products_per_pair:
                    break
            if len(products) >= max_products:
                return products[:max_products], {"n_pairs": pairs, "truncated": True}
    return products, {"n_pairs": pairs, "truncated": False}


class RdkitReactionPairwiseEnumerateStep(Step):
    """Enumerate two-component reaction products across two libraries."""

    provider = "operon-core"
    parameters_file = (
        "rdkit_reaction_pairwise_enumerate."
        "RdkitReactionPairwiseEnumerateStep.parameters.json"
    )

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rdkit_reaction_pairwise_enumerate",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Pairwise reaction enumeration",
        "description": (
            "Apply a two-component reaction SMARTS to the cross product of two "
            "SMILES libraries, deduplicate the products and report heavy-atom "
            "count and molecular weight per product."
        ),
        "category": "Machine Learning",
        "icon": "Shuffle",
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
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24", "rdkit>=2022.9"],
        "dependency_imports": ["rdkit"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        text_a = str(params.get("reactants_a") or "")
        text_b = str(params.get("reactants_b") or "")
        smarts = str(params.get("reaction_smarts") or "")
        max_products = int(params.get("max_products") or 100)
        per_pair = int(params.get("max_products_per_pair") or 20)
        dedupe = bool(params.get("dedupe", True))
        out_name = str(params.get("output", "products")) or "products"

        if max_products < 1 or max_products > 5000:
            raise StepError(
                f"{_OPERATOR}: max_products must be between 1 and 5000"
            )
        if per_pair < 1:
            raise StepError(f"{_OPERATOR}: max_products_per_pair must be positive")

        library_a = build_molecules(text_a, _OPERATOR)
        library_b = build_molecules(text_b, _OPERATOR)
        reaction = reaction_from_smarts(smarts)
        products, stats = enumerate_pairs(
            reaction,
            library_a,
            library_b,
            max_products=max_products,
            max_products_per_pair=per_pair,
            dedupe=dedupe,
        )
        labels = {
            f"{item['reactant_a']}+{item['reactant_b']}:{index + 1}": index
            for index, item in enumerate(products)
        }
        data = np.zeros((len(products), len(_STATISTICS)), dtype=np.float32)
        for index, item in enumerate(products):
            data[index] = (
                item["heavy_atoms"],
                item["molecular_weight"],
                float(len(library_a) * len(library_b)),
            )
        ctx[out_name] = Form(
            data=data,
            dims=["product", "statistic"],
            labels={
                "product": labels,
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "reaction_smarts": smarts.strip(),
                "n_reactants_a": len(library_a),
                "n_reactants_b": len(library_b),
                "n_pairs": stats["n_pairs"],
                "n_products": len(products),
                "truncated": stats["truncated"],
                "products": [
                    {
                        "smiles": item["smiles"],
                        "reactant_a": item["reactant_a"],
                        "reactant_b": item["reactant_b"],
                        "heavy_atoms": item["heavy_atoms"],
                        "molecular_weight": item["molecular_weight"],
                    }
                    for item in products
                ],
            },
        )
        self._export_data = {
            "n_pairs": stats["n_pairs"],
            "n_products": len(products),
            "truncated": stats["truncated"],
            "reaction_smarts": smarts.strip(),
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
