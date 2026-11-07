"""KING-robust kinship coefficients from a multi-sample VCF.

The estimator is the KING-robust between-family formula (Manichaikul et al.
2010, Eq. 11), the same estimator used by plink2 `--make-king-table`:

    phi_ij = 1/2 - (N_IBS1 + 4 N_IBS0) / (4 min(N_Aa(i), N_Aa(j)))

over autosomal biallelic SNPs where both samples are called, with
N_IBS1 = N_Aa(i) + N_Aa(j) - 2 N_Aa,Aa.  It is robust to population structure,
so unrelated pairs centre near zero while duplicates and first-degree relatives
move toward 0.5 and 0.25.

Output: square 2D Form [sample, sample] (diagonal self-kinship 0.5).
"""
from __future__ import annotations

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps import _vcf_utils as vcf


class VcfRelatednessStep(Step):
    """KING-robust kinship matrix for the selected VCF samples."""
    provider = 'operon-core'
    parameters_file = 'vcf_relatedness.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'vcf_relatedness',
     'version': '1.0.1',
     'kind': 'operator',
     'title': 'vcf_relatedness',
     'description': 'KING-robust between-family kinship coefficients between samples of a VCF (plink2 --make-king-table compatible).',
     'category': 'Genome',
     'icon': 'Users',
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
        samples = max(int(params.get("max_samples", 50) or 50), 1)
        variants = int(params.get("max_variants", 0) or 200000)
        return max(int(variants * samples * 16), 8 * 1024**2), 64 * 1024

    def run(self, ctx: Context, inputs) -> None:
        if not inputs or not isinstance(inputs[0], FileArtifact):
            raise StepError("vcf_relatedness requires a VCF file artifact")
        artifact = inputs[0]
        artifact.validate()
        if artifact.format not in ("vcf", "vcf.gz"):
            raise StepError(f"vcf_relatedness requires a VCF file, got {artifact.format!r}")

        params = dict(ctx.step_params)
        out_name = params.get("output") or self.name
        region = str(params.get("region") or "")
        requested = [name.strip() for name in str(params.get("samples") or "").split(",") if name.strip()]
        max_samples = int(params.get("max_samples") or 0)
        min_maf = float(params.get("min_maf", 0.05))
        min_call = float(params.get("min_call_rate", 0.9))
        max_variants = int(params.get("max_variants") or 0)

        path = next(iter(artifact.files.values()))
        dosages = []
        used_names = []

        with vcf.open_text(path) as stream:
            _meta, _columns, samples = vcf.read_header(stream)
            if not samples:
                raise StepError("vcf_relatedness: VCF has no samples")
            indices = vcf.sample_indices(samples, requested)
            if max_samples and len(indices) > max_samples:
                indices = indices[:max_samples]
            used_names = [samples[index] for index in indices]
            n = len(used_names)
            for fixed, rest in vcf.iter_sites(stream):
                chrom, pos, _id, ref, alt_text, _qual, _filt, _info = fixed
                if not vcf.region_match(chrom, pos, region):
                    continue
                alts = vcf.alt_alleles(alt_text)
                if len(alts) != 1 or len(ref) != 1 or len(alts[0]) != 1:
                    continue
                fields = rest.split("\t") if rest else []
                if not fields:
                    continue
                fmt = fields[0].split(":")
                if "GT" not in fmt:
                    continue
                gt_index = fmt.index("GT")
                row = np.full(n, np.nan, dtype=np.float32)
                for slot, index in enumerate(indices):
                    values = fields[1 + index].split(":") if len(fields) > 1 + index else []
                    if gt_index < len(values):
                        value = vcf.genotype_dosage(values[gt_index])
                        if value is not None:
                            row[slot] = value
                called = int(np.count_nonzero(~np.isnan(row)))
                if called < max(int(np.ceil(min_call * n)), 1):
                    continue
                allele_freq = float(np.nansum(row)) / (2.0 * called)
                maf = min(allele_freq, 1.0 - allele_freq)
                if maf < min_maf:
                    continue
                dosages.append(row)
                if max_variants and len(dosages) >= max_variants:
                    break

        if not dosages:
            raise StepError(
                "vcf_relatedness: no biallelic SNP passed the MAF/call-rate filters"
            )

        matrix = np.vstack(dosages).astype(np.float32)
        called = ~np.isnan(matrix)
        het = (matrix == 1.0)
        hom_ref = (matrix == 0.0)
        hom_alt = (matrix == 2.0)

        n_het = het.sum(axis=0).astype(np.float64)
        het_pairs = het.astype(np.float64).T @ het.astype(np.float64)
        opposite_hom = hom_ref.astype(np.float64).T @ hom_alt.astype(np.float64)
        opposite_hom = opposite_hom + opposite_hom.T
        ibs1 = n_het[:, None] + n_het[None, :] - 2.0 * het_pairs
        min_het = np.minimum(n_het[:, None], n_het[None, :])
        denominator = 4.0 * min_het
        with np.errstate(invalid="ignore", divide="ignore"):
            kinship = 0.5 - (ibs1 + 4.0 * opposite_hom) / denominator
        kinship = np.where(min_het > 0, kinship, np.nan).astype(np.float32)

        form = Form(
            data=kinship,
            dims=["sample", "sample_b"],
            labels={
                "sample": {name: index for index, name in enumerate(used_names)},
                "sample_b": {name: index for index, name in enumerate(used_names)},
            },
            info={
                "missing_code": np.nan,
                "representation": "vcf_relatedness",
                "n_variants": int(matrix.shape[0]),
                "n_samples": n,
                "estimator": "KING-robust between-family (Eq. 11)",
                "min_maf": min_maf,
                "min_call_rate": min_call,
            },
        )
        ctx[out_name] = form
        off_diagonal = kinship[~np.eye(n, dtype=bool)] if n > 1 else np.array([])
        self._report = {
            "n_samples": n,
            "n_variants": int(matrix.shape[0]),
            "mean_off_diagonal": round(float(np.nanmean(off_diagonal)), 6) if off_diagonal.size else 0.0,
            "max_off_diagonal": round(float(np.nanmax(off_diagonal)), 6) if off_diagonal.size else 0.0,
            "samples": used_names[:10],
        }
        print(
            f"[vcf_relatedness] {n} samples x {matrix.shape[0]} SNPs, "
            f"mean kinship={self._report['mean_off_diagonal']:.4f}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_report", {})
