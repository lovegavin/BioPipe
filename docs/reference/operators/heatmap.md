# heatmap

> Reviewed reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-plots`
- Source: [`src/task/step/steps/heatmap.py`](../../../src/task/step/steps/heatmap.py)
- Tests: [`tests/test_heatmap_limits.py`](../../../tests/test_heatmap_limits.py)
- Demo tasks: [`tasks/correlation_demo/task.yaml`](../../../tasks/correlation_demo/task.yaml), [`tasks/heatmap_demo/task.yaml`](../../../tasks/heatmap_demo/task.yaml), [`tasks/kmer_count_demo/task.yaml`](../../../tasks/kmer_count_demo/task.yaml), [`tasks/microbiome_demo/task.yaml`](../../../tasks/microbiome_demo/task.yaml), [`tasks/motif_scan_demo/task.yaml`](../../../tasks/motif_scan_demo/task.yaml), [`tasks/proteomics_de_demo/task.yaml`](../../../tasks/proteomics_de_demo/task.yaml), [`tasks/rnaseq_de_demo/task.yaml`](../../../tasks/rnaseq_de_demo/task.yaml), [`tasks/scrnaseq_demo/task.yaml`](../../../tasks/scrnaseq_demo/task.yaml), [`tasks/sequence_profiling_demo/task.yaml`](../../../tasks/sequence_profiling_demo/task.yaml), [`tasks/sop_demo/task.yaml`](../../../tasks/sop_demo/task.yaml)
- Inputs arity: `1`; output parameter: `None`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `cluster_cols` | 聚类列 | boolean | True |  |  |  | advanced |
| `cluster_rows` | 聚类行 | boolean | True |  |  |  | advanced |
| `cmap` | 配色 | string | RdBu_r |  |  |  | advanced |
| `dim` | 分析维度 | string | feature |  |  |  | basic |
| `figsize` | 画布尺寸 [宽, 高] | object / array |  |  |  |  | advanced |
| `filename` | 图片文件名 | string |  |  |  | yes | basic |
| `labels` | 特征标签 | array |  |  |  |  | basic |
| `nan_color` | 缺失值颜色 | string | #DDDDDD |  |  |  | advanced |
| `other_dim` | 样本维度 | string | sample |  |  |  | basic |
| `select` | 特征选择 | any; enum=['variance', 'label', 'all'] | variance |  |  |  | basic |
| `show_col_labels` | 显示列标签 | boolean | True |  |  |  | advanced |
| `show_row_labels` | 显示行标签 | boolean | False |  |  |  | advanced |
| `standardize` | 标准化 | any; enum=['none', 'row', 'col'] | none |  |  |  | basic |
| `title` | 图标题 | string |  |  |  |  | basic |
| `max_cells` | 最大渲染单元数 | integer | 4000000 | 1 |  |  | basic |
| `max_pixels` | 最大渲染像素数 | integer | 40000000 | 1000000 |  |  | basic |
| `top_n` | 最多特征数 | integer | 50 | 1 |  |  | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [
      {
        "param": "dim",
        "default": "feature"
      },
      {
        "param": "other_dim",
        "default": "sample"
      }
    ],
    "labels": [],
    "parallel": [],
    "ndim": 2
  }
]
```

## Output contract

```json
{
  "mode": "none"
}
```

## Processing rules (source docstring)

```text
Draw a heatmap of a 2D form.

--- module documentation ---

Heatmap of a 2D form.

Renders the matrix as an image with one cell per position. Rows and
columns can be reordered by hierarchical clustering, and rows can be
standardized before plotting.

Row selection
-------------
    select="variance"   pick the top ``top_n`` rows by variance
                        (default)
    select="label"      pick the rows named in ``labels``
    select="all"        keep all rows

Standardization
---------------
    standardize="row"   z-score each row (mean 0, std 1)
    standardize="col"   z-score each column
    standardize="none"  no transformation (default)

Missing values are shown as the ``nan_color``.

Params:
    dim          : feature dim (default "feature")
    other_dim    : sample dim (default "sample")
    select       : "variance" | "label" | "all"
    top_n        : number of rows when select="variance" (default 50)
    labels       : list of row labels when select="label"
    standardize  : "row" | "col" | "none"
    cluster_rows : hierarchical clustering of rows (default True)
    cluster_cols : hierarchical clustering of columns (default True)
    filename     : output file name (required)
    title        : optional plot title
    cmap         : matplotlib colormap (default "RdBu_r")
    nan_color    : color for missing cells (default "#DDDDDD")
    figsize      : [width, height] in inches (default auto)
    max_cells    : refuse selected matrices larger than this (default 4,000,000)
    max_pixels   : clamp the rendered canvas to this pixel budget (default 40,000,000)
    show_row_labels   : show row tick labels (default False)
    show_col_labels   : show column tick labels (default True)
```

## Minimal YAML skeleton

```yaml
- name: heatmap
  inputs: [<input1>]
  params:
    cluster_cols: <boolean>
    cluster_rows: <boolean>
    cmap: <string>
    dim: <string>
    figsize: <object / array>
    filename: <string>
    labels: <array>
    nan_color: <string>
    other_dim: <string>
    select: <any; enum=['variance', 'label', 'all']>
    show_col_labels: <boolean>
    show_row_labels: <boolean>
    standardize: <any; enum=['none', 'row', 'col']>
    title: <string>
    max_cells: <integer>
    max_pixels: <integer>
    top_n: <integer>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Curated notes

## 审校补充（热图）

- 行数由 `select` 决定：`variance` 只取 `top_n` 行；`label` 取 `labels`；`all` 保留全部行。
- 2026-10 起增加 `max_cells`（默认 4,000,000）：选中矩阵超过上限直接报错，不会进入 Matplotlib。对 5247×5247 这类相关矩阵必须先用 `top_n`/子集/聚合。
- `max_pixels`（默认 40,000,000）限制自动 figsize 的像素预算；超过时按比例缩小画布，不改变矩阵数值。
- `standardize='row'` 是每个基因在样本间 z-score，不是跨基因标准化；解读颜色前必须确认。
- 聚类只改变行列顺序，不改变数值；聚类结果不应当作分组依据。
- 热图不能证明因果、不能替代统计检验；相关矩阵热图不能说明细胞类型或调控关系。
- 缺失值用 `nan_color` 显示；大量缺失时先回到 Reader/QC 检查，不要用颜色掩盖。
