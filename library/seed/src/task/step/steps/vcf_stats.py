"""Allele-level summary statistics for a VCF/VCF.gz file.

Input: FileArtifact (format vcf or vcf.gz) produced by a file source.
Output: 2D Form [statistic, value] with one row per summary metric.

The scan is streaming and never materialises genotypes, so a 2504-sample
1000G slice costs the same as a sites-only VCF.  Only the eight mandatory
columns are split per record.  SNP, indel and other counts are per
ALT allele, matching ``bcftools stats``.
"""
from __future__ import annotations

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps import _vcf_utils as vcf


_LABELS = (
    "n_variants",
    "n_snps",
    "n_indels",
    "n_other",
    "n_multiallelic",
    "n_pass",
    "n_transitions",
    "n_transversions",
    "ts_tv_ratio",
    "mean_qual",
    "n_samples",
    "n_chromosomes",
    "n_no_alt",
)

_TRANSITIONS = {("A", "G"), ("G", "A"), ("C", "T"), ("T", "C")}


class VcfStatsStep(Step):
    """Count variants, SNPs, indels, transitions and samples in a VCF."""
    provider = 'operon-core'
    parameters_file = 'vcf_stats.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'vcf_stats',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'vcf_stats',
     'description': 'Allele-level summary statistics for a VCF/VCF.gz file.',
     'category': 'Genome',
     'icon': 'ChartBar',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'kind': 'file',
                               'numeric': False,
                               'ndim': 0,
                               'dims': [],
                               'info': {'representation': {'type': 'string',
                                                           'enum': ['vcf', 'vcf.gz']}}}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
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
        return max(int(size * 1.5), 4 * 1024**2), 64 * 1024

    def run(self, ctx: Context, inputs) -> None:
        if not inputs or not isinstance(inputs[0], FileArtifact):
            raise StepError("vcf_stats requires a VCF file artifact")
        artifact = inputs[0]
        artifact.validate()
        if artifact.format not in ("vcf", "vcf.gz"):
            raise StepError(f"vcf_stats requires a VCF file, got {artifact.format!r}")

        params = dict(ctx.step_params)
        region = str(params.get("region") or "")
        max_records = int(params.get("max_records") or 0)
        out_name = params.get("output") or self.name
        path = next(iter(artifact.files.values()))

        counts = {label: 0 for label in _LABELS}
        chromosomes = set()
        qual_sum = 0.0
        qual_n = 0
        n_samples = 0

        with vcf.open_text(path) as stream:
            _meta, _columns, samples = vcf.read_header(stream)
            n_samples = len(samples)
            for fixed, _rest in vcf.iter_sites(stream):
                chrom, pos, _id, ref, alt_text, qual, filt, info_text = fixed[:8]
                if not vcf.region_match(chrom, pos, region):
                    continue
                counts["n_variants"] += 1
                chromosomes.add(vcf.chrom_key(chrom))
                alts = vcf.alt_alleles(alt_text)
                if not alts:
                    counts["n_no_alt"] += 1
                if len(alts) > 1:
                    counts["n_multiallelic"] += 1
                if filt == "PASS":
                    counts["n_pass"] += 1
                qual_value = vcf.parse_qual(qual)
                if qual_value is not None:
                    qual_sum += qual_value
                    qual_n += 1
                for allele in alts:
                    ref_base = ref.upper()
                    alt_base = allele.upper()
                    symbolic = (
                        alt_base.startswith("<")
                        or "[" in alt_base
                        or "]" in alt_base
                    )
                    if symbolic:
                        counts["n_other"] += 1
                    elif len(ref_base) == len(alt_base):
                        # Same-length alleles are SNPs in bcftools terms; a
                        # single-base A/C/G/T pair also feeds ts/tv.
                        counts["n_snps"] += 1
                        pair = (ref_base, alt_base)
                        if (
                            len(ref_base) == 1
                            and ref_base in "ACGT"
                            and alt_base in "ACGT"
                        ):
                            if pair in _TRANSITIONS:
                                counts["n_transitions"] += 1
                            else:
                                counts["n_transversions"] += 1
                    else:
                        counts["n_indels"] += 1
                if max_records and counts["n_variants"] >= max_records:
                    break

        ts = counts["n_transitions"]
        tv = counts["n_transversions"]
        counts["ts_tv_ratio"] = (ts / tv) if tv else 0.0
        counts["mean_qual"] = (qual_sum / qual_n) if qual_n else 0.0
        counts["n_samples"] = n_samples
        counts["n_chromosomes"] = len(chromosomes)

        data = np.array([[float(counts[label])] for label in _LABELS], dtype=np.float32)
        form = Form(
            data=data,
            dims=["statistic", "value"],
            labels={
                "statistic": {label: index for index, label in enumerate(_LABELS)},
                "value": {"value": 0},
            },
            info={
                "missing_code": np.nan,
                "representation": "vcf_stats",
                "region": region or "all",
                "truncated": bool(max_records and counts["n_variants"] >= max_records),
            },
        )
        ctx[out_name] = form
        self._report = {
            "n_variants": int(counts["n_variants"]),
            "n_snps": int(counts["n_snps"]),
            "n_indels": int(counts["n_indels"]),
            "n_other": int(counts["n_other"]),
            "n_multiallelic": int(counts["n_multiallelic"]),
            "n_pass": int(counts["n_pass"]),
            "ts_tv_ratio": round(float(counts["ts_tv_ratio"]), 6),
            "mean_qual": round(float(counts["mean_qual"]), 4),
            "n_samples": int(n_samples),
            "n_chromosomes": len(chromosomes),
        }
        print(
            f"[vcf_stats] {int(counts['n_variants'])} variants, "
            f"{int(counts['n_snps'])} SNPs, ts/tv={counts['ts_tv_ratio']:.3f}, "
            f"{n_samples} samples"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_report", {})
