"""Masked marginal mutation effects from a local ESM checkpoint."""
from __future__ import annotations

import re
from typing import Callable

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

AA_ORDER = "ACDEFGHIKLMNPQRSTVWY"
_MUTATION = re.compile(r"^([ACDEFGHIKLMNPQRSTVWY])(\d+)([ACDEFGHIKLMNPQRSTVWY])$")


def parse_mutations(text: str, length: int) -> list[tuple[str, int, str]]:
    """Parse ``A12V,G4D`` into (wild type, 1-based position, mutant) tuples."""
    if not text or not str(text).strip():
        raise StepError("esm_masked_marginal: mutations must be a non-empty list")
    parsed: list[tuple[str, int, str]] = []
    for item in str(text).replace(";", ",").split(","):
        token = item.strip().upper()
        if not token:
            continue
        match = _MUTATION.match(token)
        if not match:
            raise StepError(
                "esm_masked_marginal: mutation "
                f"'{token}' is not of the form A12V (one-letter wild type, "
                "1-based position, one-letter mutant)"
            )
        wild_type, position_text, mutant = match.groups()
        position = int(position_text)
        if position < 1 or position > length:
            raise StepError(
                f"esm_masked_marginal: mutation '{token}' is outside the "
                f"sequence of length {length}"
            )
        parsed.append((wild_type, position, mutant))
    if not parsed:
        raise StepError("esm_masked_marginal: mutations must be a non-empty list")
    return parsed


def _check_wild_types(sequence: str, parsed) -> None:
    """Reject substitutions whose wild-type letter does not match the sequence."""
    for wild_type, position, mutant in parsed:
        residue = sequence[position - 1]
        if residue != wild_type:
            raise StepError(
                f"esm_masked_marginal: mutation '{wild_type}{position}{mutant}' "
                f"does not match wild-type residue '{residue}'"
            )


def masked_marginal(
    sequence: str,
    mutations: str,
    scorer: Callable[[int], np.ndarray],
) -> list[dict]:
    """Score mutations with a masked-marginal scorer over the 20 standard AAs.

    ``scorer(position)`` returns 20 raw model logits for the masked position in
    ``AA_ORDER``; they are normalised with a softmax after masking, exactly like
    ESM's masked-marginal protocol.
    """
    parsed = parse_mutations(mutations, len(sequence))
    _check_wild_types(sequence, parsed)
    rows: list[dict] = []
    for wild_type, position, mutant in parsed:
        index = position - 1
        logits = np.asarray(scorer(index), dtype=np.float64).reshape(-1)
        if logits.size != len(AA_ORDER):
            raise StepError(
                "esm_masked_marginal: scorer must return 20 logits, "
                f"got {logits.size}"
            )
        shifted = logits - logits.max()
        probabilities = np.exp(shifted)
        total = probabilities.sum()
        if not np.isfinite(total) or total <= 0:
            raise StepError("esm_masked_marginal: scorer produced invalid logits")
        probabilities = probabilities / total
        wild_probability = float(probabilities[AA_ORDER.index(wild_type)])
        mutant_probability = float(probabilities[AA_ORDER.index(mutant)])
        if wild_probability <= 0.0 or mutant_probability <= 0.0:
            log_ratio = float("-inf") if mutant_probability <= 0.0 else float("inf")
        else:
            log_ratio = float(np.log(mutant_probability / wild_probability))
        rows.append({
            "mutation": f"{wild_type}{position}{mutant}",
            "position": position,
            "wild_type": wild_type,
            "mutant": mutant,
            "wt_prob": wild_probability,
            "mut_prob": mutant_probability,
            "log_ratio": log_ratio,
        })
    return rows


class EsmMaskedMarginalStep(Step):
    provider = 'operon-core'
    """Score substitution effects with ESM masked marginals."""
    parameters_file = 'esm_masked_marginal.EsmMaskedMarginalStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'esm_masked_marginal',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'ESM masked marginal',
        'description': (
            'Mask one position at a time and report the wild-type and mutant '
            'probabilities and their log ratio under a local ESM checkpoint.'
        ),
        'category': 'Machine Learning',
        'icon': 'Brain',
        'contracts': {
            'version': 1,
            'inputs': [{
                'version': 1,
                'numeric': True,
                'info': {
                    'missing_code': {'type': ['number', 'null']},
                    'representation': {'type': 'string', 'const': 'sequence_codes'},
                    'alphabet_map': {'type': 'object'},
                    'unknown_code': {'type': 'integer'},
                },
                'dims': [
                    {'param': 'sequence_dim', 'default': 'sequence'},
                    {'param': 'position_dim', 'default': 'position'},
                ],
                'labels': [],
                'parallel': [],
                'ndim': 2,
            }],
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
            'supports_cuda': True,
            'estimate': 'estimate_memory',
        },
        'dependencies': ['torch>=2.0', 'fair-esm>=2.0'],
        'dependency_imports': ['torch', 'esm'],
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sequence_dim = ctx.step_params.get("sequence_dim", "sequence")
        position_dim = ctx.step_params.get("position_dim", "position")
        mutations = str(ctx.step_params.get("mutations", ""))
        model_path = str(ctx.step_params.get("model_path", "")).strip()
        sequence_index = int(ctx.step_params.get("sequence_index", 0))
        device = str(ctx.step_params.get("device", "cpu")).strip().lower()
        out_name = ctx.step_params.get("output", self.name)

        if len(form.dims) != 2 or list(form.dims) != [sequence_dim, position_dim]:
            raise StepError(
                f"esm_masked_marginal: expected dims "
                f"['{sequence_dim}', '{position_dim}'], got {form.dims}"
            )
        if not model_path:
            raise StepError("esm_masked_marginal: model_path is required")
        if device not in ("cpu", "cuda"):
            raise StepError("esm_masked_marginal: device must be 'cpu' or 'cuda'")

        sequences = _decode_sequences(form, sequence_dim)
        if sequence_index < 0 or sequence_index >= len(sequences):
            raise StepError(
                f"esm_masked_marginal: sequence_index {sequence_index} is out of "
                f"range for {len(sequences)} sequences"
            )
        sequence = sequences[sequence_index]
        _check_wild_types(sequence, parse_mutations(mutations, len(sequence)))

        import esm
        import torch

        if device == "cuda" and not torch.cuda.is_available():
            raise StepError(
                "esm_masked_marginal: device 'cuda' requested but CUDA is "
                "not available"
            )
        try:
            model, alphabet = esm.pretrained.load_model_and_alphabet_local(model_path)
        except Exception as exc:  # depends on the checkpoint file on disk
            raise StepError(
                f"esm_masked_marginal: could not load model from '{model_path}': {exc}"
            ) from exc
        model = model.eval().to(device)

        batch_converter = alphabet.get_batch_converter()
        _, _, tokens = batch_converter([("protein", sequence)])
        tokens = tokens.to(device)
        mask_index = alphabet.mask_idx
        aa_indices = [alphabet.get_idx(amino_acid) for amino_acid in AA_ORDER]
        cache: dict[int, np.ndarray] = {}

        def scorer(index: int) -> np.ndarray:
            if index not in cache:
                masked = tokens.clone()
                masked[0, index + 1] = mask_index
                with torch.no_grad():
                    logits = model(masked)["logits"]
                position_logits = logits[0, index + 1].detach().float().cpu().numpy()
                cache[index] = position_logits[aa_indices]
            return cache[index]

        rows = masked_marginal(sequence, mutations, scorer)
        rows.sort(key=lambda row: row["position"])

        data = np.array(
            [[row["wt_prob"], row["mut_prob"], row["log_ratio"]] for row in rows],
            dtype=np.float32,
        )
        ctx[out_name] = Form(
            data=data,
            dims=["mutation", "statistic"],
            labels={
                "mutation": {row["mutation"]: i for i, row in enumerate(rows)},
                "statistic": {"wt_prob": 0, "mut_prob": 1, "log_ratio": 2},
            },
            info={
                "missing_code": np.nan,
                "sequence": sequence,
                "sequence_index": sequence_index,
                "model_path": model_path,
                "device": device,
                "masked_positions": sorted({row["position"] for row in rows}),
                "aa_order": AA_ORDER,
            },
        )
        self._export_data = {
            "sequence_index": sequence_index,
            "sequence_length": len(sequence),
            "model_path": model_path,
            "device": device,
            "n_mutations": len(rows),
            "mutations": [row["mutation"] for row in rows],
            "log_ratios": [row["log_ratio"] for row in rows],
        }
        print(
            f"[esm_masked_marginal] {len(rows)} mutations scored on "
            f"{len(sequence)} residues ({device})"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _decode_sequences(form: Form, sequence_dim: str) -> list[str]:
    info = form.info or {}
    if info.get("representation") != "sequence_codes":
        raise StepError(
            "esm_masked_marginal: input must be a sequence_codes form "
            "(FastaReader output)"
        )
    mapping = info.get("alphabet_map")
    if not isinstance(mapping, dict) or not mapping:
        raise StepError("esm_masked_marginal: input form has no alphabet_map")
    unknown_code = int(info.get("unknown_code", 5))
    decode = {int(code): str(character) for character, code in mapping.items()}
    sequences: list[str] = []
    for row in np.asarray(form.data):
        characters: list[str] = []
        for value in row:
            if not np.isfinite(value):
                break
            code = int(round(float(value)))
            if code == unknown_code:
                raise StepError(
                    "esm_masked_marginal: the selected sequence contains "
                    "residues outside the alphabet; use a clean protein FASTA"
                )
            character = decode.get(code)
            if character is None:
                raise StepError(
                    f"esm_masked_marginal: sequence code {code} is not in "
                    "alphabet_map"
                )
            characters.append(character)
        sequences.append("".join(characters))
    if not sequences:
        raise StepError("esm_masked_marginal: input form has no sequences")
    return sequences
