# maf

> Reviewed reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-genetics`
- Source: [`src/task/step/steps/maf.py`](../../../src/task/step/steps/maf.py)
- Tests: [`tasks/bgen_qc_demo/test_bgen_qc.py`](../../../tasks/bgen_qc_demo/test_bgen_qc.py), [`tasks/verify_bgen_qc.py`](../../../tasks/verify_bgen_qc.py), [`tasks/verify_genetics_operators.py`](../../../tasks/verify_genetics_operators.py)
- Demo tasks: [`tasks/bgen_qc_demo/task.yaml`](../../../tasks/bgen_qc_demo/task.yaml), [`tasks/gwas_demo/task.yaml`](../../../tasks/gwas_demo/task.yaml), [`tasks/maf_demo/task.yaml`](../../../tasks/maf_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 变异维度 | string |  |  |  | yes | basic |
| `threshold` | 最低 MAF | number | 0.01 | 0 | 0.5 |  | basic |

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
      "ploidy": {
        "type": "integer",
        "min": 1
      },
      "representation": {
        "type": "string",
        "enum": [
          "hard_call",
          "dosage"
        ]
      }
    },
    "dims": [
      {
        "param": "dim",
        "default": null
      }
    ],
    "labels": [],
    "parallel": [],
    "values": "allele_count"
  }
]
```

## Output contract

```json
{
  "mode": "subset"
}
```

## Processing rules (source docstring)

```text
Filter positions along one dimension by MAF.

    Params:
        dim       : dimension to compute MAF along
        threshold : minimum allowed MAF
        output    : context key for the result

--- module documentation ---

Minor allele frequency filter.
```

## Minimal YAML skeleton

```yaml
- name: maf
  inputs: [<input1>]
  params:
    dim: <string>
    threshold: <number>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Curated notes

## 审校补充（MAF）

- 按 `dim` 计算次等位基因频率并过滤低于 `threshold` 的位置。
- 需要 `info.ploidy` 和 `missing_code`；输入是 ALT 等位基因计数/剂量。
- 单倍体/多倍体语义不同；不要把二倍体公式套到非二倍体。
- MAF 过滤会改变后续 HWE/LD/PCA 的位点集，必须在 ANALYSIS 写明阈值和保留数量。
- 单态位点（MAF=0）是否保留取决于阈值；不要默认它们“无信息”而静默删除。
