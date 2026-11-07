"""Nucleotide composition and sliding-window GC profile for DNA/RNA sequences."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step

_STATISTICS = ("gc_content", "gc3", "cpg_oe", "at_skew", "gc_window_std")


def _decode(form, sequence_dim: str, position_dim: str) -> list[str]:
    from src.task.step.steps._sequence_common import decode_sequences

    return decode_sequences(form, sequence_dim, position_dim)


def gc_content(sequence: str) -> float:
    """Fraction of G/C bases (U is treated as T)."""
    text = sequence.upper().replace("U", "T")
    if not text:
        raise StepError("sequence_gc_profile: at least one nucleotide is required")
    invalid = sorted({base for base in text if base not in "ACGTN"})
    if invalid:
        raise StepError(
            "sequence_gc_profile: '{}' is not a DNA/RNA base".format(",".join(invalid))
        )
    return (text.count("G") + text.count("C")) / len(text)


def gc3(sequence: str) -> float:
    """GC content of the third codon position for complete codons."""
    text = sequence.upper().replace("U", "T")
    if len(text) < 3:
        return float("nan")
    third = text[2::3]
    if not third:
        return float("nan")
    return (third.count("G") + third.count("C")) / len(third)


def cpg_observed_expected(sequence: str) -> float:
    """CpG observed/expected ratio (1.0 means no depletion)."""
    text = sequence.upper().replace("U", "T")
    length = len(text)
    if length < 2:
        return float("nan")
    cpg = sum(1 for first, second in zip(text, text[1:]) if first == "C" and second == "G")
    expected = text.count("C") * text.count("G") / length
    if expected <= 0.0:
        return float("nan")
    return cpg / expected


def at_skew(sequence: str) -> float:
    """AT skew (A - T) / (A + T)."""
    text = sequence.upper().replace("U", "T")
    a = text.count("A")
    t = text.count("T")
    if a + t == 0:
        return 0.0
    return (a - t) / (a + t)


def window_contents(sequence: str, window: int, step: int = 1) -> list[dict]:
    """Sliding-window GC content."""
    text = sequence.upper().replace("U", "T")
    if window < 1:
        raise StepError("sequence_gc_profile: window must be at least 1")
    if step < 1:
        raise StepError("sequence_gc_profile: step must be at least 1")
    if window > len(text):
        return []
    windows = []
    for start in range(0, len(text) - window + 1, step):
        chunk = text[start : start + window]
        windows.append(
            {
                "start": start + 1,
                "end": start + window,
                "gc": (chunk.count("G") + chunk.count("C")) / len(chunk),
            }
        )
    return windows


def composition_row(sequence: str, window: int = 50) -> tuple[tuple[float, ...], list[dict]]:
    """Return one summary row plus its sliding windows."""
    windows = window_contents(sequence, window)
    spread = float(np.std([item["gc"] for item in windows], ddof=1)) if len(windows) > 1 else 0.0
    row = (
        gc_content(sequence),
        gc3(sequence),
        cpg_observed_expected(sequence),
        at_skew(sequence),
        spread,
    )
    if any(value is not None and np.isfinite(value) for value in row) is False:
        raise StepError("sequence_gc_profile: the composition produced no finite value")
    return row, windows


class SequenceGcProfileStep(Step):
    """Nucleotide composition summary with a sliding GC window profile."""

    provider = "operon-core"
    parameters_file = "sequence_gc_profile.SequenceGcProfileStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_gc_profile",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Sequence GC Profile",
        "description": (
            "Summarises nucleotide composition: GC content, third-codon GC, CpG "
            "observed/expected ratio, AT skew and the spread of a sliding GC window, which "
            "supports ORF and primer design checks."
        ),
        "category": "Omics",
        "icon": "ChartLine",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "ndim": 2,
                    "dims": [
                        {"param": "sequence_dim", "default": "sequence"},
                        {"param": "position_dim", "default": "position"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "info": {
                        "representation": {"type": "string", "const": "sequence_codes"},
                    },
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
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (32 * 1024 * 1024, 0)

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        window = int(params.get("window", 50))
        sequences = _decode(inputs[0], sequence_dim, position_dim)
        valid = [text for text in sequences if text and not text.startswith("N")]
        if not valid:
            raise StepError("sequence_gc_profile: the input holds no nucleotide sequence")
        rows = []
        windows = []
        for text in valid:
            row, found = composition_row(text, window)
            rows.append(row)
            windows.append(found)
        data = np.asarray(rows, dtype=np.float32)
        labels = {str(index + 1): index for index in range(len(valid))}
        output = Form(
            data=data,
            dims=[sequence_dim, "statistic"],
            labels={
                sequence_dim: labels,
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "window": window,
                "windows": windows,
                "n_sequences": len(valid),
                "mean_gc": float(data[:, 0].mean()),
            },
            axis_info={},
        )
        output.validate()
        output_name = str(params.get("output", "gc"))
        ctx[output_name] = output
        self._export_data = {
            "n_sequences": len(valid),
            "window": window,
            "mean_gc": float(data[:, 0].mean()),
            "min_gc": float(data[:, 0].min()),
            "max_gc": float(data[:, 0].max()),
        }
        print(
            "[sequence_gc_profile] {} sequences, mean GC {:.3f}".format(len(valid), float(data[:, 0].mean()))
        )

    def export(self, ctx) -> dict:
        return dict(getattr(self, "_export_data", {}))
