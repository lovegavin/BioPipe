"""PAINS substructure alerts for a molecule set."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from ._rdkit_common import build_molecules, molecule_labels

_CATALOGUES = ("pains_a", "pains_b", "pains_c", "all")


def _catalogue(catalogue: str):
    from rdkit.Chem import FilterCatalog

    params = FilterCatalog.FilterCatalogParams()
    table = {
        "pains_a": FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS_A,
        "pains_b": FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS_B,
        "pains_c": FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS_C,
        "all": FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS,
    }
    params.AddCatalog(table[catalogue])
    return FilterCatalog.FilterCatalog(params)


def pain_alerts(molecules, catalogue: str) -> list[list[str]]:
    """Return the sorted alert descriptions for every molecule."""

    catalog = _catalogue(catalogue)
    alerts: list[list[str]] = []
    for _name, molecule in molecules:
        matches = catalog.GetMatches(molecule)
        alerts.append(sorted({str(match.GetDescription()) for match in matches}))
    return alerts


class PainsFilterStep(Step):
    """Flag PAINS substructures molecule by molecule."""

    provider = 'operon-core'
    parameters_file = 'pains_filter.PainsFilterStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'pains_filter',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'PAINS alert filter',
        'description': (
            'Screen a list of SMILES against the RDKit PAINS catalogues and '
            'report the number of matching substructure alerts per molecule '
            'together with the alert descriptions.'
        ),
        'category': 'Machine Learning',
        'icon': 'Funnel',
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
        catalogue = str(params.get("catalogue", "all")).strip().lower()
        out_name = params.get("output", self.name)

        if catalogue not in _CATALOGUES:
            raise StepError(
                "pains_filter: catalogue must be one of 'pains_a', 'pains_b', "
                "'pains_c' or 'all'"
            )

        molecules = build_molecules(params.get("smiles", ""), "pains_filter")
        names = molecule_labels([name for name, _molecule in molecules], molecule_dim)
        alerts = pain_alerts(molecules, catalogue)
        data = np.asarray([[len(item)] for item in alerts], dtype=np.float32)
        form_out = Form(
            data=data,
            dims=[molecule_dim, "statistic"],
            labels={
                molecule_dim: names,
                "statistic": {"n_alerts": 0},
            },
            info={
                "molecules": [name for name, _molecule in molecules],
                "alerts": {name: item for (name, _molecule), item in zip(molecules, alerts)},
                "catalogue": catalogue,
                "n_molecules": len(molecules),
                "n_flagged": int(sum(1 for item in alerts if item)),
            },
        )
        ctx[out_name] = form_out
        flagged = int(sum(1 for item in alerts if item))
        self._export_data = {
            "n_molecules": len(molecules),
            "n_flagged": flagged,
            "catalogue": catalogue,
        }
        print(f"[{self.name}] {len(molecules)} molecules, {flagged} flagged ({catalogue})")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
