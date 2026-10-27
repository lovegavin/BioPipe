# annotation_gaps

> Reviewed reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/annotation_gaps.py`](../../../src/task/step/steps/annotation_gaps.py)
- Tests: [`tasks/annotation_gaps_demo/test_annotation_gaps.py`](../../../tasks/annotation_gaps_demo/test_annotation_gaps.py), [`tasks/gtf_annotation_demo/test_gtf_annotation.py`](../../../tasks/gtf_annotation_demo/test_gtf_annotation.py), [`tasks/verify_gtf_annotation.py`](../../../tasks/verify_gtf_annotation.py), [`tasks/verify_operators.py`](../../../tasks/verify_operators.py)
- Demo tasks: [`tasks/annotation_gaps_demo/task.yaml`](../../../tasks/annotation_gaps_demo/task.yaml), [`tasks/annotation_qc_demo/task.yaml`](../../../tasks/annotation_qc_demo/task.yaml), [`tasks/gtf_annotation_demo/task.yaml`](../../../tasks/gtf_annotation_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `record_dim` | 记录维度 | string | record |  |  |  | basic |
| `field_dim` | 字段维度 | string | field |  |  |  | advanced |
| `min_gap` | 最小间隙 | integer | 0 | 0 |  |  | basic |
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
Inter-gene gap lengths for GFF3/GTF annotation QC.

--- module documentation ---

Inter-gene gap statistics for any GFF3/GTF Form.
```

## Minimal YAML skeleton

```yaml
- name: annotation_gaps
  inputs: [<input1>]
  params:
    record_dim: <string>
    field_dim: <string>
    min_gap: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Curated notes

## 审校补充（注释间隙）

- 输入必须是 GFF3/GTF Reader 产生的 `[record, field]` Form；记录顺序会影响相邻基因间隙。
- 只对同一染色体/同一 `type` 的相邻记录计算；跨染色体的“间隙”无意义。
- `min_gap` 过滤短于该值的间隙；坐标基准与输入 Reader 一致（GFF/GTF 1-based）。
- 重叠基因会产生负/零间隙；先决定是否排除重叠或按转录本聚合。
- 结果不能直接解释为“基因间调控长度”，只是注释记录之间的距离。
