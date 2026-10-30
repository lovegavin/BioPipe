"""Bounded row selection, file exchange, native R ComplexHeatmap rendering."""
from biopipe_sdk import Operator, run_r, register_figure

class ComplexHeatmap(Operator):
    parameters_file = 'complex_heatmap.parameters.json'
    definition = {'protocol_version': 3, 'version': '0.1.0', 'kind': 'operator', 'category': '可视化', 'icon': 'ChartLine', 'inputs_arity': 1, 'outputs': [], 'output_parameter': None, 'contracts': {'version': 1, 'inputs': [{'kind': 'form', 'numeric': True, 'ndim': 2}], 'output': {'mode': 'report'}}, 'resources': {'memory_modes': ['full'], 'estimate': 'estimate_memory', 'r': {'version': '>=4.3,<5', 'packages': [{'name': 'ComplexHeatmap', 'source': 'bioconductor', 'version': '>=2.18'}]}}, 'id': 'example.complex_heatmap', 'title': 'ComplexHeatmap', 'dependencies': ['numpy>=1.26']}

    def compute(self, inputs, params, context):
        import csv
        import uuid
        form = inputs[0]
        count = min(params['top_n'], form.data.shape[0]) if params['top_n'] else form.data.shape[0]
        matrix = context.artifact_path('heatmap-input-' + uuid.uuid4().hex[:12] + '.tsv')
        rows = {v: k for k, v in form.labels[form.dims[0]].items()}
        columns = {v: k for k, v in form.labels[form.dims[1]].items()}
        with matrix.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream, delimiter='\t')
            writer.writerow(['feature', *[columns[i] for i in range(form.data.shape[1])]])
            for i in range(count):
                writer.writerow([rows[i], *form.data[i]])
        output = run_r(context, self.definition['resources']['r'], R_SCRIPT, inputs={'matrix': str(matrix)})
        return {**register_figure(context, 'heatmap', {fmt: output / ('heatmap.'+fmt) for fmt in ('pdf','svg','png')},
                                  title=params['title'], width_mm=params['figure_width_mm'], height_mm=params['figure_height_mm'], dpi=params['figure_dpi']),
                'rows_plotted': count, 'rows_available': int(form.data.shape[0])}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        rows, cols = inputs[0].data.shape
        rows = min(rows, params.get('top_n', 50)) if params.get('top_n', 50) else rows
        return int(rows*cols*40 + (rows*rows+cols*cols)*16 + 256*1024**2), 0

R_SCRIPT = r'''
matrix <- as.matrix(read.delim(inputs$matrix, row.names=1, check.names=FALSE, fileEncoding="UTF-8"))
render <- function() {
  ht <- ComplexHeatmap::Heatmap(matrix, name="Value", column_title=params$title,
    cluster_rows=params$cluster_rows, cluster_columns=params$cluster_columns,
    row_names_gp=grid::gpar(fontsize=params$figure_font_size),
    column_names_gp=grid::gpar(fontsize=params$figure_font_size))
  ComplexHeatmap::draw(ht)
}
w <- params$figure_width_mm/25.4; h <- params$figure_height_mm/25.4
pdf(file.path(output_dir,"heatmap.pdf"),width=w,height=h,useDingbats=FALSE); render(); dev.off()
svg(file.path(output_dir,"heatmap.svg"),width=w,height=h); render(); dev.off()
png(file.path(output_dir,"heatmap.png"),width=w,height=h,units="in",res=params$figure_dpi); render(); dev.off()
'''
