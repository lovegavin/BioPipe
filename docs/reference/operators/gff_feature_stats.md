# gff_feature_stats

> Reviewed reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/gff_feature_stats.py`](../../../src/task/step/steps/gff_feature_stats.py)
- Tests: [`tasks/gff_feature_stats_demo/test_gff_feature_stats.py`](../../../tasks/gff_feature_stats_demo/test_gff_feature_stats.py), [`tasks/gtf_annotation_demo/test_gtf_annotation.py`](../../../tasks/gtf_annotation_demo/test_gtf_annotation.py), [`tasks/verify_gtf_annotation.py`](../../../tasks/verify_gtf_annotation.py), [`tasks/verify_operators.py`](../../../tasks/verify_operators.py)
- Demo tasks: [`tasks/annotation_qc_demo/task.yaml`](../../../tasks/annotation_qc_demo/task.yaml), [`tasks/gff_feature_stats_demo/task.yaml`](../../../tasks/gff_feature_stats_demo/task.yaml), [`tasks/gtf_annotation_demo/task.yaml`](../../../tasks/gtf_annotation_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `record_dim` | 记录维度 | string | record |  |  |  | basic |
| `field_dim` | 字段维度 | string | field |  |  |  | advanced |
| `output` | 输出名称 | string |  |  |  |  | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {
      "missing_code": {
        "type": [
          "number",
          "null"
        ]
      },
      "encoders": {
        "type": "object",
        "optional": true
      }
    },
    "dims": [
      {
        "param": "record_dim",
        "default": "record"
      },
      {
        "param": "field_dim",
        "default": "field"
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
  "mode": "declare",
  "schema": {
    "ndim": 2,
    "numeric": true,
    "info_open": true,
    "axis_info_open": true
  }
}
```

## Processing rules (source docstring)

```text
Per-feature-type length and count statistics for GFF3/GTF.

--- module documentation ---

Per-feature-type statistics for any GFF3/GTF Form.
```

## Minimal YAML skeleton

```yaml
- name: gff_feature_stats
  inputs: [<input1>]
  params:
    record_dim: <string>
    field_dim: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Curated notes

## 审校补充（GFF 特征统计）

- 输入是 GFF3/GTF Reader 的 `[record, field]` Form；按 `type` 分组。
- 统计 count、总长度、平均/最小/最大长度、每 gene 平均 exon 数；长度按 `end-start+1`（1-based inclusive）。
- `gene`/`exon` 识别依赖编码列和属性列；缺少层级时相应统计可能为空。
- 这不是“基因组覆盖率”；覆盖率需先合并区间再除以参考基因组长度。
- 不同注释版本（GENCODE/Ensembl/RefSeq）不要直接混在同一张表比较。
