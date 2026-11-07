"""Masked pseudo-likelihood scoring with a local ESM checkpoint."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._esm_common import AA_ORDER, load_esm, sequence_tokens
from ._sequence_common import decode_sequences

STATISTICS = ("log_prob",)


def masked_log_probs(model, alphabet, torch, sequence: str, device: str,
                     batch_size: int = 32) -> np.ndarray:
    """Return ``log P(x_t | x_-t)`` for every residue of ``sequence``.

    Each position is masked in turn and the model's distribution over the 20
    standard amino acids is scored at the masked position.  Positions are
    evaluated in batches so long sequences stay fast.
    """
    mapping = {amino_acid: alphabet.get_idx(amino_acid) for amino_acid in AA_ORDER}
    unknown = [index + 1 for index, residue in enumerate(sequence) if residue not in mapping]
    if unknown:
        raise StepError(
            "esm_pseudo_likelihood: sequence positions "
            f"{unknown[:5]} are not standard amino acids; use a clean protein "
            "FASTA"
        )
    tokens = sequence_tokens(alphabet, torch, sequence, device)
    length = len(sequence)
    indices = torch.tensor(
        [mapping[amino_acid] for amino_acid in sequence], device=device
    )
    scores = np.empty(length, dtype=np.float64)
    for start in range(0, length, batch_size):
        stop = min(start + batch_size, length)
        rows = tokens.repeat(stop - start, 1)
        positions = torch.arange(start, stop, device=device)
        rows[torch.arange(stop - start, device=device), positions + 1] = alphabet.mask_idx
        with torch.no_grad():
            logits = model(rows)["logits"]
        selected = logits[
            torch.arange(stop - start, device=device),
            positions + 1,
            :,
        ]
        log_probs = torch.log_softmax(selected, dim=-1)
        amino = torch.tensor(
            [mapping[amino_acid] for amino_acid in AA_ORDER], device=device
        )
        target = torch.tensor(
            [AA_ORDER.index(residue) for residue in sequence[start:stop]],
            device=device,
        )
        row_index = torch.arange(stop - start, device=device)
        amino_acid_log_probs = log_probs[:, amino]
        scores[start:stop] = (
            amino_acid_log_probs[row_index, target].detach().cpu().numpy()
        )
    if not np.all(np.isfinite(scores)):
        raise StepError("esm_pseudo_likelihood: model produced non-finite scores")
    return scores


class EsmPseudoLikelihoodStep(Step):
    provider = 'operon-core'
    """Masked pseudo-likelihood of protein sequences under a local ESM model."""
    parameters_file = (
        'esm_pseudo_likelihood.EsmPseudoLikelihoodStep.parameters.json'
    )
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'esm_pseudo_likelihood',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'ESM masked pseudo-likelihood',
     'category': 'Machine Learning',
     'icon': 'Brain',
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
     'dependency_imports': ['torch', 'esm'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Per-residue masked pseudo-likelihood log P(x_t | x_-t) of a protein sequence under a local ESM checkpoint; mean and total scores in info.'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        params = ctx.step_params
        seq_dim = str(params.get("sequence_dim", "sequence"))
        pos_dim = str(params.get("position_dim", "position"))
        model_path = str(params.get("model_path", "") or "").strip()
        device = str(params.get("device", "cpu") or "cpu").strip().lower()
        batch_size = int(params.get("batch_size", 32))
        out_name = params.get("output", self.name)
        if len(form.dims) != 2 or list(form.dims) != [seq_dim, pos_dim]:
            raise StepError(
                "esm_pseudo_likelihood: input form must have dims "
                f"[{seq_dim!r}, {pos_dim!r}], got {list(form.dims)!r}"
            )
        if batch_size < 1:
            raise StepError(
                "esm_pseudo_likelihood: batch_size must be at least 1"
            )
        sequences = decode_sequences(form, seq_dim, pos_dim)
        if not sequences:
            raise StepError("esm_pseudo_likelihood: input form has no sequences")
        if len(sequences) != 1:
            raise StepError(
                "esm_pseudo_likelihood: expects exactly one sequence per call, "
                f"got {len(sequences)}; split the form with select first"
            )
        sequence = sequences[0]
        model, alphabet, torch, resolved = load_esm(
            model_path, device, "esm_pseudo_likelihood"
        )
        scores = masked_log_probs(
            model, alphabet, torch, sequence, resolved, batch_size
        )
        length = len(sequence)
        out = Form(
            data=scores.reshape(length, 1).astype(np.float32),
            dims=["position", "statistic"],
            labels={
                "position": {str(index + 1): index for index in range(length)},
                "statistic": {"log_prob": 0},
            },
            info={
                "missing_code": np.nan,
                "sequence": sequence,
                "model_path": str(model_path),
                "device": resolved,
                "n_positions": length,
                "mean_log_prob": float(scores.mean()),
                "total_log_prob": float(scores.sum()),
                "metric": "masked_pseudo_likelihood",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "sequence": sequence,
            "n_positions": length,
            "mean_log_prob": float(scores.mean()),
            "total_log_prob": float(scores.sum()),
            "model_path": str(model_path),
            "device": resolved,
        }
        print(
            f"[esm_pseudo_likelihood] {length} positions, "
            f"mean log prob {scores.mean():.4f} on {resolved}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
