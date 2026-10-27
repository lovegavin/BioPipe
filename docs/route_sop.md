# BioPipe 自定义任务 SOP

本标准适用于：用户有一组新数据，希望在 BioPipe 中用现有 Reader 和算子搭建一条可复现的分析路线，而不要求用户或 LLM 通读整个仓库。

## 1. 角色

| 角色 | 负责 |
|---|---|
| 用户 | 提供数据的**绝对路径**、分析目标（可省略）、审查 `ANALYSIS.md`、执行导入/运行 |
| LLM | 检查数据、查说明书/索引、按需读源码、写 `task.yaml` 和 `ANALYSIS.md`、做静态校验、解释每一步和图片 |
| BioPipe | 按 Reader/算子契约执行；不替用户判断科学问题 |

## 2. 目录约定

```text
tasks/<slug>/
  input/                 # 用户数据（可含多个文件/文件组）
  task.yaml              # LLM 生成，BioPipe 执行
  ANALYSIS.md            # LLM 生成，说明数据、步骤、理由、图片
  output/                # 运行时生成，不手工编辑
```

`<slug>` 只能使用字母、数字、下划线、短横线；建议 `data_topic_goal`，例如 `airway_dex_deg`。

仓库内有一个已走通的最小示例：`tasks/sop_demo/`（`input/` + `task.yaml` + `ANALYSIS.md` + 实际运行产物）。

## 3. 路径规则

1. 用户在对话中提供**绝对路径**，例如 `<数据目录>\airway_counts.csv`。
2. LLM 必须先验证路径存在、是文件、可读；不能猜文件名或目录。
3. LLM 把文件复制或硬链接到 `tasks/<slug>/input/`（大文件优先硬链接；跨盘则复制）。
4. `task.yaml` 中只写相对任务目录的路径，例如 `input/airway_counts.csv`。
5. LLM 必须在 `ANALYSIS.md` 写明：
   - 用户给的绝对路径；
   - 实际落到的相对路径；
   - 为什么这样处理：绝对路径用于消除歧义，相对路径保证任务可移动、可导入 Studio。

默认写相对路径；单机调试（尤其是 Studio profile 与项目不在同一盘）允许写项目内绝对路径，此时 Studio 导入不需要基准目录，但该任务不宜直接分享到其他机器。

## 4. 标准流程

### 阶段 0：准备

- 在项目根目录打开终端，激活 Python 环境。
- 确认 `python scripts/run.py --help` 可用。
- 生成/更新参考索引：

```bash
python scripts/build_reference_docs.py
```

### 阶段 1：检查输入

```bash
python -m biopipe inspect "<绝对路径>" --json
```

记录：

- Reader 名称、格式、压缩方式；
- shape、dims、labels；
- 缺失值、数值范围；
- 重复标签、编码列、样本/特征数量；
- 是否存在配套文件（例如 MTX 的 barcodes/features、PLINK 的 bed/bim/fam、BGEN 的索引）。

如果 Reader 需要参数（例如 CSV 的 `--sep`），用：

```bash
python -m biopipe inspect "<绝对路径>" --reader csv --arg sep="\t" --json
```

### 阶段 2：明确目标

- 用户给了目标：LLM 复述目标、成功标准、数据限制。
- 用户没给目标：LLM 给出 1–3 个候选分析，每个写明：
  - 能回答的问题；
  - 需要的 Reader/算子；
  - 前提和假设；
  - 不能回答的问题；
  - 预计输出（表格/图片）。
- 用户选定一个后，才写 YAML。

### 阶段 3：选 Reader/算子

1. 先读 `docs/reference/operator_index.json` 和 `reader_index.json`。
2. 只打开 3–8 个候选算子的页面。
3. 页面信息不足或涉及数值边界时，读页面链接的源码和至少一个测试。
4. 检查输入/输出契约和维度是否衔接；不要凭算子名字猜。

### 阶段 4：写 `task.yaml`

```yaml
name: <slug>

sources:
  counts:
    path: input/counts.csv
    dims: [gene, sample]
    labels:
      gene: {sample: 0}
      sample: builtin

steps:
  - name: filter_min
    inputs: [counts]
    params:
      dim: gene
      min_value: 10
      min_samples: 3
      output: filtered

  - name: normalize
    inputs: [filtered]
    params:
      method: cpm
      dim: sample
      output: normalized
```

规则：

- 只使用已注册 Reader/算子；
- 不写 `_input_names`（引擎内部键，写了也会被剥离）；
- 不写未知参数；
- 输出名唯一；
- 图片文件名只能是文件名，不能带目录/盘符；
- `output` 是上下文键，不是文件路径。

### 阶段 5：写 `ANALYSIS.md`

必须包含：

1. 数据来源、绝对路径、落到 `input/` 的相对路径；
2. 数据概况：shape、dims、labels、缺失、编码；
3. 分析目标与成功标准；
4. 步骤表：算子、参数、输入→输出、为什么；
5. 每张图：文件名、画的是什么、轴/颜色/阈值、怎么读、不能说明什么；
6. 假设、限制、过滤掉的数量；
7. 复现命令。

模板见 `docs/templates/ANALYSIS.md`。

### 阶段 6：静态校验

```bash
python scripts/run.py tasks/<slug> --check
```

必须看到 `"ok": true` 和 `CHECK OK`。它会检查：

- 输入文件是否存在；
- Reader 是否可识别、Reader 参数是否合法；
- 算子是否存在、参数是否严格合法；
- 输入是否在前序步骤产生；
- 输出名是否重复；
- 图片文件名是否安全。

`--check` 不执行分析。校验失败时不要运行，先修 YAML。

### 阶段 7：用户导入/执行

任选其一：

**命令行：**

```bash
python scripts/run.py tasks/<slug>
```

**Studio：**

- 打开 Studio；
- 使用“导入 YAML / JSON”，选择 `tasks/<slug>/task.yaml`；
- 检查源文件路径和算子参数；
- 运行。

### 阶段 8：解释结果

LLM 必须：

- 读运行日志和 `ANALYSIS.md`；
- 说明实际执行了什么、过滤了多少；
- 按“图片说明”解释每张图；
- 区分探索性结果和确证性结论；
- 不把相关性写成因果，不把未校正 P 值写成显著结论。

## 5. 图片处理规范

平台只负责生成 PNG 和 report，不负责“看懂图片”；识图是 LLM 自身能力，不是 BioPipe 功能。

每张图至少写：

| 项目 | 要求 |
|---|---|
| 文件名 | `filename` 参数值 |
| 画的是什么 | 行/列、分组、统计量 |
| 轴 | 单位、范围、是否对数 |
| 颜色 | 颜色映射、中心值、缺失颜色 |
| 阈值 | 显著性线、倍数阈值、样本量线 |
| 怎么读 | 高/低、聚集、离群点的含义 |
| 不能说明什么 | 因果、机制、未测变量、多重校正后的结论 |

## 6. 失败处理

| 现象 | 优先检查 |
|---|---|
| `file not found` | 绝对路径、`input/`、任务目录 |
| `No reader for extension` | 文件后缀、Reader 索引、是否需要 `--reader` |
| `Unknown operator` | 算子名拼写、索引版本、是否需要刷新 |
| `Additional properties are not allowed` | 是否写了未知参数或 `_input_names` |
| `input ... not produced` | `inputs` 名称、前序 `output` |
| `contract incompatible` | 维度/数值/编码是否匹配 |
| `heatmap ... max_cells` | 矩阵太大；用 `select/top_n`、子集或先聚合 |
| 图片 OOM | 降低 `max_pixels`、减少行列、关闭聚类 |

## 7. 验收清单

- [ ] 用户提供了绝对路径；
- [ ] LLM 验证并复述了绝对路径；
- [ ] 数据已放到 `tasks/<slug>/input/`；
- [ ] `task.yaml` 使用相对路径；
- [ ] 每个算子都有契约依据，不是猜的；
- [ ] 没有 `_input_names` 或未知参数；
- [ ] `--check` 返回 `ok: true`；
- [ ] `ANALYSIS.md` 有逐步理由和图片说明；
- [ ] 用户已审阅 YAML 和 ANALYSIS；
- [ ] 运行后检查了日志和过滤数量；
- [ ] 结论没有超出数据/设计能支持的范围。
