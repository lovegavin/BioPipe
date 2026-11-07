"""Genotype concordance between a query VCF and a truth VCF.

Both inputs must be VCF/VCF.gz file artifacts.  One sample is compared per
file (defaults to the first sample).  Records are compared per ALT allele:
sites are keyed by (contig, position, ALT index, ALT base), so multi-allelic
records are handled without normalising the files first.  REF/ALT identity is
checked before genotypes are compared, so an allele mismatch is never silently
counted as a genotype discordance.

Output: 2D Form [metric, value].
"""
from __future__ import annotations

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps import _vcf_utils as vcf


_METRICS = (
    "n_query_sites",
    "n_truth_sites",
    "n_matched_sites",
    "n_query_only",
    "n_query_duplicates",
    "n_truth_only",
    "n_allele_mismatch",
    "n_genotypes_compared",
    "n_genotypes_discordant",
    "genotype_concordance",
    "allele_concordance",
)


def _gt_value(rest, index):
    fields = rest.split("\t") if rest else []
    if not fields:
        return None
    fmt = fields[0].split(":")
    if "GT" not in fmt:
        return None
    gt_index = fmt.index("GT")
    values = fields[1 + index].split(":") if len(fields) > 1 + index else []
    return values[gt_index] if gt_index < len(values) else None


def _load_truth(artifact, sample, region, min_qual, require_pass):
    path = next(iter(artifact.files.values()))
    table = {}
    positions = set()
    n_alleles = 0
    with vcf.open_text(path) as stream:
        _meta, _columns, samples = vcf.read_header(stream)
        if not samples:
            raise StepError("vcf_concordance: truth VCF has no samples")
        indices = vcf.sample_indices(samples, [sample] if sample else [])
        index = indices[0] if sample else 0
        for fixed, rest in vcf.iter_sites(stream):
            chrom, pos, _id, ref, alt_text, qual_text, filt, _info = fixed
            if not vcf.region_match(chrom, pos, region):
                continue
            qual = vcf.parse_qual(qual_text)
            if min_qual > 0 and (qual is None or qual < min_qual):
                continue
            if require_pass and filt != "PASS":
                continue
            alts = vcf.alt_alleles(alt_text)
            if not alts:
                continue
            pos_key = (vcf.chrom_key(chrom), int(pos))
            positions.add(pos_key)
            gt = _gt_value(rest, index)
            for alt_index, alt in enumerate(alts, 1):
                n_alleles += 1
                table[(pos_key[0], pos_key[1], alt.upper())] = (ref.upper(), gt, alt_index)
    return table, positions, n_alleles


class VcfConcordanceStep(Step):
    """Compare one sample's genotypes between a query and a truth VCF."""

    provider = "operon-core"
    parameters_file = "vcf_concordance.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}},
                    {'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "vcf_concordance",
        "version": "1.0.1",
        "kind": "operator",
        "title": "vcf_concordance",
        "description": "Site and genotype concordance between a query VCF and a truth VCF.",
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
                    "info": {"representation": {"type": "string", "enum": ["vcf", "vcf.gz"]}},
                },
                {
                    "version": 1,
                    "kind": "file",
                    "numeric": False,
                    "ndim": 0,
                    "dims": [],
                    "info": {"representation": {"type": "string", "enum": ["vcf", "vcf.gz"]}},
                },
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(artifact, "file_bytes", 0) or 0) for artifact in inputs or [])
        return max(int(size * 2.0), 8 * 1024**2), 64 * 1024

    def run(self, ctx: Context, inputs) -> None:
        if len(inputs) < 2:
            raise StepError("vcf_concordance requires query and truth VCF files")
        query, truth = inputs[0], inputs[1]
        for name, artifact in (("query", query), ("truth", truth)):
            if not isinstance(artifact, FileArtifact):
                raise StepError(f"vcf_concordance: {name} input must be a file artifact")
            artifact.validate()
            if artifact.format not in ("vcf", "vcf.gz"):
                raise StepError(f"vcf_concordance: {name} file is not VCF ({artifact.format!r})")

        params = dict(ctx.step_params)
        region = str(params.get("region") or "")
        min_qual = float(params.get("min_qual") or 0.0)
        require_pass = bool(params.get("require_pass", False))
        sample_query = str(params.get("sample_query") or "")
        sample_truth = str(params.get("sample_truth") or "")
        out_name = params.get("output") or self.name

        truth_table, truth_positions, n_truth = _load_truth(
            truth, sample_truth, region, min_qual, require_pass
        )

        n_query = 0
        matched = 0
        query_duplicates = 0
        allele_mismatch = 0
        compared = 0
        discordant = 0
        seen = set()

        query_path = next(iter(query.files.values()))
        with vcf.open_text(query_path) as stream:
            _meta, _columns, samples = vcf.read_header(stream)
            if not samples:
                raise StepError("vcf_concordance: query VCF has no samples")
            indices = vcf.sample_indices(samples, [sample_query] if sample_query else [])
            index = indices[0] if sample_query else 0
            for fixed, rest in vcf.iter_sites(stream):
                chrom, pos, _id, ref, alt_text, qual_text, filt, _info = fixed
                if not vcf.region_match(chrom, pos, region):
                    continue
                qual = vcf.parse_qual(qual_text)
                if min_qual > 0 and (qual is None or qual < min_qual):
                    continue
                if require_pass and filt != "PASS":
                    continue
                alts = vcf.alt_alleles(alt_text)
                if not alts:
                    continue
                pos_key = (vcf.chrom_key(chrom), int(pos))
                query_gt = _gt_value(rest, index)
                for alt_index, alt in enumerate(alts, 1):
                    n_query += 1
                    key = (pos_key[0], pos_key[1], alt.upper())
                    if key in seen:
                        query_duplicates += 1
                        continue
                    seen.add(key)
                    truth_row = truth_table.get(key)
                    if truth_row is None:
                        if pos_key in truth_positions:
                            allele_mismatch += 1
                        continue
                    truth_ref, truth_gt, truth_alt_index = truth_row
                    if ref.upper() != truth_ref:
                        allele_mismatch += 1
                        continue
                    matched += 1
                    query_dosage = vcf.genotype_dosage(query_gt or "", allele_index=alt_index)
                    truth_dosage = vcf.genotype_dosage(truth_gt or "", allele_index=truth_alt_index)
                    if query_dosage is None or truth_dosage is None:
                        continue
                    compared += 1
                    if query_dosage != truth_dosage:
                        discordant += 1

        query_only = max(n_query - matched - allele_mismatch, 0)
        truth_only = max(n_truth - matched, 0)
        concordance = (compared - discordant) / compared if compared else 0.0
        allele_concordance = matched / n_query if n_query else 0.0
        values = {
            "n_query_sites": n_query,
            "n_truth_sites": n_truth,
            "n_matched_sites": matched,
            "n_query_only": query_only,
            "n_query_duplicates": query_duplicates,
            "n_truth_only": truth_only,
            "n_allele_mismatch": allele_mismatch,
            "n_genotypes_compared": compared,
            "n_genotypes_discordant": discordant,
            "genotype_concordance": concordance,
            "allele_concordance": allele_concordance,
        }
        labels = {name: position for position, name in enumerate(_METRICS)}
        data = np.asarray([[float(values[name])] for name in _METRICS], dtype=float)
        form = Form(
            data=data,
            dims=["metric", "value"],
            labels={"metric": labels, "value": {"value": 0}},
            info={
                "query": str(query_path),
                "truth": str(next(iter(truth.files.values()))),
                "sample_query": sample_query or samples[0],
                "sample_truth": sample_truth or "",
                "region": region,
            },
        )
        ctx[out_name] = form
        self._export_data = values

    def export(self, ctx):
        n = getattr(self, "_export_data", {})
        print(
            "[vcf_concordance] matched {matched}/{query} alleles, genotype concordance {concordance:.3f}".format(
                matched=n.get("n_matched_sites", 0),
                query=n.get("n_query_sites", 0),
                concordance=n.get("genotype_concordance", 0.0),
            )
        )
        return n
