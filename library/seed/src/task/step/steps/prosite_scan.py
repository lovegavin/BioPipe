"""PROSITE-style motif scanning over protein sequences."""

from __future__ import annotations

import re

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences


def parse_patterns(text: str) -> list[tuple[str, str]]:
    """Parse ``PATTERN [name]`` lines into (pattern, name) pairs."""
    parsed: list[tuple[str, str]] = []
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        pattern = parts[0]
        name = " ".join(parts[1:]) if len(parts) > 1 else pattern
        parsed.append((pattern, name))
    if not parsed:
        raise StepError(
            "prosite_scan: patterns must contain at least one pattern "
            "('PATTERN [name]' per line)"
        )
    names = [name for _, name in parsed]
    if len(names) != len(set(names)):
        raise StepError("prosite_scan: pattern names must be unique")
    return parsed


def translate_pattern(pattern: str) -> str:
    """Translate a PROSITE-like pattern into a regular expression."""
    text = pattern.upper().strip()
    if not text:
        raise StepError("prosite_scan: a pattern must not be empty")
    pieces: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char in "-.":
            index += 1
            continue
        if char == "X":
            pieces.append(".")
            index += 1
            continue
        if char == "[":
            end = text.find("]", index)
            if end < 0:
                raise StepError(
                    f"prosite_scan: pattern '{pattern}' has an unclosed '['"
                )
            content = text[index + 1 : end]
            if not content:
                raise StepError(
                    f"prosite_scan: pattern '{pattern}' has an empty character set"
                )
            pieces.append("[" + content + "]")
            index = end + 1
            continue
        if char == "{":
            end = text.find("}", index)
            if end < 0:
                raise StepError(
                    f"prosite_scan: pattern '{pattern}' has an unclosed '{{'"
                )
            content = text[index + 1 : end]
            if not content:
                raise StepError(
                    f"prosite_scan: pattern '{pattern}' has an empty exclusion set"
                )
            pieces.append("[^" + content + "]")
            index = end + 1
            continue
        if char in "]}":
            raise StepError(
                f"prosite_scan: pattern '{pattern}' has an unexpected '{char}'"
            )
        if not char.isalpha() or char > "Z":
            raise StepError(
                f"prosite_scan: pattern '{pattern}' contains unsupported "
                f"character '{char}'"
            )
        pieces.append(char)
        index += 1
    if not pieces:
        raise StepError(
            f"prosite_scan: pattern '{pattern}' does not select any position"
        )
    return "".join(pieces)


def find_hits(sequence: str, expression: str) -> list[int]:
    """Return 1-based positions of every overlapping match."""
    try:
        compiled = re.compile(f"(?=({expression}))")
    except re.error as error:  # pragma: no cover - defensive
        raise StepError(f"prosite_scan: cannot compile pattern: {error}") from error
    return [match.start() + 1 for match in compiled.finditer(sequence)]


class PrositeScanStep(Step):
    """Scan protein sequences for PROSITE-like patterns."""

    provider = "operon-core"
    parameters_file = "prosite_scan.PrositeScanStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "prosite_scan",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Motif scan",
        "category": "Machine Learning",
        "icon": "ListBullets",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "sequence_dim", "default": "sequence"},
                        {"param": "position_dim", "default": "position"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                    "info": {
                        "representation": {"type": "string", "const": "sequence_codes"},
                        "alphabet": {"type": "string", "const": "protein"},
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
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "description": (
            "Translate PROSITE-like patterns (letters, x, [sets], {exclusions}) "
            "into regular expressions and report hit counts and positions."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence") or "sequence")
        position_dim = str(params.get("position_dim", "position") or "position")
        motif_dim = str(params.get("motif_dim", "motif") or "motif")
        out_name = params.get("output", self.name)
        patterns = parse_patterns(str(params.get("patterns", "") or ""))

        form = inputs[0]
        if list(form.dims) != [sequence_dim, position_dim]:
            raise StepError(
                "prosite_scan: sequence input expected "
                f"[{sequence_dim}, {position_dim}], got {list(form.dims)}"
            )
        sequences = decode_sequences(form, sequence_dim, position_dim)

        rows: list[list[float]] = []
        hits: dict[str, list[dict]] = {}
        for pattern, name in patterns:
            expression = translate_pattern(pattern)
            positions_per_sequence: list[list[int]] = []
            for sequence in sequences:
                positions_per_sequence.append(find_hits(sequence, expression))
            flat = [position for values in positions_per_sequence for position in values]
            n_sequences = sum(1 for values in positions_per_sequence if values)
            rows.append(
                [
                    float(len(flat)),
                    float(n_sequences),
                    float(flat[0]) if flat else np.nan,
                    float(np.mean(flat)) if flat else np.nan,
                ]
            )
            hits[name] = [
                {
                    "sequence": index,
                    "positions": positions,
                }
                for index, positions in enumerate(positions_per_sequence)
                if positions
            ]

        data = np.asarray(rows, dtype=np.float32)
        out = Form(
            data=data,
            dims=[motif_dim, "statistic"],
            labels={
                motif_dim: {name: index for index, (_, name) in enumerate(patterns)},
                "statistic": {
                    "n_hits": 0,
                    "n_sequences_hit": 1,
                    "first_position": 2,
                    "mean_position": 3,
                },
            },
            info={
                "missing_code": np.nan,
                "patterns": [pattern for pattern, _ in patterns],
                "expressions": [translate_pattern(pattern) for pattern, _ in patterns],
                "hits": hits,
                "n_sequences": len(sequences),
                "sequences": sequences,
                "representation": "prosite-like",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_motifs": len(patterns),
            "n_sequences": len(sequences),
            "total_hits": int(data[:, 0].sum()) if len(rows) else 0,
            "patterns": [pattern for pattern, _ in patterns],
        }
        print(
            f"[prosite_scan] {len(patterns)} pattern(s) over {len(sequences)} "
            f"sequence(s): {int(data[:, 0].sum())} hit(s)"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
