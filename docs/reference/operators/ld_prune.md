# ld_prune

> Reviewed reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-genetics`
- Source: [`src/task/step/steps/ld_prune.py`](../../../src/task/step/steps/ld_prune.py)
- Tests: [`tasks/bgen_qc_demo/test_bgen_qc.py`](../../../tasks/bgen_qc_demo/test_bgen_qc.py), [`tasks/verify_bgen_qc.py`](../../../tasks/verify_bgen_qc.py), [`tasks/verify_genetics_operators.py`](../../../tasks/verify_genetics_operators.py)
- Demo tasks: [`tasks/bgen_qc_demo/task.yaml`](../../../tasks/bgen_qc_demo/task.yaml), [`tasks/gwas_demo/task.yaml`](../../../tasks/gwas_demo/task.yaml), [`tasks/ld_prune_demo/task.yaml`](../../../tasks/ld_prune_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 变异维度 | string |  |  |  | yes | basic |
| `r2` | R² 阈值 | number | 0.2 | 0 | 1 |  | basic |
| `window` | 窗口大小 | integer | 50 | 1 |  |  | basic |

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
      }
    },
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
  "mode": "subset"
}
```

## Processing rules (source docstring)

```text
Prune positions along one dimension by LD.

Params:
    dim    : dimension to prune along
    window : window size in positions
    r2     : r^2 threshold
    output : context key for the result

--- module documentation ---

LD pruning.
```

## Minimal YAML skeleton

```yaml
- name: ld_prune
  inputs: [<input1>]
  params:
    dim: <string>
    r2: <number>
    window: <integer>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Curated notes

## 审校补充（LD 修剪）

- 沿 `dim`（通常是 variant）按窗口和 `r2` 阈值贪心修剪；窗口是位置数，不是物理距离。
- 输入必须是硬调用/剂量基因型，带 `missing_code`；缺失过多的位点先 QC。
- 修剪顺序受输入顺序影响；不同排序可能保留不同 tag SNP，需在 ANALYSIS 说明。
- 只做 LD 去冗余，不做因果/功能判断；被移除的位点不代表不重要。
- `window`/`r2` 没有通用最优值，必须按物种/群体/芯片密度设定。
