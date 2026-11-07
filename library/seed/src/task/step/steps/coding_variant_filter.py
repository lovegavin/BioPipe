"""Filter an annotated VCF down to coding and splice-site consequences."""
from __future__ import annotations

from pathlib import Path

from src.core import FileArtifact, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps import _vcf_utils as vcf
from src.task.step.steps._native_results import output_directory, remember_native, result_file
from src.task.step.steps._variant_utils import CODING_CLASSES, SPLICE_CLASSES

_DEFAULT_KEEP = CODING_CLASSES | SPLICE_CLASSES


def _file_path(artifact, operator):
    if not isinstance(artifact, FileArtifact):
        raise StepError(f"{operator} expects a file artifact")
    artifact.validate()
    if str(getattr(artifact, "format", "")) not in {"vcf", "vcf.gz"}:
        raise StepError(f"{operator} expects a VCF artifact")
    return next(iter(artifact.files.values()))


def _info_value(info, key):
    for item in info.split(";"):
        if item.startswith(key + "="):
            return item[len(key) + 1:]
    return ""


class CodingVariantFilterStep(Step):
    provider = "operon-core"
    parameters_file = "coding_variant_filter.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'file_artifact',
                      'representations': ['file_artifact'],
                      'metadata': {}}]},
        "protocol_version": 3,
        "id": "coding_variant_filter",
        "version": "1.0.0",
        "kind": "operator",
        "title": "coding_variant_filter",
        "description": "Keep annotated VCF records with coding or splice-site consequences.",
        "category": "Genome",
        "icon": "Filter",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "kind": "file", "numeric": False, "ndim": 0, "dims": [],
                 "info": {"representation": {"type": "string", "enum": ["vcf", "vcf.gz"]}}},
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "version": 1,
                    "kind": "file",
                    "numeric": False,
                    "ndim": 0,
                    "dims": [],
                    "info": {"representation": {"type": "string", "const": "vcf"}},
                    "info_open": True,
                },
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return 256 * 1024 * 1024, 8 * 1024 * 1024

    def run(self, ctx: Context, inputs) -> None:
        (annotation,) = inputs
        params = ctx.step_params
        out_name = params.get("output", "filtered") or "filtered"
        keep = {part.strip() for part in str(params.get("keep", "")).split(",") if part.strip()}
        if not keep:
            keep = set(_DEFAULT_KEEP)
        path = _file_path(annotation, "coding_variant_filter")
        directory = Path(output_directory(ctx, out_name))
        destination = directory / f"{out_name}.vcf"

        kept = 0
        removed = 0
        with vcf.open_text(path) as stream:
            meta, samples, _columns = vcf.read_header(stream)
            with open(destination, "w", encoding="utf-8", newline="\n") as out:
                for line in meta:
                    out.write(line + "\n")
                columns = ["#CHROM", "POS", "ID", "REF", "ALT", "QUAL", "FILTER", "INFO"]
                if samples:
                    columns.append("FORMAT")
                    columns.extend(samples)
                out.write("\t".join(columns) + "\n")
                for fixed, rest in vcf.iter_sites(stream):
                    consequence = _info_value(fixed[7], "CSQ") or "intergenic"
                    if consequence not in keep:
                        removed += 1
                        continue
                    row = list(fixed)
                    if rest:
                        row.extend(rest.split("\t"))
                    out.write("\t".join(row) + "\n")
                    kept += 1

        size = int(destination.stat().st_size)
        result_files = [result_file("filtered", str(destination), "vcf", "Coding VCF")]
        remember_native(ctx, out_name, result_files)
        ctx[out_name] = FileArtifact(
            "vcf",
            {"filtered": str(destination)},
            info={"representation": "vcf", "source": "coding_variant_filter"},
        )
        self._result_files = result_files
        self._export_data = {
            "kept": kept,
            "removed": removed,
            "kept_fraction": float(kept / (kept + removed)) if (kept + removed) else 0.0,
            "keep_classes": sorted(keep),
            "file": str(destination),
            "bytes": size,
            "result_files": result_files,
        }
        print(f"[coding_variant_filter] kept {kept}, removed {removed}")

    def export(self, ctx: Context) -> dict:
        return dict(getattr(self, "_export_data", {}))
