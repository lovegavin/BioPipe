"""ETKDG conformer generation with MMFF94/UFF energy scoring."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._rdkit_common import build_molecules, molecule_labels, parse_smiles_text

_FORCE_FIELDS = ("MMFF94", "MMFF94s", "UFF")
_STATISTICS = (
    "n_conformers",
    "min_energy",
    "mean_energy",
    "energy_spread",
    "minimized",
)


class RdkitConformerEnergyStep(Step):
    provider = 'operon-core'
    """Multi-conformer embedding scored with an RDKit force field."""
    parameters_file = 'rdkit_conformer_energy.RdkitConformerEnergyStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'rdkit_conformer_energy',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'RDKit conformer energies',
     'category': 'Machine Learning',
     'icon': 'ChartScatter',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True,
                                         'info': {'missing_code': {'type': ['number', 'null']}}}}},
     'resources': {'memory_modes': ['full'],
                   'supports_cuda': False,
                   'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.24', 'rdkit>=2022.9'],
     'dependency_imports': ['rdkit'],
     'inputs_arity': 0,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Embed ETKDGv3 conformers per molecule and report the MMFF94/UFF energy distribution.'}

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        smiles_text = str(params.get("smiles", "") or "").strip()
        molecule_dim = str(params.get("molecule_dim", "molecule"))
        force_field = str(params.get("force_field", "MMFF94") or "MMFF94").strip()
        num_conformers = int(params.get("num_conformers", 5))
        max_iterations = int(params.get("max_iterations", 500))
        seed = int(params.get("random_seed", 20240517))
        minimize = bool(params.get("minimize", True))
        out_name = params.get("output", self.name)
        if not smiles_text:
            raise StepError(
                "rdkit_conformer_energy: smiles is required; give one "
                "'SMILES [name]' line per molecule"
            )
        if force_field not in _FORCE_FIELDS:
            raise StepError(
                f"rdkit_conformer_energy: force_field must be one of "
                f"{list(_FORCE_FIELDS)}, got {force_field!r}"
            )
        if not 1 <= num_conformers <= 50:
            raise StepError(
                "rdkit_conformer_energy: num_conformers must be between 1 and 50"
            )
        if not 1 <= max_iterations <= 20000:
            raise StepError(
                "rdkit_conformer_energy: max_iterations must be between 1 and 20000"
            )
        try:
            from rdkit import Chem
            from rdkit.Chem import AllChem
        except ImportError as error:  # pragma: no cover - dependency guard
            raise StepError(
                f"rdkit_conformer_energy: rdkit is required ({error})"
            ) from error

        molecules = build_molecules(smiles_text, "rdkit_conformer_energy")
        pairs = parse_smiles_text(smiles_text, "rdkit_conformer_energy")
        rows: list[list[float]] = []
        conformer_energies: list[list[float]] = []
        for name, molecule in molecules:
            try:
                mol = Chem.AddHs(molecule)
                if force_field.startswith("MMFF") and not AllChem.MMFFHasAllMoleculeParams(mol):
                    raise StepError(
                        f"rdkit_conformer_energy: MMFF parameters are not "
                        f"available for molecule '{name}'"
                    )
                if force_field == "UFF" and not AllChem.UFFHasAllMoleculeParams(mol):
                    raise StepError(
                        f"rdkit_conformer_energy: UFF parameters are not "
                        f"available for molecule '{name}'"
                    )
                embedding = AllChem.ETKDGv3()
                embedding.randomSeed = seed
                embedding.pruneRmsThresh = 0.25
                embedding.numThreads = 1
                conf_ids = list(
                    AllChem.EmbedMultipleConfs(
                        mol, numConfs=num_conformers, params=embedding
                    )
                )
                if not conf_ids:
                    raise StepError(
                        f"rdkit_conformer_energy: no conformer could be embedded "
                        f"for molecule '{name}'"
                    )
                if force_field.startswith("MMFF"):
                    properties = AllChem.MMFFGetMoleculeProperties(
                        mol, mmffVariant=force_field
                    )
                else:
                    properties = None
                energies: list[float] = []
                for conf_id in conf_ids:
                    if force_field.startswith("MMFF"):
                        force = AllChem.MMFFGetMoleculeForceField(
                            mol, properties, confId=int(conf_id)
                        )
                    else:
                        force = AllChem.UFFGetMoleculeForceField(
                            mol, confId=int(conf_id)
                        )
                    if force is None:
                        raise StepError(
                            f"rdkit_conformer_energy: force field construction "
                            f"failed for molecule '{name}'"
                        )
                    if minimize:
                        force.Minimize(maxIts=max_iterations)
                    energies.append(float(force.CalcEnergy()))
            except StepError:
                raise
            except Exception as error:  # noqa: BLE001 - RDKit raises varied types
                raise StepError(
                    f"rdkit_conformer_energy: cannot embed molecule '{name}': "
                    f"{error}"
                ) from error

            values = np.asarray(energies, dtype=np.float64)
            rows.append([
                float(len(energies)),
                float(values.min()),
                float(values.mean()),
                float(values.max() - values.min()),
                1.0 if minimize else 0.0,
            ])
            conformer_energies.append([round(value, 6) for value in energies])

        out = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[molecule_dim, "statistic"],
            labels={
                molecule_dim: molecule_labels([name for name, _ in molecules], molecule_dim),
                "statistic": {
                    name: position for position, name in enumerate(_STATISTICS)
                },
            },
            info={
                "missing_code": np.nan,
                "force_field": force_field,
                "num_conformers": num_conformers,
                "max_iterations": max_iterations,
                "random_seed": seed,
                "minimize": minimize,
                "conformer_energies": conformer_energies,
                "input_smiles": [smiles for _, smiles in pairs],
                "energy_unit": "kcal/mol",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_molecules": len(molecules),
            "force_field": force_field,
            "num_conformers": num_conformers,
            "conformer_energies": conformer_energies,
            "statistics": list(_STATISTICS),
        }
        print(
            f"[rdkit_conformer_energy] {len(molecules)} molecules x "
            f"{num_conformers} conformers ({force_field})"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
