"""Redesign only the binder-side interface residues of a complex with ESM-IF."""

from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step
from src.task.step.steps._esm_if_common import (
    chain_residues,
    load_esm_if,
    native_sequence,
    residue_log_probs,
    validate_sequence,
)
from src.task.step.steps._protein_common import (
    column_index,
    decode_column,
    has_column,
    heavy_atom_mask,
    residue_labels,
)
from src.task.step.steps._structure_common import pick_chain_sides
from src.task.step.steps.esm_if_redesign import _fixed_partial


class EsmIfInterfaceRedesignStep(Step):
    provider = "operon-core"
    parameters_file = (
        "esm_if_interface_redesign.EsmIfInterfaceRedesignStep.parameters.json"
    )

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm_if_interface_redesign",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ESM-IF 界面重设计",
        "description": "只重设计复合物 binder 侧界面残基，其余位置保持原生序列。",
        "category": "Machine Learning",
        "icon": "Intersect",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "atom_dim", "default": "atom"},
                        {"param": "field_dim", "default": "field"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
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
            "supports_cuda": True,
            "estimate": "estimate_memory",
        },
        "dependencies": [
            "numpy>=1.24",
            "scipy>=1.10",
            "torch>=2.0",
            "fair-esm>=2.0",
            "biotite>=0.37",
        ],
        "dependency_imports": ["numpy", "scipy", "torch", "esm", "biotite"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list[Form]) -> None:
        params = ctx.step_params
        form = inputs[0] if inputs else None
        atom_dim = str(params.get("atom_dim", "atom"))
        field_dim = str(params.get("field_dim", "field"))
        if form is None or len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                "esm_if_interface_redesign: a structure form with dims "
                f"[{atom_dim}, {field_dim}] is required"
            )
        for name in ("x", "y", "z", "chain", "resname", "residue_number"):
            if not has_column(form, field_dim, name):
                raise StepError(
                    f"esm_if_interface_redesign: the structure form has no '{name}' column"
                )
        binder_text = str(params.get("binder_chains", "A"))
        target_text = str(params.get("target_chains", "")).strip()
        chain_values = decode_column(form, field_dim, "chain")
        binder_chains, target_chains = pick_chain_sides(
            set(chain_values), binder_text, target_text, "esm_if_interface_redesign"
        )
        if len(binder_chains) != 1:
            raise StepError(
                "esm_if_interface_redesign: binder_chains must select exactly one chain "
                "because ESM-IF redesigns a single chain"
            )
        chain = next(iter(binder_chains))
        cutoff = float(params.get("cutoff", 8.0))
        if not 0.0 < cutoff <= 20.0:
            raise StepError(
                "esm_if_interface_redesign: cutoff must be in (0, 20] angstrom"
            )
        model_path = str(params.get("model_path", "")).strip()
        temperature = float(params.get("temperature", 0.1))
        if not 0.01 <= temperature <= 2.0:
            raise StepError(
                "esm_if_interface_redesign: temperature must be in [0.01, 2.0]"
            )
        num_samples = int(params.get("num_samples", 4))
        if not 1 <= num_samples <= 16:
            raise StepError(
                "esm_if_interface_redesign: num_samples must be between 1 and 16"
            )
        seed = int(params.get("seed", 1))
        if seed < 0:
            raise StepError("esm_if_interface_redesign: seed must not be negative")
        output = str(params.get("output", "designs"))

        coordinates = np.column_stack(
            [
                np.asarray(form.data[:, column_index(form, field_dim, "x")], dtype=float),
                np.asarray(form.data[:, column_index(form, field_dim, "y")], dtype=float),
                np.asarray(form.data[:, column_index(form, field_dim, "z")], dtype=float),
            ]
        )
        heavy = heavy_atom_mask(form, field_dim)
        labels = residue_labels(form, field_dim)
        binder_rows = heavy & np.asarray(
            [value in binder_chains for value in chain_values], dtype=bool
        )
        target_rows = heavy & np.asarray(
            [value in target_chains for value in chain_values], dtype=bool
        )
        if not binder_rows.any() or not target_rows.any():
            raise StepError(
                "esm_if_interface_redesign: binder and target chains need heavy atoms"
            )
        tree = cKDTree(coordinates[target_rows])
        hits = tree.query_ball_point(coordinates[binder_rows], r=cutoff)
        interface_labels = {
            labels[index]
            for index, neighbours in zip(np.flatnonzero(binder_rows), hits)
            if neighbours
        }
        if not interface_labels:
            raise StepError(
                "esm_if_interface_redesign: no binder residue is within "
                f"{cutoff:.1f} angstrom of the target chains"
            )

        residue_labels_list, residue_names, coords = chain_residues(form, field_dim, chain)
        sequence = native_sequence(residue_names)
        validate_sequence(sequence, len(residue_labels_list), "esm_if_interface_redesign")
        design_positions = [
            index
            for index, label in enumerate(residue_labels_list)
            if label in interface_labels
        ]
        if not design_positions:
            raise StepError(
                "esm_if_interface_redesign: the interface has no residue of the selected "
                f"binder chain '{chain}'"
            )
        partial = _fixed_partial(sequence, design_positions)

        model, alphabet, torch = load_esm_if(model_path, "esm_if_interface_redesign")
        records: list[dict] = []
        for sample in range(1, num_samples + 1):
            torch.manual_seed(seed + sample - 1)
            designed = str(model.sample(coords, partial_seq=partial, temperature=temperature)).strip()
            if len(designed) != len(sequence):
                raise StepError(
                    "esm_if_interface_redesign: sample "
                    f"{sample} returned {len(designed)} residues for a "
                    f"{len(sequence)}-residue chain"
                )
            log_probs = residue_log_probs(model, alphabet, coords, designed)
            matched = sum(
                1
                for position in design_positions
                if designed[position] == sequence[position]
            )
            records.append(
                {
                    "sample": sample,
                    "sequence": designed,
                    "mean_log_prob": float(np.mean(log_probs)),
                    "interface_recovery": matched / len(design_positions),
                    "n_designed": len(design_positions),
                }
            )
        ctx[output] = Form(
            data=np.asarray(
                [
                    [
                        record["mean_log_prob"],
                        record["interface_recovery"],
                        float(record["n_designed"]),
                    ]
                    for record in records
                ],
                dtype=np.float32,
            ),
            dims=["sample", "statistic"],
            labels={
                "sample": {
                    f"sample_{record['sample']}": index
                    for index, record in enumerate(records)
                },
                "statistic": {
                    "mean_log_prob": 0,
                    "interface_recovery": 1,
                    "n_designed": 2,
                },
            },
            info={
                "missing_code": np.nan,
                "sequences": [record["sequence"] for record in records],
                "native_sequence": sequence,
                "chain": chain,
                "interface_positions": [position + 1 for position in design_positions],
                "n_interface": len(design_positions),
                "cutoff": cutoff,
                "model_path": model_path,
                "temperature": temperature,
                "seed": seed,
                "device": "cpu",
            },
        )
        self._export_data = {
            "chain": chain,
            "n_interface": len(design_positions),
            "interface_positions": [position + 1 for position in design_positions],
            "n_samples": len(records),
            "mean_log_prob": round(
                float(np.mean([record["mean_log_prob"] for record in records])), 4
            ),
            "mean_interface_recovery": round(
                float(np.mean([record["interface_recovery"] for record in records])), 4
            ),
            "sequences": [record["sequence"] for record in records],
            "cutoff": cutoff,
        }
        print(
            f"[esm_if_interface_redesign] {len(records)} samples, "
            f"{len(design_positions)} interface residues (chain {chain})"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
