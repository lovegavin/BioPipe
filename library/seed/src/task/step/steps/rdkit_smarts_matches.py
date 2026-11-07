"""Count SMARTS pattern matches for every molecule in a SMILES list."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from ._rdkit_common import build_molecules, molecule_labels, parse_smiles_text


def parse_patterns(text: str) -> list[str]:
    """Split the pattern text on newlines and semicolons and validate each SMARTS."""
    from rdkit import Chem

    patterns = [piece.strip() for piece in str(text).replace(";", "\n").splitlines()]
    patterns = [pattern for pattern in patterns if pattern]
    if not patterns:
        raise StepError("smarts is required; give one SMARTS pattern per line")
    parsed: list[str] = []
    for pattern in patterns:
        query = Chem.MolFromSmarts(pattern)
        if query is None:
            raise StepError(f"cannot parse SMARTS pattern {pattern!r}")
        if query.GetNumAtoms() == 0:
            raise StepError(f"SMARTS pattern {pattern!r} matches no atoms")
        parsed.append(pattern)
    return parsed


def count_matches(molecule, query, unique: bool) -> int:
    """Count the matches of ``query`` in ``molecule``."""
    matches = molecule.GetSubstructMatches(query, uniquify=bool(unique))
    return len(matches)


class RdkitSmartsMatchesStep(Step):
    """Count SMARTS pattern matches for every molecule in a SMILES list."""

    provider = "operon-core"
    parameters_file = "rdkit_smarts_matches.RdkitSmartsMatchesStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rdkit_smarts_matches",
        "version": "1.0.0",
        "kind": "operator",
        "title": "RDKit SMARTS Matches",
        "description": (
            "Match a list of SMARTS patterns against every input molecule and report the "
            "per-molecule match counts as a [molecule, pattern] matrix."
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
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24", "rdkit>=2022.9"],
        "dependency_imports": ["rdkit"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        smiles_text = str(ctx.step_params.get("smiles", ""))
        molecule_dim = str(ctx.step_params.get("molecule_dim", "molecule"))
        pattern_dim = str(ctx.step_params.get("pattern_dim", "pattern"))
        unique = bool(ctx.step_params.get("unique", True))
        output_name = str(ctx.step_params.get("output", "smarts_matches"))
        if molecule_dim == pattern_dim:
            raise StepError("molecule_dim and pattern_dim must differ")
        patterns = parse_patterns(str(ctx.step_params.get("smarts", "")))
        from rdkit import Chem

        queries = [Chem.MolFromSmarts(pattern) for pattern in patterns]
        entries = parse_smiles_text(smiles_text, "rdkit_smarts_matches")
        names = [name for name, _ in entries]
        molecules = build_molecules(smiles_text, "rdkit_smarts_matches")
        values = np.zeros((len(molecules), len(patterns)), dtype=np.float32)
        for row, (_, molecule) in enumerate(molecules):
            for column, query in enumerate(queries):
                values[row, column] = count_matches(molecule, query, unique)
        output = Form(
            data=values,
            dims=[molecule_dim, pattern_dim],
            labels={
                molecule_dim: molecule_labels(names, molecule_dim),
                pattern_dim: {pattern: index for index, pattern in enumerate(patterns)},
            },
            info={
                "missing_code": np.nan,
                "patterns": patterns,
                "smiles": [entry[1] for entry in entries],
                "n_molecules": len(molecules),
                "unique": bool(unique),
                "matches": {pattern: int(values[:, index].sum()) for index, pattern in enumerate(patterns)},
            },
        )
        output.validate()
        ctx[output_name] = output
        self._export_data = {
            "n_molecules": len(molecules),
            "n_patterns": len(patterns),
            "molecules_with_hits": int(np.count_nonzero(values.sum(axis=1))),
            "total_matches": int(values.sum()),
        }
        print(
            f"[rdkit_smarts_matches] {len(molecules)} molecules x {len(patterns)} patterns, "
            f"{int(values.sum())} matches"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
