"""Six-frame open-reading-frame detection for nucleotide sequences."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences, reverse_complement

STOPS = {"TAA", "TAG", "TGA"}
STATISTICS = ("frame", "start", "end", "length", "has_start", "has_stop")


def frames(sequence: str):
    sequence = sequence.upper().replace("U", "T")
    yield "+1", sequence, False
    yield "+2", sequence, False
    yield "+3", sequence, False
    rc = reverse_complement(sequence, "dna")
    yield "-1", rc, True
    yield "-2", rc, True
    yield "-3", rc, True


def find_orfs(sequence: str, min_length: int, require_start: bool) -> list[dict]:
    orfs: list[dict] = []
    for name, frame, reverse in frames(sequence):
        offset = int(name[1]) - 1
        index = offset
        while index + 3 <= len(frame):
            codon = frame[index:index + 3]
            if codon != "ATG" and require_start:
                index += 3
                continue
            start = index
            stop = None
            position = index
            while position + 3 <= len(frame):
                if frame[position:position + 3] in STOPS:
                    stop = position
                    break
                position += 3
            end = stop if stop is not None else len(frame) - ((len(frame) - offset) % 3)
            length = end - start
            if length >= min_length:
                start_index = len(frame) - (end + 3) + 1 if reverse else start + 1
                end_index = len(frame) - start if reverse else end
                coding = frame[start:end]
                if reverse:
                    coding = coding.translate(str.maketrans("ACGT", "TGCA"))[::-1]
                orfs.append({
                    "frame": name,
                    "start": float(start_index),
                    "end": float(end_index),
                    "length": float(length),
                    "has_start": 1.0,
                    "has_stop": 1.0 if stop is not None else 0.0,
                    "codons": len(coding) // 3,
                    "protein": coding,
                })
            index = (stop + 3) if stop is not None else len(frame)
    orfs.sort(key=lambda row: (-row["length"], row["frame"], row["start"]))
    return orfs


class SequenceOrfFinderStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_orf_finder.SequenceOrfFinderStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_orf_finder",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Six-frame ORF finder",
        "description": "Finds open reading frames on both strands with a minimum length.",
        "category": "Omics",
        "icon": "ListBullets",
        "contracts": {
            "version": 1,
            "inputs": [{
                "version": 1,
                "numeric": True,
                "dims": [
                    {"param": "sequence_dim", "default": "sequence"},
                    {"param": "position_dim", "default": "position"},
                ],
                "labels": [],
                "parallel": [],
                "ndim": 2,
                "info": {"representation": {"type": "string", "const": "sequence_codes"}},
            }],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        form = inputs[0]
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim") or "sequence")
        position_dim = str(params.get("position_dim") or "position")
        orf_dim = str(params.get("orf_dim") or "orf")
        min_length = int(params.get("min_length", 30))
        require_start = bool(params.get("require_start", True))
        out_name = str(params["output"])

        if len(form.dims) != 2 or list(form.dims) != [sequence_dim, position_dim]:
            raise StepError(
                f"sequence_orf_finder: a sequence form with dims [{sequence_dim}, {position_dim}] "
                f"is required, got {list(form.dims)}"
            )
        if min_length < 3:
            raise StepError("sequence_orf_finder: min_length must be at least 3 nucleotides")

        sequences = [sequence for sequence in decode_sequences(form, sequence_dim, position_dim) if sequence]
        if not sequences:
            raise StepError("sequence_orf_finder: the form contains no nucleotides")

        rows: list[dict] = []
        for index, sequence in enumerate(sequences):
            cleaned = sequence.upper().replace("U", "T")
            if set(cleaned) - set("ACGTN"):
                raise StepError(f"sequence_orf_finder: sequence {index} contains non-nucleotide residues")
            for row in find_orfs(cleaned, min_length, require_start):
                row["sequence"] = index + 1
                rows.append(row)
        if not rows:
            raise StepError(
                f"sequence_orf_finder: no open reading frame of at least {min_length} nucleotides was found"
            )

        data = np.asarray([[row[name] for name in STATISTICS] for row in rows], dtype=np.float32)
        labels = {}
        for index, row in enumerate(rows):
            label = f"seq{row['sequence']}_{row['frame']}_{int(row['start'])}"
            suffix = 1
            while label in labels:
                label = f"seq{row['sequence']}_{row['frame']}_{int(row['start'])}_{suffix}"
                suffix += 1
            labels[label] = index
        output = Form(
            data=data,
            dims=[orf_dim, "statistic"],
            labels={orf_dim: labels, "statistic": {name: index for index, name in enumerate(STATISTICS)}},
            info={
                "missing_code": float("nan"),
                "min_length": min_length,
                "require_start": require_start,
                "n_orfs": len(rows),
                "n_sequences": len(sequences),
                "orfs": [
                    {"label": label, "frame": row["frame"], "start": int(row["start"]),
                     "end": int(row["end"]), "length": int(row["length"]),
                     "has_stop": bool(row["has_stop"]), "codons": row["codons"],
                     "protein": row["protein"]}
                    for label, row in zip(labels, rows)
                ],
            },
            axis_info={},
        )
        output.validate()
        ctx[out_name] = output
        self._export_data = {
            "n_orfs": len(rows),
            "n_sequences": len(sequences),
            "longest": int(max(row["length"] for row in rows)),
            "min_length": min_length,
        }
        print(
            f"[sequence_orf_finder] {len(rows)} ORFs across {len(sequences)} sequences, "
            f"longest {self._export_data['longest']} nt"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
