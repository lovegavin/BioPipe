"""foldseek_align: pairwise structural alignment with Foldseek."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step

_FORMAT = "query,target,alntmscore,rmsd,lddt,fident,qcov,tcov,alnlen"
_COLUMNS = ("alntmscore", "rmsd", "lddt", "fident", "qcov", "tcov", "alnlen")


def foldseek_command(binary: str, query: Path, target: Path, result: Path, workdir: Path) -> list[str]:
    """Build the easy-search invocation (structurealign needs four databases)."""

    launcher = [sys.executable, binary] if binary.lower().endswith(".py") else [binary]
    return [
        *launcher,
        "easy-search",
        str(query),
        str(target),
        str(result),
        str(workdir),
        "--format-output",
        _FORMAT,
    ]


def run_alignment(binary: str, query: Path, target: Path, *, timeout: int = 300) -> str:
    """Run Foldseek easy-search and return the raw TSV text."""

    workdir = Path(tempfile.mkdtemp(prefix="foldseek_align_"))
    result = workdir / "result.m8"
    command = foldseek_command(binary, query, target, result, workdir / "tmp")
    (workdir / "tmp").mkdir()
    env = dict(os.environ)
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired as exc:
        raise StepError(f"foldseek_align: Foldseek timed out after {timeout} s") from exc
    except FileNotFoundError as exc:
        raise StepError("foldseek_align: the Foldseek executable was not found; set foldseek_path to its location") from exc
    if completed.returncode != 0:
        tail = " ".join((completed.stderr or completed.stdout or "").strip().splitlines()[-2:])
        raise StepError(f"foldseek_align: Foldseek failed with exit code {completed.returncode}: {tail[:300]}")
    if not result.is_file():
        raise StepError("foldseek_align: Foldseek returned no alignment")
    return result.read_text().strip()


def parse_row(text: str, query_name: str, target_name: str) -> dict:
    """Parse one structurealign row; tolerate Foldseek writing several lines."""

    rows = [line for line in str(text).splitlines() if line.strip()]
    if not rows:
        raise StepError("foldseek_align: Foldseek returned no alignment")
    fields = rows[0].split("\t")
    if len(fields) < 2 + len(_COLUMNS):
        raise StepError(f"foldseek_align: unexpected Foldseek output '{rows[0][:120]}'")
    values = dict(zip(_COLUMNS, (float(field) for field in fields[2: 2 + len(_COLUMNS)])))
    return {
        "query": str(fields[0] or query_name),
        "target": str(fields[1] or target_name),
        "query_name": query_name,
        "target_name": target_name,
        **values,
    }


class FoldseekAlignStep(Step):
    provider = "operon-core"
    parameters_file = "foldseek_align.FoldseekAlignStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "foldseek_align",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Foldseek structural alignment",
        "description": "Align two structures with Foldseek structurealign and report TM-score, RMSD, lDDT, identity and coverage.",
        "category": "Structure",
        "icon": "ShareNetwork",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory",
                       "external_tools": ["foldseek"]},
        "dependencies": [],
        "dependency_imports": [],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        query = Path(str(params.get("query_path", ""))).expanduser()
        target = Path(str(params.get("target_path", ""))).expanduser()
        if not str(params.get("query_path", "")):
            raise StepError("foldseek_align: query_path is required")
        if not str(params.get("target_path", "")):
            raise StepError("foldseek_align: target_path is required")
        if not query.is_file():
            raise StepError(f"foldseek_align: query_path {query} is not a file")
        if not target.is_file():
            raise StepError(f"foldseek_align: target_path {target} is not a file")
        binary = str(params.get("foldseek_path") or "foldseek")
        resolved = shutil.which(binary) or (binary if Path(binary).is_file() else "")
        if not resolved:
            raise StepError("foldseek_align: the Foldseek executable was not found; set foldseek_path to its location")
        text = run_alignment(resolved, query, target, timeout=int(params.get("timeout_seconds", 300)))
        record = parse_row(text, query.stem, target.stem)
        data = np.array([[record[column] for column in _COLUMNS]], dtype=np.float32)
        out = params.get("output", "alignment")
        ctx[out] = Form(
            data=data,
            dims=["pair", "statistic"],
            labels={"pair": {f"{query.name}~{target.name}": 0}, "statistic": {column: index for index, column in enumerate(_COLUMNS)}},
            info={
                "missing_code": np.nan,
                "query_path": str(query),
                "target_path": str(target),
                "query": record["query"],
                "target": record["target"],
                "format": _FORMAT,
                **{column: float(record[column]) for column in _COLUMNS},
            },
        )
        self._export_data = {"output": out, "alntmscore": float(record["alntmscore"]), "rmsd": float(record["rmsd"])}
        return ctx[out]

    def export(self, ctx):
        return getattr(self, "_export_data", {})
