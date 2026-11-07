"""Foldseek structural search wrapper."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_FORMAT = "query,target,evalue,bits,prob,alntmscore,qtmscore,ttmscore"


def foldseek_command(binary: str, query: Path, database: Path, output: Path, tmp: Path, *, threads: int = 1) -> list[str]:
    return [binary, "easy-search", str(query), str(database), str(output), str(tmp), "--format-output", _FORMAT, "--threads", str(threads)]


def parse_m8(text: str) -> list[dict]:
    hits = []
    for line in text.splitlines():
        fields = line.rstrip().split("\t")
        if len(fields) < 8:
            continue
        try:
            hits.append({"query": fields[0], "target": fields[1], "evalue": float(fields[2]), "bits": float(fields[3]), "prob": float(fields[4]), "alntmscore": float(fields[5]), "qtmscore": float(fields[6]), "ttmscore": float(fields[7])})
        except ValueError:
            continue
    hits.sort(key=lambda hit: (-hit["alntmscore"], hit["evalue"]))
    return hits


class FoldseekSearchStep(Step):
    provider = "operon-core"
    parameters_file = "foldseek_search.FoldseekSearchStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "foldseek_search",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Foldseek structural search",
        "category": "Structure",
        "icon": "Database",
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
        query = Path(str(params.get("query_path", ""))).expanduser()
        if not query.is_file():
            raise StepError(f"foldseek_search: query_path {query} is not a file")
        database = Path(str(params.get("database_path", ""))).expanduser()
        if not database.exists():
            raise StepError(f"foldseek_search: database_path {database} does not exist; download a Foldseek database first")
        candidate = str(params.get("foldseek_path") or "foldseek")
        binary = shutil.which(candidate)
        if binary is None and Path(candidate).is_file():
            binary = candidate
        if binary is None:
            raise StepError("foldseek_search: 'foldseek' was not found on PATH; download the static binary from the Foldseek release page")
        workdir = Path(tempfile.mkdtemp(prefix="foldseek_"))
        output = workdir / "hits.m8"
        command = foldseek_command(binary, query, database, output, workdir / "tmp", threads=int(params.get("threads", 1)))
        if str(binary).lower().endswith(".py"):
            command = [sys.executable] + command
        completed = subprocess.run(command, capture_output=True, text=True, timeout=int(params.get("timeout_seconds", 1800)))
        if completed.returncode != 0:
            tail = ((completed.stderr or completed.stdout).strip().splitlines() or [""])[-1]
            raise StepError(f"foldseek_search: Foldseek failed with exit code {completed.returncode}: {tail}")
        hits = parse_m8(output.read_text() if output.is_file() else "")[: int(params.get("max_hits", 100))]
        if not hits:
            raise StepError("foldseek_search: no structural hit was reported")
        data = np.asarray([[hit["evalue"], hit["bits"], hit["prob"], hit["alntmscore"], hit["qtmscore"], hit["ttmscore"]] for hit in hits], dtype=np.float32)
        ctx[params.get("output", "hits")] = Form(
            data=data,
            dims=["hit", "statistic"],
            labels={"hit": {f"{hit['target']}#{index + 1}": index for index, hit in enumerate(hits)}, "statistic": {"evalue": 0, "bits": 1, "prob": 2, "alntmscore": 3, "qtmscore": 4, "ttmscore": 5}},
            info={"missing_code": np.nan, "n_hits": len(hits), "query": str(query), "database": str(database), "targets": [hit["target"] for hit in hits]},
        )
        self._export_data = {"n_hits": len(hits), "top_target": hits[0]["target"]}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
