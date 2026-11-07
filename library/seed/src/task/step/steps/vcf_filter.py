"""Filter a VCF/VCF.gz and write the retained records as a native VCF file.

The output is a byte-preserving subset: header meta lines and each retained
record are copied verbatim, so INFO/FORMAT fields, phasing and sample order
are unchanged.  The filtered file is registered as a native result and also
exposed as a FileArtifact so downstream operators can consume it directly.

Filters are site-level by default; sample-level missingness is only evaluated
when ``max_missing_rate < 1``.
"""
from __future__ import annotations

from pathlib import Path

from src.core import FileArtifact, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps import _vcf_utils as vcf
from src.task.step.steps._native_results import output_directory, remember_native, result_file


class VcfFilterStep(Step):
    """Quality/type/region filtering with a native filtered VCF output."""
    provider = 'operon-core'
    parameters_file = 'vcf_filter.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'file_artifact',
                      'representations': ['file_artifact'],
                      'metadata': {}}]},
        'protocol_version': 3,
     'id': 'vcf_filter',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'vcf_filter',
     'description': 'Filter VCF records by quality, FILTER, variant type, depth, missingness and region.',
     'category': 'Genome',
     'icon': 'Filter',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'kind': 'file',
                               'numeric': False,
                               'ndim': 0,
                               'dims': [],
                               'info': {'representation': {'type': 'string',
                                                           'enum': ['vcf', 'vcf.gz']}}}],
                   'output': {'mode': 'declare',
                              'schema': {'kind': 'file',
                                         'numeric': False,
                                         'ndim': 0,
                                         'dims': [],
                                         'info': {'representation': {'type': 'string',
                                                                     'const': 'vcf'}},
                                         'info_open': True}}},
     'resources': {'memory_modes': ['full'],
                   'supports_cuda': False,
                   'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output'}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = 0
        for artifact in inputs or []:
            size += int(getattr(artifact, "file_bytes", 0) or 0)
        return max(int(size * 2.5), 4 * 1024**2), max(int(size * 1.1), 1024**2)

    def run(self, ctx: Context, inputs) -> None:
        if not inputs or not isinstance(inputs[0], FileArtifact):
            raise StepError("vcf_filter requires a VCF file artifact")
        artifact = inputs[0]
        artifact.validate()
        if artifact.format not in ("vcf", "vcf.gz"):
            raise StepError(f"vcf_filter requires a VCF file, got {artifact.format!r}")

        params = dict(ctx.step_params)
        out_name = params.get("output") or self.name
        min_qual = float(params.get("min_qual") or 0.0)
        require_pass = bool(params.get("require_pass", False))
        biallelic_only = bool(params.get("biallelic_only", False))
        variant_type = str(params.get("variant_type") or "any")
        min_dp = int(params.get("min_dp") or 0)
        max_missing = float(params.get("max_missing_rate", 1.0))
        region = str(params.get("region") or "")
        max_records = int(params.get("max_records") or 0)

        if variant_type not in ("any", "snps", "indels"):
            raise StepError("vcf_filter: variant_type must be any, snps or indels")
        if not 0.0 <= max_missing <= 1.0:
            raise StepError("vcf_filter: max_missing_rate must be within [0, 1]")

        directory = output_directory(ctx, out_name)
        destination = Path(directory) / f"{out_name}.vcf"

        n_in = n_out = 0
        removed = {"region": 0, "qual": 0, "filter": 0, "type": 0, "depth": 0, "missing": 0}
        source_path = next(iter(artifact.files.values()))

        with vcf.open_text(source_path) as stream, destination.open("w", encoding="utf-8", newline="\n") as out:
            samples = []
            format_index = None
            for line in stream:
                if line.startswith("##"):
                    out.write(line)
                    continue
                if line.startswith("#CHROM"):
                    out.write(line)
                    columns = line.rstrip("\n").split("\t")
                    samples = columns[9:]
                    continue
                n_in += 1
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 8:
                    raise StepError("vcf_filter: VCF record has fewer than 8 columns")
                chrom, pos, _id, ref, alt_text, qual_text, filt, info_text = parts[:8]
                rest = parts[8] if len(parts) > 8 else ""

                if not vcf.region_match(chrom, pos, region):
                    removed["region"] += 1
                    continue
                qual = vcf.parse_qual(qual_text)
                if min_qual > 0 and (qual is None or qual < min_qual):
                    removed["qual"] += 1
                    continue
                if require_pass and filt != "PASS":
                    removed["filter"] += 1
                    continue
                alts = vcf.alt_alleles(alt_text)
                if biallelic_only and len(alts) != 1:
                    removed["type"] += 1
                    continue
                if variant_type != "any":
                    if not alts:
                        removed["type"] += 1
                        continue
                    is_snp = len(ref) == 1 and len(alts[0]) == 1
                    if variant_type == "snps" and not is_snp:
                        removed["type"] += 1
                        continue
                    if variant_type == "indels" and is_snp:
                        removed["type"] += 1
                        continue
                if min_dp > 0:
                    info = vcf.parse_info(info_text)
                    try:
                        depth = int(float(info.get("DP", 0)))
                    except (TypeError, ValueError):
                        depth = 0
                    if depth < min_dp:
                        removed["depth"] += 1
                        continue
                if max_missing < 1.0 and samples:
                    if format_index is None:
                        format_index = 0
                    fields = rest.split("\t")
                    fmt = fields[0].split(":") if fields else []
                    gt_index = fmt.index("GT") if "GT" in fmt else None
                    if gt_index is None:
                        removed["missing"] += 1
                        continue
                    missing = 0
                    total = 0
                    for field in fields[1:]:
                        values = field.split(":")
                        total += 1
                        if gt_index >= len(values) or values[gt_index] in (".", "./.", ".|."):
                            missing += 1
                    if total and missing / total > max_missing:
                        removed["missing"] += 1
                        continue

                out.write(line)
                n_out += 1
                if max_records and n_out >= max_records:
                    break

        if n_out == 0:
            destination.unlink(missing_ok=True)
            raise StepError("vcf_filter: no records passed the filters")

        files = [result_file("variants", destination, "vcf", "Filtered VCF")]
        remember_native(ctx, str(out_name), files)
        ctx[out_name] = FileArtifact(
            "vcf",
            {"variants": str(destination)},
            {"representation": "vcf", "filtered_from": artifact.format},
        )
        self._result_files = files
        self._report = {
            "n_input": n_in,
            "n_output": n_out,
            "n_removed": n_in - n_out,
            "removed": removed,
            "file": destination.name,
            "bytes": destination.stat().st_size,
        }
        print(f"[vcf_filter] kept {n_out}/{n_in} records -> {destination.name}")

    def export(self, ctx: Context) -> dict:
        report = dict(getattr(self, "_report", {}))
        report["result_files"] = list(getattr(self, "_result_files", []))
        return report
