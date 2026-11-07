"""antiSMASH biosynthetic gene cluster detection."""

from __future__ import annotations

import json
import re
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._resources_common import check_resource, load_resources, remedy
from src.task.step.steps._sequence_common import decode_sequences


def _tool_env(binary: Path) -> dict:
    """Make helper binaries from the tool's own environment visible."""
    env = dict(os.environ)
    env["PATH"] = str(Path(binary).resolve().parent) + os.pathsep + env.get("PATH", "")
    return env

_STATISTICS = ("start", "end", "length", "n_genes", "n_protoclusters")
_TAXA = ("bacteria", "fungi")
_LOCATION = re.compile(r"\[(\d+):(\d+)\]\(([+-])\)")


def write_fasta(sequences: list[str], path: Path) -> None:
    lines = []
    for index, sequence in enumerate(sequences):
        lines.append(f">contig{index + 1}")
        for start in range(0, len(sequence), 70):
            lines.append(sequence[start : start + 70])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _feature_span(location: str) -> tuple[int, int, int] | None:
    """First span of an antiSMASH/GenBank location string (1-based, inclusive)."""
    match = _LOCATION.search(str(location))
    if not match:
        return None
    start, end = int(match.group(1)), int(match.group(2))
    if start > end:
        start, end = end, start
    return start, end, (1 if match.group(3) == "+" else -1)


def parse_antismash_json(text: str) -> dict:
    """Parse the antiSMASH JSON result into region and gene records.

    antiSMASH JSON coordinates are stored with a zero-based start and an
    inclusive end; this function converts every span to one-based inclusive
    coordinates, matching the rest of the library and GenBank displays.
    """

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise StepError(f"antismash_bgc: the antiSMASH JSON is invalid: {error}") from error
    regions: list[dict] = []
    product_counts: dict[str, int] = {}
    for record in payload.get("records") or []:
        contig = str(record.get("id") or "")
        features = record.get("features") or []
        region_number = 0
        for area in record.get("areas") or []:
            if area.get("area_type") not in (None, "region"):
                continue
            if "products" not in area:
                continue
            region_number += 1
            start = int(area.get("start") or 0) + 1
            end = int(area.get("end") or 0)
            products = [str(item) for item in area.get("products") or []]
            raw_clusters = area.get("protoclusters") or []
            if isinstance(raw_clusters, dict):
                clusters = [value for value in raw_clusters.values() if isinstance(value, dict)]
            else:
                clusters = [value for value in raw_clusters if isinstance(value, dict)]
            genes: list[dict] = []
            seen_genes: set[tuple] = set()
            for feature in features:
                if str(feature.get("type") or "") not in {"gene", "CDS"}:
                    continue
                span = _feature_span(str(feature.get("location") or ""))
                if span is None:
                    continue
                gene_start = span[0] + 1
                gene_end = span[1]
                if gene_start < start or gene_end > end:
                    continue
                qualifiers = feature.get("qualifiers") or {}
                locus_tag = str((qualifiers.get("locus_tag") or [""])[0])
                key = (
                    ("tag", locus_tag)
                    if locus_tag
                    else ("span", gene_start, gene_end, span[2])
                )
                if key in seen_genes:
                    continue
                seen_genes.add(key)
                genes.append({
                    "locus_tag": str((qualifiers.get("locus_tag") or [""])[0]),
                    "gene": str((qualifiers.get("gene") or [""])[0]),
                    "product": str((qualifiers.get("product") or [""])[0]),
                    "start": gene_start,
                    "end": gene_end,
                    "strand": span[2],
                })
            regions.append({
                "contig": contig,
                "region_number": region_number,
                "start": start,
                "end": end,
                "products": products,
                "protocluster_products": [str(item.get("product") or "") for item in clusters],
                "n_genes": len(genes),
                "n_protoclusters": len(clusters),
                "genes": genes,
            })
            for product in products:
                product_counts[product] = product_counts.get(product, 0) + 1
    return {"regions": regions, "product_counts": product_counts,
            "n_records": len(payload.get("records") or [])}


def run_antismash(binary: Path, sequences: list[str], *, database_dir: str,
                  taxon: str = "bacteria", timeout: float = 3600.0) -> dict:
    if taxon not in _TAXA:
        raise StepError(f"antismash_bgc: taxon must be one of {', '.join(_TAXA)}")
    with tempfile.TemporaryDirectory(prefix="antismash_") as tmp:
        folder = Path(tmp)
        fasta = folder / "input.fa"
        write_fasta(sequences, fasta)
        output = folder / "out"
        launcher = [sys.executable, str(binary)] if str(binary).lower().endswith(".py") else [str(binary)]
        command = [
            *launcher,
            "--output-dir", str(output),
            "--genefinding-tool", "prodigal",
            "--taxon", taxon,
            "--cpus", "1",
        ]
        if database_dir:
            command.extend(["--databases", str(Path(database_dir).expanduser())])
        command.append(str(fasta))
        try:
            completed = subprocess.run(command, check=False, capture_output=True,
                                       text=True, timeout=timeout, env=_tool_env(binary))
        except FileNotFoundError as error:
            raise StepError(f"antismash_bgc: '{binary}' was not found on PATH") from error
        except subprocess.TimeoutExpired as error:
            raise StepError(f"antismash_bgc: antiSMASH timed out after {timeout:.0f} s") from error
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()
            raise StepError("antismash_bgc: antiSMASH failed with exit code "
                            f"{completed.returncode}: {' | '.join(tail[-4:])}")
        candidates = sorted(output.glob("*.json"))
        if not candidates:
            raise StepError("antismash_bgc: antiSMASH produced no JSON result")
        return parse_antismash_json(candidates[0].read_text(encoding="utf-8", errors="replace"))


def _jsonable(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _export_summary(form) -> dict:
    return {
        "dims": list(form.dims),
        "labels": _jsonable(form.labels),
        "info": _jsonable({key: value for key, value in form.info.items() if key != "missing_code"}),
    }


class AntismashBgcStep(Step):
    provider = "operon-core"
    parameters_file = "antismash_bgc.AntismashBgcStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "antismash_bgc",
        "version": "1.0.0",
        "kind": "operator",
        "title": "antiSMASH biosynthetic gene clusters",
        "category": "Genome",
        "icon": "Flask",
        "contracts": {
            "version": 1,
            "inputs": [{
                "version": 1,
                "numeric": True,
                "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}],
                "labels": [],
                "parallel": [],
                "ndim": 2,
                "info": {"representation": {"type": "string", "const": "sequence_codes"}},
            }],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True,
                           "axis_info_open": True,
                           "info": {"missing_code": {"type": ["number", "null"]}}},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory",
                      "external_tools": ["antismash"]},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "description": (
            "Detect biosynthetic gene clusters with the official antiSMASH binary; "
            "returns region spans, products, gene counts and per-region gene tables."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        out_name = params.get("output", self.name)
        sequences = decode_sequences(inputs[0], str(params.get("sequence_dim", "sequence")),
                                     str(params.get("position_dim", "position")))
        if not sequences:
            raise StepError("antismash_bgc: the input carries no sequence")
        database_text = str(params.get("database_dir", "") or "").strip()
        if database_text:
            database = Path(database_text).expanduser()
            if not database.is_dir():
                raise StepError(f"antismash_bgc: database_dir '{database}' is not a directory")
            database_dir = str(database)
        else:
            resource = load_resources()["antismash"]
            check = check_resource(resource)
            if check["status"] != "ok":
                raise StepError(f"antismash_bgc: {remedy(check)}")
            database_dir = check["root"]
        binary = Path(str(params.get("antismash_path", "") or "antismash")).expanduser()
        payload = run_antismash(binary, sequences, database_dir=database_dir,
                                taxon=str(params.get("taxon", "bacteria") or "bacteria"),
                                timeout=float(params.get("timeout_seconds", 3600.0)))
        regions = payload["regions"]
        rows = [(region["start"], region["end"], region["end"] - region["start"] + 1,
                 region["n_genes"], region["n_protoclusters"]) for region in regions]
        data = np.asarray(rows, dtype=np.float32).reshape(len(rows), len(_STATISTICS))
        labels = {f"{region['contig']}:region{region['region_number']}": index
                  for index, region in enumerate(regions)}
        result = Form(
            data=data,
            dims=["region", "statistic"],
            labels={"region": labels,
                    "statistic": {name: index for index, name in enumerate(_STATISTICS)}},
            info={"missing_code": np.nan, "regions": regions,
                  "n_regions": len(regions), "product_counts": payload["product_counts"],
                  "n_records": payload["n_records"], "database": database_dir},
        )
        self._export_data = _export_summary(result)
        ctx[out_name] = result

    def export(self, ctx: Context):
        return getattr(self, "_export_data", {})
