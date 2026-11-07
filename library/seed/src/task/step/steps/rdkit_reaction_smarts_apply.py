"""Apply a reaction SMARTS to a molecule collection."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._rdkit_common import build_molecules

STATISTICS = ("n_reactant_matches", "n_products", "mean_product_heavy_atoms")


def reaction_from_smarts(text: str):
    from rdkit.Chem import AllChem

    if not text or not text.strip():
        raise StepError("rdkit_reaction_smarts_apply: reaction_smarts is required")
    try:
        reaction = AllChem.ReactionFromSmarts(text.strip())
    except Exception as error:  # noqa: BLE001 - RDKit raises a bare Exception subclass
        raise StepError(
            f"rdkit_reaction_smarts_apply: cannot parse reaction_smarts {text!r}: {error}"
        ) from error
    if reaction is None:
        raise StepError(f"rdkit_reaction_smarts_apply: cannot parse reaction_smarts {text!r}")
    return reaction


def product_smiles(reaction, molecule, max_products: int) -> list[str]:
    products, _ = reaction_products(reaction, molecule, max_products)
    return products


def reaction_products(reaction, molecule, max_products: int):
    from rdkit import Chem

    products: list[str] = []
    outcomes = reaction.RunReactants((molecule,))
    matched = len(outcomes)
    for outcome in outcomes:
        for product in outcome:
            if product is None:
                continue
            try:
                Chem.SanitizeMol(product)
            except Exception:  # noqa: BLE001 - invalid products are dropped
                continue
            smiles = Chem.MolToSmiles(product)
            if smiles and smiles not in products:
                products.append(smiles)
        if len(products) >= max_products:
            break
    return products[:max_products], matched


class RdkitReactionSmartsApplyStep(Step):
    provider = "operon-core"
    parameters_file = "rdkit_reaction_smarts_apply.RdkitReactionSmartsApplyStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rdkit_reaction_smarts_apply",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Reaction SMARTS application",
        "description": "Applies one or more reaction SMARTS to a SMILES collection and counts products.",
        "category": "Machine Learning",
        "icon": "ArrowsDownUp",
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

    def run(self, ctx, inputs) -> None:
        from rdkit import Chem
        from rdkit.Chem import Descriptors

        params = ctx.step_params
        smiles = str(params.get("smiles") or "")
        text = str(params.get("reaction_smarts") or "")
        molecule_dim = str(params.get("molecule_dim") or "molecule")
        max_products = int(params.get("max_products", 50))
        out_name = str(params["output"])

        if max_products < 1:
            raise StepError("rdkit_reaction_smarts_apply: max_products must be positive")

        reaction = reaction_from_smarts(text)
        molecules = build_molecules(smiles, "rdkit_reaction_smarts_apply")
        rows = []
        details = []
        for name, molecule in molecules:
            products, matched = reaction_products(reaction, molecule, max_products)
            heavy = [
                Chem.MolFromSmiles(product).GetNumHeavyAtoms()
                for product in products
                if Chem.MolFromSmiles(product) is not None
            ]
            rows.append([
                float(matched),
                float(len(products)),
                float(np.mean(heavy)) if heavy else 0.0,
            ])
            details.append(
                {"name": name, "smiles": Chem.MolToSmiles(molecule), "products": products,
                 "molecular_weight": float(Descriptors.MolWt(molecule))}
            )

        data = np.asarray(rows, dtype=np.float32)
        labels = {detail["name"]: index for index, detail in enumerate(details)}
        output = Form(
            data=data,
            dims=[molecule_dim, "statistic"],
            labels={molecule_dim: labels, "statistic": {name: index for index, name in enumerate(STATISTICS)}},
            info={
                "missing_code": float("nan"),
                "reaction_smarts": text.strip(),
                "n_molecules": len(details),
                "molecules": details,
            },
            axis_info={},
        )
        output.validate()
        ctx[out_name] = output
        self._export_data = {
            "n_molecules": len(details),
            "n_with_products": int(sum(1 for detail in details if detail["products"])),
            "reaction_smarts": text.strip(),
        }
        print(
            f"[rdkit_reaction_smarts_apply] {len(details)} molecules, "
            f"{self._export_data['n_with_products']} with products"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
