"""Kabsch superposition and per-residue RMSD for two PDB forms."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from ._protein_common import decode_column, has_column, heavy_atom_mask
from ._structure_common import (
    atom_coords,
    atom_keys,
    atom_names,
    insertion_codes,
    pick_chain_sides,
    residue_numbers,
)


def kabsch(mobile: np.ndarray, reference: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Return the rotation, translation and RMSD that map mobile onto reference."""

    mobile_center = mobile.mean(axis=0)
    reference_center = reference.mean(axis=0)
    covariance = (mobile - mobile_center).T @ (reference - reference_center)
    left, _singular, right_t = np.linalg.svd(covariance)
    sign = np.sign(np.linalg.det(right_t.T @ left.T))
    correction = np.diag([1.0, 1.0, sign])
    rotation = right_t.T @ correction @ left.T
    translation = reference_center - rotation @ mobile_center
    moved = (rotation @ mobile.T).T + translation
    rmsd = float(np.sqrt(np.mean(np.sum((moved - reference) ** 2, axis=1))))
    return rotation, translation, rmsd


def parse_fit_residues(text, present: set[str], operator: str) -> dict[str, list[tuple[int, int]]]:
    """Parse ``A:1-20,B:5`` into chain -> inclusive residue ranges."""

    spans: dict[str, list[tuple[int, int]]] = {}
    for token in str(text or "").replace(";", ",").split(","):
        piece = token.strip()
        if not piece:
            continue
        if ":" not in piece:
            raise StepError(
                f"{operator}: fit_residues entry {piece!r} is not of the form A:12-20 or A:12"
            )
        chain, spec = piece.split(":", 1)
        chain = chain.strip()
        spec = spec.strip()
        if not chain:
            raise StepError(f"{operator}: fit_residues entry {piece!r} does not name a chain")
        if chain not in present:
            raise StepError(
                f"{operator}: fit_residues chain {chain!r} is not in the structure "
                f"(available chains: {sorted(present)})"
            )
        if "-" in spec:
            start_text, end_text = spec.split("-", 1)
            try:
                start, end = int(start_text), int(end_text)
            except ValueError as error:
                raise StepError(
                    f"{operator}: fit_residues range {spec!r} is not numeric"
                ) from error
        else:
            try:
                start = end = int(spec)
            except ValueError as error:
                raise StepError(f"{operator}: fit_residues entry {piece!r} is not numeric") from error
        if end < start:
            raise StepError(f"{operator}: fit_residues range {spec!r} starts after it ends")
        spans.setdefault(chain, []).append((start, end))
    return spans


def _resident(chain: str, number: int, spans: dict[str, list[tuple[int, int]]]) -> bool:
    return any(start <= number <= end for start, end in spans.get(chain, ()))


class StructureRmsdStep(Step):
    """Superpose two structures and report per-residue RMSD."""

    provider = 'operon-core'
    parameters_file = 'structure_rmsd.StructureRmsdStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'structure_rmsd',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Structure RMSD',
        'description': (
            'Match atoms of a mobile and a reference PDB form by chain, residue '
            'number and atom name, fit the mobile structure with the Kabsch '
            'algorithm, and report the per-residue RMSD together with the '
            'global RMSD and the fitted rigid transform.'
        ),
        'category': 'Machine Learning',
        'icon': 'Ruler',
        'contracts': {
            'version': 1,
            'inputs': [
                {
                    'version': 1,
                    'numeric': True,
                    'info': {'encoders': {'type': 'object', 'optional': True}},
                    'dims': [
                        {'param': 'atom_dim', 'default': 'atom'},
                        {'param': 'field_dim', 'default': 'field'},
                    ],
                    'labels': [],
                    'parallel': [],
                    'ndim': 2,
                },
                {
                    'version': 1,
                    'numeric': True,
                    'info': {'encoders': {'type': 'object', 'optional': True}},
                    'dims': [
                        {'param': 'atom_dim', 'default': 'atom'},
                        {'param': 'field_dim', 'default': 'field'},
                    ],
                    'labels': [],
                    'parallel': [],
                    'ndim': 2,
                },
            ],
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
        'dependencies': ['numpy>=1.24'],
        'dependency_imports': ['numpy'],
        'inputs_arity': 2,
        'outputs': [],
        'output_parameter': 'output',
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim", "atom")).strip() or "atom"
        field_dim = str(params.get("field_dim", "field")).strip() or "field"
        residue_dim = str(params.get("residue_dim", "residue")).strip() or "residue"
        atom_filter = {
            token.strip().upper()
            for token in str(params.get("atom_names", "")).split(",")
            if token.strip()
        }
        min_rmsd = float(params.get("min_rmsd", 0.0))
        out_name = params.get("output", self.name)

        if min_rmsd < 0.0:
            raise StepError("structure_rmsd: min_rmsd must be zero or positive")

        mobile, reference = inputs[0], inputs[1]
        for label, form in (("mobile", mobile), ("reference", reference)):
            if list(form.dims) != [atom_dim, field_dim]:
                raise StepError(
                    f"structure_rmsd: expected a [{atom_dim}, {field_dim}] PDB form for "
                    f"the {label} structure, got {list(form.dims)}"
                )
            for column in ("x", "y", "z", "chain", "residue_number", "atom_name"):
                if not has_column(form, field_dim, column):
                    raise StepError(f"structure_rmsd: the {label} form has no '{column}' column")

        if not len(mobile.data):
            raise StepError("structure_rmsd: the mobile structure contains no atoms")
        if not len(reference.data):
            raise StepError("structure_rmsd: the reference structure contains no atoms")

        mobile_names = atom_names(mobile, field_dim)
        reference_names = atom_names(reference, field_dim)
        mobile_keys = atom_keys(mobile, field_dim, mobile_names)
        reference_keys = atom_keys(reference, field_dim, reference_names)

        mobile_mask = heavy_atom_mask(mobile, field_dim)
        reference_mask = heavy_atom_mask(reference, field_dim)
        if atom_filter:
            mobile_mask = mobile_mask & np.isin(mobile_names, list(atom_filter))
            reference_mask = reference_mask & np.isin(reference_names, list(atom_filter))
        if not mobile_mask.any() or not reference_mask.any():
            raise StepError("structure_rmsd: no atoms are left after the heavy-atom/atom-name filter")

        index_by_key: dict[tuple[str, int, str, str], int] = {}
        for index in np.flatnonzero(reference_mask).tolist():
            index_by_key.setdefault(reference_keys[index], index)

        mobile_rows: list[int] = []
        reference_rows: list[int] = []
        mobile_labels: list[str] = []
        for index in np.flatnonzero(mobile_mask).tolist():
            key = mobile_keys[index]
            partner = index_by_key.get(key)
            if partner is None:
                continue
            mobile_rows.append(index)
            reference_rows.append(int(partner))
            mobile_labels.append(
                f"{key[0]}:{decode_column(mobile, field_dim, 'resname')[index]}:{key[1]}{key[2]}"
            )

        if len(mobile_rows) < 3:
            raise StepError(
                "structure_rmsd: at least three matched atoms are required for a "
                f"superposition, found {len(mobile_rows)}"
            )

        mobile_coords = atom_coords(mobile, field_dim)[mobile_rows]
        reference_coords = atom_coords(reference, field_dim)[reference_rows]
        present_mobile = {str(value).strip() for value in decode_column(mobile, field_dim, "chain")}
        present_reference = {
            str(value).strip() for value in decode_column(reference, field_dim, "chain")
        }
        mobile_chains = sorted(present_mobile)
        reference_chains = sorted(present_reference)
        shared = [chain for chain in mobile_chains if chain in reference_chains]

        fit_spans = parse_fit_residues(
            params.get("fit_residues", ""),
            set(shared) or set(mobile_chains),
            "structure_rmsd",
        )
        if fit_spans:
            mobile_numbers = residue_numbers(mobile, field_dim)
            fit_mask = np.asarray(
                [
                    _resident(mobile_keys[row][0], int(mobile_numbers[row]), fit_spans)
                    for row in mobile_rows
                ]
            )
            if fit_mask.sum() < 3:
                raise StepError(
                    "structure_rmsd: fit_residues must cover at least three matched "
                    f"atoms, found {int(fit_mask.sum())}"
                )
        else:
            fit_mask = np.ones(len(mobile_rows), dtype=bool)

        rotation, translation, fitted_rmsd = kabsch(
            mobile_coords[fit_mask], reference_coords[fit_mask]
        )
        moved = (rotation @ mobile_coords.T).T + translation
        atom_rmsd = np.sqrt(np.sum((moved - reference_coords) ** 2, axis=1))

        residue_chain = np.asarray([key[0] for key in mobile_keys], dtype=object)
        residue_number = residue_numbers(mobile, field_dim)
        residue_code = np.asarray(
            [str(value).strip() for value in decode_column(mobile, field_dim, "resname")],
            dtype=object,
        )
        residue_code_i = insertion_codes(mobile, field_dim)

        order: list[str] = []
        totals: dict[str, list[float]] = {}
        for row, atom in enumerate(mobile_rows):
            label = (
                f"{residue_chain[atom]}:{residue_code[atom]}:"
                f"{int(residue_number[atom])}{residue_code_i[atom]}"
            )
            if label not in totals:
                order.append(label)
                totals[label] = []
            totals[label].append(float(atom_rmsd[row]))

        rows = [
            label
            for label in order
            if float(np.sqrt(np.mean(np.square(totals[label])))) >= min_rmsd - 1e-12
        ]
        rows.sort(
            key=lambda label: (
                -round(float(np.sqrt(np.mean(np.square(totals[label])))), 6),
                label,
            )
        )

        if rows:
            data = np.asarray(
                [
                    [float(np.sqrt(np.mean(np.square(totals[label])))), float(len(totals[label]))]
                    for label in rows
                ],
                dtype=np.float32,
            )
        else:
            data = np.zeros((0, 2), dtype=np.float32)
        form_out = Form(
            data=data,
            dims=[residue_dim, "statistic"],
            labels={
                residue_dim: {label: position for position, label in enumerate(rows)},
                "statistic": {"rmsd": 0, "n_atoms": 1},
            },
            info={
                "rmsd": fitted_rmsd,
                "fit_atoms": int(fit_mask.sum()),
                "matched_atoms": len(mobile_rows),
                "residues": len(rows),
                "rotation": rotation.tolist(),
                "translation": translation.tolist(),
                "mobile_chains": mobile_chains,
                "reference_chains": reference_chains,
                "atom_names": sorted(atom_filter) if atom_filter else "all",
                "min_rmsd": min_rmsd,
                "unit": "A",
            },
        )
        ctx[out_name] = form_out
        self._export_data = {
            "rmsd": round(fitted_rmsd, 4),
            "fit_atoms": int(fit_mask.sum()),
            "matched_atoms": len(mobile_rows),
            "residues": len(rows),
            "mobile_chains": mobile_chains,
            "reference_chains": reference_chains,
        }
        print(
            f"[{self.name}] {len(mobile_rows)} matched atoms: RMSD {fitted_rmsd:.3f} A "
            f"over {len(rows)} residues"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
