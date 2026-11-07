"""Zero-shot variant effect scan with a local ESM checkpoint."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._esm_common import AA_ORDER, load_esm, sequence_tokens
from ._sequence_common import decode_sequences

STATISTICS = ("llr", "wt_log_prob", "mut_log_prob", "mutant_rank")
_MAX_POSITIONS = 4096


def parse_positions(text: str, length: int) -> list[int]:
    """Parse a 1-based position expression such as ``12,14-16`` into indices."""
    raw = str(text or "").strip()
    if not raw:
        return list(range(length))
    positions: list[int] = []
    for chunk in raw.replace(";", ",").split(","):
        piece = chunk.strip()
        if not piece:
            continue
        if "-" in piece[1:]:
            start_text, end_text = piece.split("-", 1)
            try:
                start, end = int(start_text), int(end_text)
            except ValueError as error:
                raise StepError(
                    f"esm_variant_effect: position range {piece!r} is not "
                    "of the form 12-16"
                ) from error
            if start > end:
                raise StepError(
                    f"esm_variant_effect: position range {piece!r} starts after "
                    "it ends"
                )
            span = range(start, end + 1)
        else:
            try:
                value = int(piece)
            except ValueError as error:
                raise StepError(
                    f"esm_variant_effect: position {piece!r} is not an integer"
                ) from error
            span = range(value, value + 1)
        for value in span:
            if not 1 <= value <= length:
                raise StepError(
                    f"esm_variant_effect: position {value} is outside the "
                    f"sequence of length {length}"
                )
            positions.append(value - 1)
    if not positions:
        raise StepError(
            "esm_variant_effect: positions selected no residue; leave it empty "
            "to scan every position"
        )
    unique = sorted(set(positions))
    if len(unique) > _MAX_POSITIONS:
        raise StepError(
            f"esm_variant_effect: {len(unique)} positions exceed the "
            f"{_MAX_POSITIONS}-position limit"
        )
    return unique


def masked_position_log_probs(model, alphabet, torch, sequence: str,
                              device: str, positions: list[int],
                              batch_size: int = 16) -> np.ndarray:
    """Return ``log P(x_t = a | x_-t)`` over the 20 amino acids.

    The result has shape ``(len(positions), 20)`` in ``AA_ORDER`` order.
    """
    mapping = {amino_acid: alphabet.get_idx(amino_acid) for amino_acid in AA_ORDER}
    unknown = [index + 1 for index, residue in enumerate(sequence) if residue not in mapping]
    if unknown:
        raise StepError(
            "esm_variant_effect: sequence positions "
            f"{unknown[:5]} are not standard amino acids; use a clean protein "
            "FASTA"
        )
    tokens = sequence_tokens(alphabet, torch, sequence, device)
    amino = torch.tensor(
        [mapping[amino_acid] for amino_acid in AA_ORDER], device=device
    )
    result = np.empty((len(positions), len(AA_ORDER)), dtype=np.float64)
    for start in range(0, len(positions), batch_size):
        batch = positions[start : start + batch_size]
        rows = tokens.repeat(len(batch), 1)
        index = torch.arange(len(batch), device=device)
        positions_tensor = torch.tensor(batch, device=device)
        rows[index, positions_tensor + 1] = alphabet.mask_idx
        with torch.no_grad():
            logits = model(rows)["logits"]
        selected = logits[index, positions_tensor + 1, :]
        log_probs = torch.log_softmax(selected, dim=-1)
        result[start : start + len(batch)] = (
            log_probs[:, amino].detach().cpu().numpy()
        )
    if not np.all(np.isfinite(result)):
        raise StepError("esm_variant_effect: model produced non-finite log probabilities")
    return result


class EsmVariantEffectStep(Step):
    provider = 'operon-core'
    """Zero-shot amino-acid substitution effects from masked ESM predictions."""
    parameters_file = 'esm_variant_effect.EsmVariantEffectStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'esm_variant_effect',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'ESM variant effect scan',
     'category': 'Machine Learning',
     'icon': 'ArrowsDownUp',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {'representation': {'type': 'string', 'const': 'sequence_codes'},
                                        'alphabet': {'type': 'string', 'const': 'protein'},
                                        'missing_code': {'type': ['number', 'null']}},
                               'dims': [{'param': 'sequence_dim', 'default': 'sequence'},
                                        {'param': 'position_dim', 'default': 'position'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True,
                                         'info': {'missing_code': {'type': ['number', 'null']}}}}},
     'resources': {'memory_modes': ['full'],
                   'supports_cuda': True,
                   'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.24', 'torch>=2.0', 'fair-esm>=2.0'],
     'dependency_imports': ['esm', 'torch'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Mask each selected residue, read the ESM distribution over the 20 standard amino acids, and score all 19 single substitutions by log-likelihood ratio.'}

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        model_path = str(params.get("model_path", "") or "").strip()
        device = str(params.get("device", "cpu") or "cpu").strip().lower()
        positions_text = str(params.get("positions", "") or "")
        batch_size = int(params.get("batch_size", 16))
        out_name = params.get("output", self.name)
        if batch_size < 1:
            raise StepError("esm_variant_effect: batch_size must be positive")

        form = inputs[0]
        if len(form.dims) != 2 or list(form.dims) != [sequence_dim, position_dim]:
            raise StepError(
                "esm_variant_effect: expected a ["
                f"{sequence_dim}, {position_dim}] sequence form, got "
                f"{list(form.dims)}"
            )
        sequences = decode_sequences(form, sequence_dim, position_dim)
        if len(sequences) != 1:
            raise StepError(
                "esm_variant_effect: exactly one sequence is supported so the "
                f"mutation labels stay unique, got {len(sequences)}"
            )
        sequence = sequences[0]
        positions = parse_positions(positions_text, len(sequence))

        model, alphabet, torch, resolved_device = load_esm(
            model_path, device, "esm_variant_effect"
        )
        probs = masked_position_log_probs(
            model, alphabet, torch, sequence, resolved_device, positions,
            batch_size=batch_size,
        )

        residues = AA_ORDER
        labels: dict[str, int] = {}
        rows: list[list[float]] = []
        mutation_names: list[str] = []
        for row, position in enumerate(positions):
            wild_type = sequence[position]
            wt_index = residues.index(wild_type) if wild_type in residues else -1
            wt_log_prob = float(probs[row, wt_index]) if wt_index >= 0 else float("nan")
            order = np.argsort(-probs[row], kind="stable")
            rank_of = {int(index): rank + 1 for rank, index in enumerate(order)}
            for index, amino_acid in enumerate(residues):
                if amino_acid == wild_type:
                    continue
                mutation = f"{wild_type}{position + 1}{amino_acid}"
                labels[mutation] = len(mutation_names)
                mutation_names.append(mutation)
                rows.append([
                    float(probs[row, index] - wt_log_prob),
                    wt_log_prob,
                    float(probs[row, index]),
                    float(rank_of[index]),
                ])

        out = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["mutation", "statistic"],
            labels={
                "mutation": labels,
                "statistic": {
                    name: position for position, name in enumerate(STATISTICS)
                },
            },
            info={
                "missing_code": np.nan,
                "sequence": sequence,
                "sequence_index": 0,
                "model_path": model_path,
                "device": resolved_device,
                "positions": [position + 1 for position in positions],
                "n_mutations": len(mutation_names),
                "aa_order": AA_ORDER,
                "metric": "llr = log P(mutant | masked context) - log P(wild type | masked context)",
                "top_mutations": sorted(
                    zip(mutation_names, (row[0] for row in rows)),
                    key=lambda item: item[1],
                    reverse=True,
                )[:10],
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_mutations": len(mutation_names),
            "positions": len(positions),
            "sequence": sequence,
            "model_path": model_path,
            "top_mutations": out.info["top_mutations"],
        }
        print(
            f"[esm_variant_effect] {len(positions)} positions x 19 substitutions "
            f"= {len(mutation_names)} variants ({resolved_device})"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
