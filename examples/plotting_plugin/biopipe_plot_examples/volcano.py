"""Publication volcano plot and companion significance histogram."""
from biopipe_sdk import Operator, save_matplotlib, figure_collection, publication_style

class Volcano(Operator):
    parameters_file = 'volcano.parameters.json'
    definition = {'protocol_version': 3, 'version': '0.1.0', 'kind': 'operator', 'category': '可视化', 'icon': 'ChartLine', 'inputs_arity': 1, 'outputs': [], 'output_parameter': None, 'contracts': {'version': 1, 'inputs': [{'kind': 'form', 'numeric': True, 'ndim': 2, 'dims': ['feature', 'stat']}], 'output': {'mode': 'report'}}, 'resources': {'memory_modes': ['full'], 'estimate': 'estimate_memory'}, 'id': 'example.volcano', 'title': 'Volcano + significance distribution', 'dependencies': ['numpy>=1.26', 'matplotlib>=3.8']}

    def compute(self, inputs, params, context):
        import numpy as np
        import matplotlib.pyplot as plt
        form = inputs[0]
        if form.dims != ['feature', 'stat']:
            raise ValueError('Expected a feature-by-stat matrix')
        columns = form.labels['stat']
        if not {'log2FC', 'padj'} <= columns.keys():
            raise ValueError('Input requires log2FC and padj columns; padj must already be FDR adjusted')
        effect = form.data[:, columns['log2FC']]
        q = form.data[:, columns['padj']]
        if np.any((q[np.isfinite(q)] < 0) | (q[np.isfinite(q)] > 1)):
            raise ValueError('padj must lie between zero and one')
        keep = np.isfinite(effect) & np.isfinite(q)
        effect, q = effect[keep], q[keep]
        significance = -np.log10(np.maximum(q, np.finfo(float).tiny))
        selected = (q <= params['fdr']) & (np.abs(effect) >= params['effect_threshold'])
        publication_style(context)
        fig, ax = plt.subplots()
        ax.scatter(effect, significance, c=np.where(selected, params['highlight'], '#999999'), s=5, rasterized=True)
        ax.axhline(-np.log10(params['fdr']), color='#555555', linestyle='--', linewidth=.6)
        ax.set(xlabel='log2 fold change', ylabel='-log10 adjusted P', title=params['title'])
        volcano = save_matplotlib(context, fig, 'volcano.pdf', figure_id='volcano', title=params['title'])
        fig, ax = plt.subplots()
        ax.hist(q, bins=20, color='#0072B2', edgecolor='white', linewidth=.4)
        ax.set(xlabel='Adjusted P', ylabel='Features')
        distribution = save_matplotlib(context, fig, 'distribution.pdf', figure_id='distribution', title='Adjusted P distribution')
        return {**figure_collection(volcano, distribution), 'n_features': int(len(q)), 'n_excluded': int((~keep).sum())}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return int(inputs[0].data.shape[0]) * 160 + 64 * 1024**2, 0
