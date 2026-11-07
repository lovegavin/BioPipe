"""Scan every single-residue substitution of a backbone chain with ESM-IF1."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from ._esm_if_common import chain_residues, load_esm_if, native_sequence

_AA_ALPHABET = "ACDEFGHIKLMNPQRSTVWY"
_STATISTICS = ("llr", "wt_log_prob", "mut_log_prob", "mutant_rank")


def parse_positions(text: str, length: int) -> list[int]:
    """Return the sorted, unique 1-based positions selected by ``text``."""
    if not str(text).strip():
        return list(range(1, length + 1))
    positions: list[int] = []
    for piece in str(text).replace(";", ",").split(","):
        piece = piece.strip()
        if not piece:
            continue
        if "-" in piece:
            start_text, _, end_text = piece.partition("-")
            try:
                start, end = int(start_text), int(end_text)
            except ValueError as error:
                raise StepError(f"position range {piece!r} is not of the form 12-16") from error
            if start > end:
                raise StepError(f"position range {piece!r} starts after it ends")
            positions.extend(range(start, end + 1))
        else:
            try:
                positions.append(int(piece))
            except ValueError as error:
                raise StepError(f"position {piece!r} is not an integer") from error
    if not positions:
        raise StepError("positions selected no residue")
    selected = sorted(set(positions))
    for position in selected:
        if position < 1 or position > length:
            raise StepError(f"position {position} is outside the chain of length {length}")
    return selected


def context_log_probs(model, alphabet, coords, sequence: str, torch) -> np.ndarray:
    """Return ``(length, vocabulary)`` log probabilities from one ESM-IF pass."""
    from esm.inverse_folding.util import CoordBatchConverter

    converter = CoordBatchConverter(alphabet)
    batch_coords, confidence, _, tokens, padding_mask = converter([(coords, None, sequence)])
    logits, _ = model.forward(batch_coords, padding_mask, confidence, tokens[:, :-1])
    # The inverse-folding decoder returns (batch, vocabulary, position); positions run
    # along the last axis because it is driven by the incremental decoder.
    log_probs = torch.log_softmax(logits[0].transpose(0, 1), dim=-1)
    values = log_probs.detach().cpu().numpy()
    if values.shape[0] < len(sequence):
        raise StepError(
            "ESM-IF returned fewer position scores than residues; check that the chain has "
            "complete N, CA and C backbone atoms"
        )
    return values[: len(sequence)]


def mutation_rows(
    sequence: str, log_probs: np.ndarray, alphabet, positions: list[int]
) -> list[tuple[str, int, float, float, float, int]]:
    """Build ``(label, position, llr, wild_type, mutant, rank)`` scan rows."""
    rows: list[tuple[str, int, float, float, float, int]] = []
    for position in positions:
        wild_type = sequence[position - 1]
        wild_type_log = float(log_probs[position - 1, alphabet.get_idx(wild_type)])
        alternatives = [
            (residue, float(log_probs[position - 1, alphabet.get_idx(residue)]))
            for residue in _AA_ALPHABET
            if residue != wild_type
        ]
        alternatives.sort(key=lambda item: (-item[1], item[0]))
        ranks = {residue: index + 1 for index, (residue, _) in enumerate(alternatives)}
        for residue, mutant_log in alternatives:
            rows.append(
                (
                    f"{wild_type}{position}{residue}",
                    position,
                    mutant_log - wild_type_log,
                    wild_type_log,
                    mutant_log,
                    ranks[residue],
                )
            )
    return rows


class EsmIfMutationScanStep(Step):
    """Score all single-residue substitutions of a backbone chain with ESM-IF1."""

    provider = "operon-core"
    parameters_file = "esm_if_mutation_scan.EsmIfMutationScanStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm_if_mutation_scan",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ESM-IF Mutation Scan",
        "description": (
            "Score every single-residue substitution of a protein chain with the official "
            "ESM-IF1 inverse-folding model and report the log-likelihood ratio of each mutant "
            "against the native residue."
        ),
        "category": "Machine Learning",
        "icon": "ArrowsDownUp",
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
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "dependencies": [
            "numpy>=1.24",
            "torch>=2.0",
            "fair-esm>=2.0",
            "biotite>=0.37",
        ],
        "dependency_imports": ["esm", "torch"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def _validate(self) -> tuple[str, str, str, str, str, int]:
        atom_dim = str(self.ctx.step_params.get("atom_dim", "atom"))
        field_dim = str(self.ctx.step_params.get("field_dim", "field"))
        chain = str(self.ctx.step_params.get("chain", "A"))
        model_path = str(self.ctx.step_params.get("model_path", ""))
        positions_text = str(self.ctx.step_params.get("positions", ""))
        max_positions = int(self.ctx.step_params.get("max_positions", 256))
        if not chain:
            raise StepError("chain must name the backbone chain to scan")
        if not model_path:
            raise StepError("model_path is required; point it at a local ESM-IF1 checkpoint")
        if max_positions < 1:
            raise StepError("max_positions must be at least 1")
        return atom_dim, field_dim, chain, model_path, positions_text, max_positions

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (8 * 1024**3, 0)

    def run(self, ctx: Context, inputs) -> None:
        self.ctx = ctx
        atom_dim, field_dim, chain, model_path, positions_text, max_positions = self._validate()
        form = inputs[0]
        output_name = str(ctx.step_params.get("output", "mutations"))
        if len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(f"a PDB form with dims [{atom_dim}, {field_dim}] is required")
        labels, resnames, backbone = chain_residues(form, field_dim, chain)
        sequence = native_sequence(resnames)
        positions = parse_positions(positions_text, len(sequence))
        if len(positions) > max_positions:
            raise StepError(
                f"the scan covers {len(positions)} positions but max_positions is {max_positions}"
            )
        model, alphabet, torch = load_esm_if(model_path, "esm_if_mutation_scan")
        log_probs = context_log_probs(model, alphabet, backbone, sequence, torch)
        rows = mutation_rows(sequence, log_probs, alphabet, positions)
        if not rows:
            raise StepError("the mutation scan produced no rows")
        values = np.array([[row[2], row[3], row[4], row[5]] for row in rows], dtype=np.float32)
        if not np.all(np.isfinite(values)):
            raise StepError("the model produced non-finite mutation scores")
        output = Form(
            data=values,
            dims=["mutation", "statistic"],
            labels={
                "mutation": {row[0]: index for index, row in enumerate(rows)},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "sequence": sequence,
                "chain": chain,
                "positions": positions,
                "model_path": model_path,
                "aa_order": _AA_ALPHABET,
                "metric": "log-likelihood ratio of the mutant against the native residue",
                "n_mutations": len(rows),
                "n_positions": len(positions),
            },
        )
        output.validate()
        ctx[output_name] = output
        self._export_data = {
            "n_mutations": len(rows),
            "n_positions": len(positions),
            "positions": positions,
            "sequence": sequence,
            "model_path": model_path,
            "top_mutations": [
                {"mutation": row[0], "llr": round(row[2], 6)}
                for row in sorted(rows, key=lambda row: -row[2])[:10]
            ],
        }
        print(
            f"[esm_if_mutation_scan] {len(rows)} substitutions over {len(positions)} positions "
            f"of chain {chain}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
