# correlation

> Reviewed reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-microbiome`
- Source: [`src/task/step/steps/correlation.py`](../../../src/task/step/steps/correlation.py)
- Tests: [`tasks/correlation_demo/test_correlation.py`](../../../tasks/correlation_demo/test_correlation.py), [`tasks/verify_existing_operators.py`](../../../tasks/verify_existing_operators.py), [`tests/test_extension7.py`](../../../tests/test_extension7.py)
- Demo tasks: [`tasks/correlation_demo/task.yaml`](../../../tasks/correlation_demo/task.yaml), [`tasks/microbiome_demo/task.yaml`](../../../tasks/microbiome_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 分析维度 | string |  |  |  | yes | basic |
| `metric` | 距离/相关指标 | string; enum=['pearson', 'spearman', 'kendall', 'cosine', 'jaccard', 'overlap'] | pearson |  |  |  | advanced |
| `min_valid` | 最少有效值 | integer | 3 | 2 |  |  | basic |
| `max_positions` | 最大位置数 | integer / null | None | 1 |  |  | basic |

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
        "default": null
      }
    ],
    "labels": [],
    "parallel": []
  }
]
```

## Output contract

```json
{
  "mode": "project",
  "derived": true,
  "info": {
    "missing_code": {
      "type": [
        "number",
        "null"
      ]
    },
    "representation": {
      "type": "string",
      "const": "correlation"
    }
  },
  "keep_dims": [
    {
      "param": "dim",
      "default": null
    }
  ],
  "append_dims": [
    {
      "name": {
        "param": "dim",
        "suffix": "_b"
      },
      "labels_from": {
        "param": "dim",
        "default": null
      }
    }
  ]
}
```

## Processing rules (source docstring)

```text
Pairwise correlation matrix along one axis.

--- module documentation ---

Pairwise correlation matrix along one axis of a form.

For every pair of positions along ``dim``, computes the correlation
of their values across the other axes. The output is a square form
with the same labels on both axes.

This is the natural companion of ``distance_matrix``. Where
``distance_matrix`` measures dissimilarity, this measures
similarity. Both are useful for sample QC, feature clustering,
co-expression analysis, and as input to a heatmap.

Output dims
-----------
    dims = [dim, f"{dim}_b"]

Both axes carry the same labels, in the same order. ``form.data[i, j]``
is the correlation between position ``i`` and position ``j``.

Metrics
-------
    pearson       Pearson product-moment correlation (default)
    spearman      Spearman rank correlation
    kendall       Kendall's tau
    cosine        cosine similarity (dot product of normalized rows)
    jaccard       Jaccard similarity on binarized (>0) values
    overlap       overlap coefficient |A and B| / min(|A|, |B|),
                  on binarized (>0) values

Missing values
--------------
Missing cells are handled pairwise: for each pair (i, j), only
positions where both i and j are valid contribute to the
correlation. This matches the standard treatment of missing data in
correlation matrices.

Size guard
----------
The output is a dense ``n x n`` matrix. The memory planner accounts for its
quadratic allocation. An optional ``max_positions`` adds a count limit;
the default is None, leaving admission to the configured memory budget.

Params:
    dim            : axis to compute correlations along (required)
    metric         : metric name (default "pearson")
    min_valid      : minimum number of valid positions per pair
                     (default 3)
    max_positions  : refuse if dim has more positions than this
                     (default None; governed by the memory budget)
    output         : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: correlation
  inputs: [<input1>]
  params:
    dim: <string>
    metric: <string; enum=['pearson', 'spearman', 'kendall', 'cosine', 'jaccard', 'overlap']>
    min_valid: <integer>
    max_positions: <integer / null>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Curated notes

## 审校补充（相关矩阵）

- `correlation` 输出 `positions × positions` 的稠密矩阵；5247 个位置会产生约 27.5M 个单元，时间/内存都很高。
- 先用 `max_positions` 或上游 `select/top_n` 限制位置；相关矩阵不要直接接全量热图，先取子集/聚类均值/PC。
- `pearson` 对离群值和线性关系敏感；`spearman` 对单调非线性更稳健，但仍是关联，不是因果。
- 缺失处理会影响相关系数；在 ANALYSIS 中写明缺失比例和是否成对删除。
- 相关矩阵的对角线恒为 1，热图解读时应关注非对角块，不要用对角线颜色下结论。
