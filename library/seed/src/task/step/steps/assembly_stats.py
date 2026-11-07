"""Assembly quality metrics through the official QUAST report."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences

_METRIC = "value"
_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")


def write_fasta(sequences: list[str], path: Path) -> None:
    lines: list[str] = []
    for index, sequence in enumerate(sequences):
        lines.append(f">contig{index + 1}")
        for start in range(0, len(sequence), 70):
            lines.append(sequence[start : start + 70])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def tool_environment(binary: str) -> dict:
    """Prepend the tool's own directory to PATH (QUAST calls sibling binaries)."""

    env = dict(os.environ)
    folder = str(Path(binary).expanduser().absolute().parent)
    env["PATH"] = folder + os.pathsep + env.get("PATH", "")
    return env


def parse_value(text: str) -> float | None:
    """Parse a QUAST report value, scaling kbp/Mbp suffixes."""

    raw = str(text).strip().replace(",", "")
    if not raw or raw.upper() in {"N/A", "NA", "-"}:
        return None
    match = _NUMBER.search(raw)
    if match is None:
        return None
    value = float(match.group(0))
    lowered = raw.lower()
    if "kbp" in lowered or lowered.endswith("kb"):
        value *= 1000.0
    elif "mbp" in lowered or lowered.endswith("mb"):
        value *= 1_000_000.0
    return value


def parse_report(text: str) -> dict[str, float]:
    """Parse QUAST ``report.tsv`` into a metric/value mapping."""

    metrics: dict[str, float] = {}
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) < 2:
            continue
        if fields[0].strip() == "Assembly":
            continue
        name = fields[0].strip()
        value = parse_value(fields[1])
        if value is None or not np.isfinite(value):
            continue
        metrics[name] = float(value)
    return metrics


def _launcher(binary: str, *, platform_name: str | None = None) -> list[str]:
    """Return the command prefix used to execute an external tool.

    Windows cannot execute a ``.py`` path directly, and on POSIX a script
    without the executable bit ignores its shebang.  In both cases run the
    script with the current interpreter instead.
    """
    name = os.name if platform_name is None else platform_name
    path = str(binary)
    if path.lower().endswith(".py") and (name == "nt" or not os.access(path, os.X_OK)):
        return [sys.executable, path]
    return [path]


def run_quast(
    binary: str,
    sequences: list[str],
    *,
    reference: Path | None = None,
    threads: int = 4,
    min_contig: int = 0,
    timeout: float = 900.0,
) -> dict[str, float]:
    """Run QUAST on the given contigs and return its parsed metrics."""

    with tempfile.TemporaryDirectory(prefix="quast_") as tmp:
        folder = Path(tmp)
        contigs = folder / "contigs.fna"
        write_fasta(sequences, contigs)
        out_dir = folder / "quast_out"
        launcher = _launcher(binary)
        command = [
            *launcher,
            str(contigs),
            "-o",
            str(out_dir),
            "-t",
            str(max(1, int(threads))),
            "--min-contig",
            str(max(0, int(min_contig))),
            "--no-plots",
        ]
        if reference is not None:
            command.extend(["-r", str(reference)])
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=tool_environment(binary),
            )
        except FileNotFoundError as error:
            raise StepError(f"assembly_stats: '{binary}' was not found") from error
        except subprocess.TimeoutExpired as error:
            raise StepError(
                f"assembly_stats: QUAST timed out after {timeout:.0f} s"
            ) from error
        report = out_dir / "report.tsv"
        if completed.returncode != 0 or not report.is_file():
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()
            raise StepError(
                "assembly_stats: QUAST failed with exit code "
                f"{completed.returncode}: {' | '.join(tail[-3:])}"
            )
        metrics = parse_report(report.read_text(encoding="utf-8", errors="replace"))
    if not metrics:
        raise StepError("assembly_stats: QUAST returned an empty report")
    return metrics


class AssemblyStatsStep(Step):
    provider = "operon-core"
    parameters_file = "assembly_stats.AssemblyStatsStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "assembly_stats",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Assembly quality metrics (QUAST)",
        "description": (
            "Run the official QUAST report on contigs and return assembly metrics, "
            "optionally against a reference genome."
        ),
        "category": "Genome",
        "icon": "ChartBar",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                    "info": {
                        "representation": {"type": "string", "const": "sequence_codes"}
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
                    "info": {"missing_code": {"type": ["number", "null"]}},
                },
            },
        },
        "resources": {
            "memory_modes": ["full"],
            "estimate": "estimate_memory",
            "external_tools": ["quast"],
        },
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        out_name = params.get("output", self.name)
        sequences = decode_sequences(
            inputs[0],
            str(params.get("sequence_dim", "sequence")),
            str(params.get("position_dim", "position")),
        )
        if not sequences:
            raise StepError("assembly_stats: the input carries no contig sequence")
        binary = str(params.get("quast_path") or "quast")
        resolved = shutil.which(binary) or (binary if Path(binary).is_file() else "")
        if not resolved:
            raise StepError(
                "assembly_stats: the QUAST executable was not found; set quast_path "
                "to its location"
            )
        reference_text = str(params.get("reference_path", "") or "")
        reference = Path(reference_text).expanduser() if reference_text else None
        if reference is not None and not reference.is_file():
            raise StepError(f"assembly_stats: reference_path {reference} is not a file")
        metrics = run_quast(
            resolved,
            sequences,
            reference=reference,
            threads=int(params.get("threads", 4)),
            min_contig=int(params.get("min_contig", 0)),
            timeout=float(params.get("timeout_seconds", 900)),
        )
        names = sorted(metrics)
        data = np.asarray([[metrics[name] for name in names]], dtype=np.float32).T
        summary = {
            "n50": metrics.get("N50"),
            "l50": metrics.get("L50"),
            "total_length": metrics.get("Total length (>= 0 bp)"),
            "n_contigs": metrics.get("# contigs (>= 0 bp)"),
            "largest": metrics.get("Largest contig"),
            "genome_fraction": metrics.get("Genome fraction (%)"),
        }
        ctx[out_name] = Form(
            data=data,
            dims=["metric", "statistic"],
            labels={
                "metric": {name: index for index, name in enumerate(names)},
                "statistic": {_METRIC: 0},
            },
            info={
                "missing_code": np.nan,
                "source": "quast",
                "reference_path": str(reference) if reference is not None else "",
                "n_metrics": len(names),
                **{key: value for key, value in summary.items() if value is not None},
                "metrics": metrics,
            },
        )
        self._export_data = {
            "output": out_name,
            "n_metrics": len(names),
            **{key: float(value) for key, value in summary.items() if value is not None},
        }

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
