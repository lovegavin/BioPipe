"""DSSP secondary-structure segments."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


import subprocess
import tempfile
from pathlib import Path

_SS_CODES = {"H": "helix", "G": "helix", "I": "helix", "E": "strand", "B": "strand", "T": "turn", "S": "bend", "-": "coil", " ": "coil", "P": "coil"}


def parse_dssp(text: str) -> list[dict]:
    records = []
    for line in text.splitlines():
        if len(line) < 17 or not line[:5].strip().isdigit():
            continue
        tokens = line.split()
        if len(tokens) < 6:
            continue
        try:
            number = int(tokens[1])
        except ValueError:
            continue
        records.append({"chain": tokens[2], "number": number, "residue": tokens[3], "code": tokens[4], "state": _SS_CODES.get(tokens[4], "coil")})
    return records


def segment_rows(records: list[dict]) -> list[dict]:
    if not records:
        raise StepError("structure_dssp_segments: DSSP reported no residue")
    segments = []
    current = None
    for record in records:
        key = (record["chain"], record["state"])
        if current is None or current["key"] != key:
            if current is not None:
                current.pop("key")
                segments.append(current)
            current = {"key": key, "chain": record["chain"], "state": record["state"], "start": record["number"], "end": record["number"], "codes": [record["code"]]}
        else:
            current["end"] = record["number"]
            current["codes"].append(record["code"])
    if current is not None:
        current.pop("key")
        segments.append(current)
    for segment in segments:
        segment["length"] = segment["end"] - segment["start"] + 1
        segment["codes"] = "".join(segment["codes"])
    return segments


def run_dssp(binary: str, structure: Path, workdir: Path, *, timeout: int = 300) -> str:
    output = workdir / "structure.dssp"
    command = [binary, "--output-format", "dssp", str(structure), str(output)]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise StepError(f"structure_dssp_segments: DSSP executable '{binary}' was not found on PATH; install mkdssp") from None
    except subprocess.TimeoutExpired:
        raise StepError(f"structure_dssp_segments: DSSP timed out after {timeout} s") from None
    if completed.returncode != 0:
        tail = ((completed.stderr or completed.stdout).strip().splitlines() or [""])[-1]
        raise StepError(f"structure_dssp_segments: DSSP failed with exit code {completed.returncode}: {tail}")
    if not output.is_file():
        raise StepError("structure_dssp_segments: DSSP produced no output")
    return output.read_text(errors="replace")


class StructureDsspSegmentsStep(Step):
    provider = "biopipe-core"
    parameters_file = "structure_dssp_segments.StructureDsspSegmentsStep.parameters.json"

    definition = {
        "protocol_version": 3,
        "id": "structure_dssp_segments",
        "version": "1.0.0",
        "kind": "operator",
        "title": "DSSP secondary-structure segments",
        "category": "Structure",
        "icon": "TreeStructure",
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "dims": [{"param": "atom_dim"}, {"param": "field_dim"}], "labels": [], "parallel": [], "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
            "outputs": [],
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        structure = Path(str(params["structure_path"])).expanduser()
        if not structure.is_file():
            raise StepError(f"structure_dssp_segments: structure_path {structure} is not a file")
        text = run_dssp(str(params.get("mkdssp_path") or "mkdssp"), structure, Path(tempfile.mkdtemp()), timeout=int(params.get("timeout_seconds", 300)))
        segments = segment_rows(parse_dssp(text))
        data = np.array([[s["length"]] for s in segments], dtype=np.float32)
        labels = {f"{s['chain']}:{s['state']}[{s['start']}-{s['end']}]": i for i, s in enumerate(segments)}
        total = sum(s["length"] for s in segments)
        fractions = {state: round(sum(s["length"] for s in segments if s["state"] == state) / total, 4) for state in ("helix", "strand", "coil", "turn", "bend")}
        ctx[params.get("output", "segments")] = Form(
            data=data,
            dims=["segment", "statistic"],
            labels={"segment": labels, "statistic": {"length": 0}},
            info={"missing_code": np.nan, "n_segments": len(segments), "n_residues": total, "fractions": fractions, "segments": [{k: s[k] for k in ("chain", "state", "start", "end", "length", "codes")} for s in segments], "mkdssp": str(params.get("mkdssp_path") or "mkdssp")},
        )
        self._export_data = {"n_segments": len(segments), "n_residues": total}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
