"""Species-pool richness estimators (vegan::specpool semantics)."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._ecology_common import abundance, group_codes
from ._ext_common import make_form


_STATISTICS = ["Species", "chao", "chao.se", "jack1", "jack1.se",
               "jack2", "boot", "boot.se", "n"]


class SpecpoolStep(Step):
    provider = 'operon-microbiome'
    parameters_file = 'specpool.SpecpoolStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'specpool',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Species pool estimators',
        'category': 'Omics',
        'contracts': {
            'version': 1,
            'inputs': [
                {'version': 1, 'numeric': True, 'info': {},
                 'dims': [{'param': 'sample_dim', 'default': 'sample'},
                          {'param': 'taxon_dim', 'default': 'taxon'}],
                 'labels': [], 'parallel': [], 'ndim': 2},
                {'version': 1, 'numeric': True, 'info': {},
                 'dims': [{'param': 'sample_dim', 'default': 'sample'},
                          {'param': 'group_dim', 'default': 'feature'}],
                 'labels': [], 'parallel': [], 'ndim': 2},
            ],
            'output': {'mode': 'declare',
                       'schema': {'ndim': 2, 'numeric': True,
                                  'info_open': True, 'axis_info_open': True}},
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False,
                      'estimate': 'estimate_memory'},
        'dependencies': ['numpy>=1.24'],
        'dependency_imports': ['numpy'],
        'inputs_arity': 2,
        'outputs': [],
        'output_parameter': 'output',
        'description': 'Chao, first- and second-order jackknife and bootstrap '
                       'species-pool richness estimators with standard errors.',
    }

    def run(self, ctx: Context, inputs) -> None:
        abundance_form, meta = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        taxon_dim = ctx.step_params.get("taxon_dim", "taxon")
        group_label = ctx.step_params["group_label"]
        smallsample = bool(ctx.step_params.get("smallsample", True))
        out_name = ctx.step_params.get("output", self.name)
        data, samples, taxa = abundance(abundance_form, sample_dim, taxon_dim,
                                        "specpool")
        codes = group_codes(meta, sample_dim, group_label, samples, "specpool")
        pools = sorted(set(codes))
        if not pools:
            raise StepError("specpool: no pools found")
        rows = []
        for pool in pools:
            counts = data[codes == pool]
            n = counts.shape[0]
            if n < 1:
                raise StepError(f"specpool: pool {pool!r} has no samples")
            frequency = (counts > 0).sum(axis=0)
            observed = int(np.count_nonzero(frequency > 0))
            if observed == 0:
                raise StepError(f"specpool: pool {pool!r} has no observed species")
            ssc = (n - 1.0) / n if smallsample else 1.0
            a1 = int(np.count_nonzero(frequency == 1))
            a2 = int(np.count_nonzero(frequency == 2))
            chao = observed + (ssc * a1 * a1 / (2.0 * a2) if a2 > 0
                               else ssc * a1 * (a1 - 1) / 2.0)
            jack1 = observed + a1 * (n - 1.0) / n
            if n > 1:
                jack2 = (observed + a1 * (2.0 * n - 3.0) / n
                         - a2 * (n - 2.0) ** 2 / (n * (n - 1.0)))
            else:
                jack2 = float(observed)
            p = frequency[frequency > 0] / n
            boot = observed + float(np.sum((1.0 - p) ** n))
            if a2 > 0:
                ratio = a1 / a2
                var_chao = a1 * ssc * (0.5 + ssc * (1.0 + ratio / 4.0) * ratio) * ratio
            else:
                var_chao = ssc * (
                    ssc * (a1 * (2.0 * a1 - 1.0) ** 2 / 4.0
                           - a1 ** 4 / chao / 4.0)
                    + a1 * (a1 - 1.0) / 2.0)
            if a1 > 0:
                singletons = (counts[:, frequency == 1] > 0).sum(axis=1)
                counts_of = np.bincount(singletons)
                weighted = np.sum(np.arange(counts_of.size) ** 2 * counts_of)
                var_jack1 = (weighted - a1 / n) * (n - 1.0) / n
            else:
                var_jack1 = 0.0
            pn = (1.0 - p) ** n
            present = counts[:, frequency > 0]
            joint = (present == 0).T.astype(np.float64) @ (present == 0).astype(np.float64)
            zp = (joint / n) ** n - np.outer(pn, pn)
            lower = np.tril_indices(zp.shape[0], -1)
            var_boot = float(np.sum(pn * (1.0 - pn)) + 2.0 * np.sum(zp[lower]))
            rows.append([observed, chao, np.sqrt(max(var_chao, 0.0)), jack1,
                         np.sqrt(max(var_jack1, 0.0)), jack2, boot,
                         np.sqrt(max(var_boot, 0.0)), n])
        pool_labels = {str(pool): i for i, pool in enumerate(pools)}
        statistics = {name: i for i, name in enumerate(_STATISTICS)}
        ctx[out_name] = make_form(
            np.asarray(rows, dtype=np.float64),
            ["pool", "statistic"],
            {"pool": pool_labels, "statistic": statistics},
            {"method": "specpool", "smallsample": smallsample,
             "n_pools": len(pools), "n_taxa": len(taxa)},
        )
        self._export = {"pools": [str(p) for p in pools],
                        "n_pools": len(pools),
                        "species": [int(row[0]) for row in rows]}
        print(f"[specpool] pools={len(pools)} taxa={len(taxa)}")

    def export(self, ctx: Context) -> dict:
        return self._export
