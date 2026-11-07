"""Lift VCF records between assemblies using a UCSC chain file."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import StepError
from src.core.files import FileArtifact

from src.task.step.base import Step
from src.task.step.steps._native_results import output_directory, remember_native, result_file
from ._liftover_utils import ChainIndex, chain_path, load_chain, reverse_complement
from ._vcf_utils import iter_sites, open_text, read_header

_DEFAULTS = {"chrom_field": "CHROM", "output": "liftover_variants"}


def vcf_path(artifact, operator):
    files = getattr(artifact, "files", None)
    if not isinstance(files, dict) or not files:
        raise StepError(f"{operator}: VCF input must be a FileArtifact")
    path = Path(next(iter(files.values())))
    if not path.is_file():
        raise StepError(f"{operator}: VCF file not found: {path}")
    return path


class LiftoverVariantsStep(Step):
    provider = "operon-core"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}},
                    {'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'file_artifact',
                      'representations': ['file_artifact'],
                      'metadata': {}}]},
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "liftover_variants",
        "kind": "operator",
        "title": "liftOver variants",
        "description": "Map VCF records to another assembly with a UCSC chain file.",
        "category": "Genome",
        "icon": "GitCompare",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "kind": "file",
                    "numeric": False,
                    "ndim": 0,
                    "dims": [],
                    "info": {"representation": {"type": "string", "enum": ["vcf"]}},
                },
                {
                    "version": 1,
                    "kind": "file",
                    "numeric": False,
                    "ndim": 0,
                    "dims": [],
                    "info": {"representation": {"type": "string", "const": "chain"}},
                },
            ],
            "output": {"mode": "declare", "schema": {"kind": "file", "numeric": False, "ndim": 0, "dims": [], "info": {"representation": {"type": "string", "const": "vcf"}}, "info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (16 * 1024 * 1024, 1024 * 1024)

    def run(self, ctx, inputs):
        params = dict(_DEFAULTS)
        params.update(ctx.step_params or {})
        operator = self.name or "liftover_variants"
        out_name = str(params.get("output") or self.name or "liftover_variants")

        source = vcf_path(inputs[0], operator)
        index = ChainIndex(load_chain(chain_path(inputs[1], operator)))

        with open_text(source) as stream:
            meta, _format_columns, samples = read_header(stream)
            records = list(iter_sites(stream))
        if not records:
            raise StepError(f"{operator}: VCF has no records")

        header = list(meta)
        if not any(line.startswith("##liftover") for line in header):
            header.append("##liftover=UCSC chain")
        columns = ["#CHROM", "POS", "ID", "REF", "ALT", "QUAL", "FILTER", "INFO"]
        if samples:
            columns.append("FORMAT")
            columns.extend(samples)
        header.append("\t".join(columns))

        mapped_lines = []
        unmapped_lines = []
        n_reverse = 0
        for fixed, rest in records:
            chrom, pos_text, record_id, ref, alt, qual, filters, info = fixed
            try:
                position = int(pos_text)
            except ValueError as exc:
                raise StepError(f"{operator}: invalid POS '{pos_text}'") from exc
            if position < 1:
                raise StepError(f"{operator}: POS must be >= 1")
            if not ref or ref == ".":
                raise StepError(f"{operator}: REF must not be empty")
            start = position - 1
            end = start + len(ref)
            try:
                result = index.map_interval(chrom, start, end)
            except ValueError as exc:
                raise StepError(f"{operator}: {exc}") from exc
            original = fixed + ([rest] if rest else [])
            if result is None:
                unmapped_lines.append("\t".join(original))
                continue
            target, target_start, target_end, strand = result
            new_ref = ref
            new_alt = alt
            if strand == "-":
                new_ref = reverse_complement(ref)
                alleles = []
                for allele in alt.split(","):
                    if allele in {"*", ".", ""}:
                        alleles.append(allele)
                    else:
                        alleles.append(reverse_complement(allele))
                new_alt = ",".join(alleles)
                n_reverse += 1
            record = [
                target,
                str(int(target_start) + 1),
                record_id,
                new_ref,
                new_alt,
                qual,
                filters,
                info,
            ]
            if rest:
                record.append(rest)
            mapped_lines.append("\t".join(record))

        directory = output_directory(ctx, out_name)
        mapped_path = directory / f"{out_name}.mapped.vcf"
        unmapped_path = directory / f"{out_name}.unmapped.vcf"
        mapped_path.write_bytes(
            ("\n".join(header + mapped_lines) + "\n").encode("utf-8")
        )
        unmapped_path.write_bytes(
            ("\n".join(header + unmapped_lines) + "\n").encode("utf-8")
        )
        result_files = [
            result_file("mapped", str(mapped_path), "vcf", "Variants lifted to the target assembly"),
            result_file("unmapped", str(unmapped_path), "vcf", "Variants without a target location"),
        ]
        remember_native(ctx, out_name, result_files)
        ctx[out_name] = FileArtifact(
            "vcf",
            {"mapped": str(mapped_path), "unmapped": str(unmapped_path)},
            info={
                "source": "liftover_variants",
                "n_records": len(records),
                "n_mapped": len(mapped_lines),
                "n_unmapped": len(unmapped_lines),
            },
        )

        self._export_data = {
            "n_records": len(records),
            "n_mapped": len(mapped_lines),
            "n_unmapped": len(unmapped_lines),
            "n_reverse_complemented": n_reverse,
            "map_rate": (len(mapped_lines) / len(records)) if records else 0.0,
            "mapped_file": str(mapped_path),
            "mapped_bytes": int(mapped_path.stat().st_size),
            "unmapped_file": str(unmapped_path),
            "unmapped_bytes": int(unmapped_path.stat().st_size),
            "result_files": result_files,
        }
        print(
            f"[liftover_variants] {len(records)} records, {len(mapped_lines)} mapped, "
            f"{len(unmapped_lines)} unmapped, {n_reverse} reverse-complemented"
        )

    def export(self, ctx):
        return self._export_data
