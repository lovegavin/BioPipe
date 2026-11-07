"""Mean-pooled ESM embeddings for protein sequences."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._esm_common import (
    load_esm,
    sequence_embeddings,
)
from src.task.step.steps._sequence_common import decode_sequences


class EsmEmbeddingStep(Step):
    """Embed protein sequences with a local ESM checkpoint."""

    provider = 'operon-core'
    parameters_file = 'esm_embedding.EsmEmbeddingStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'esm_embedding',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'ESM embeddings',
        'description': (
            'Load a local ESM2 checkpoint with fair-esm and return the '
            'mean-pooled final-layer embedding of every protein sequence in a '
            'sequence Form, ready for clustering, regression or visualization.'
        ),
        'category': 'Machine Learning',
        'icon': 'Brain',
        'contracts': {
            'version': 1,
            'inputs': [
                {
                    'version': 1,
                    'numeric': True,
                    'info': {
                        'missing_code': {'type': ['number', 'null']},
                        'representation': {
                            'type': 'string',
                            'const': 'sequence_codes',
                        },
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
                }
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
            'supports_cuda': True,
            'estimate': 'estimate_memory',
        },
        'dependencies': ['numpy>=1.24', 'torch>=2.0', 'fair-esm>=2.0'],
        'dependency_imports': ['torch', 'esm'],
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence")).strip() or "sequence"
        position_dim = str(params.get("position_dim", "position")).strip() or "position"
        out_name = params.get("output", self.name)

        form = inputs[0]
        if list(form.dims) != [sequence_dim, position_dim]:
            raise StepError(
                "esm_embedding: expected a ["
                f"{sequence_dim}, {position_dim}] sequence form, got "
                f"{list(form.dims)}"
            )
        sequences = decode_sequences(form, sequence_dim, position_dim)
        if not sequences:
            raise StepError("esm_embedding: the input form has no sequences")
        for index, sequence in enumerate(sequences):
            if not sequence:
                raise StepError(
                    f"esm_embedding: sequence {index} is empty after decoding"
                )

        model, alphabet, torch, device = load_esm(
            params.get("model_path", ""), params.get("device", "cpu"),
            "esm_embedding",
        )
        embeddings = sequence_embeddings(
            model, alphabet, torch, sequences, device
        )
        width = embeddings.shape[1]
        data = np.ascontiguousarray(embeddings, dtype=np.float32)
        form_out = Form(
            data=data,
            dims=[sequence_dim, "embedding"],
            labels={
                sequence_dim: dict(form.labels[sequence_dim]),
                "embedding": {
                    str(position): position for position in range(width)
                },
            },
            info={
                "model_path": str(params.get("model_path", "")),
                "device": device,
                "embedding_dim": width,
                "n_sequences": len(sequences),
                "pooling": "mean",
            },
        )
        ctx[out_name] = form_out
        self._export_data = {
            "sequence_dim": sequence_dim,
            "embedding_dim": width,
            "device": device,
            "n_sequences": len(sequences),
        }
        print(
            f"[{self.name}] {len(sequences)} sequences -> {width}-d embeddings "
            f"on {device}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
