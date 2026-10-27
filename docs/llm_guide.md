# LLM 路线搭建手册

本手册给具备终端/文件读取能力的 LLM。目标：**不通读仓库**，只读 `docs/README.md`、`docs/architecture.md`、`docs/route_sop.md`、机器索引、少量算子页和必要的源码/测试，就能为用户搭建可校验的 BioPipe 任务。

## 1. 阅读顺序（严格遵守）

1. `docs/README.md` 与 `docs/architecture.md`（入口和仓库结构）；
2. `docs/route_sop.md`（流程和验收）；
3. `docs/reference/operator_index.json` / `reader_index.json`（先筛选候选）；
4. 只打开候选 Reader/算子页面（3–8 个）；
5. 页面链接的源码/测试，仅在语义、边界、参数不确定时阅读；
6. `docs/templates/ANALYSIS.md`；
7. 本手册的“输出格式”。

不要一开始递归读取整个 `src/`；不要根据算子名猜行为。

## 2. 输入检查

用户必须给**绝对路径**。你必须：

- 复述路径；
- 验证存在、是文件、可读；
- 运行：

```bash
python -m biopipe inspect "<绝对路径>" --json
```

如需 Reader 参数：

```bash
python -m biopipe inspect "<绝对路径>" --reader csv --arg sep="\t" --json
```

记录并在 `ANALYSIS.md` 中写出：

- Reader、格式、压缩；
- shape、dims、labels、缺失、范围；
- 重复标签和编码；
- 配套文件是否齐全。

绝不能编造列名、样本数、分组或数值。

## 3. 选 Reader

从 `reader_index.json` 选，检查：

- `extensions` / `file_input`；
- `parameters_schema`；
- `output_contract`；
- 页面里的格式边界和配套文件要求。

如果扩展名有歧义（例如 `.txt` 实际是 tab 分隔表），在 YAML 的 `args.reader` 指定 Reader，并在 `args` 中给出必要参数。`reader` 不是 Reader 的参数，而是路由选择器，`--check` 会正确剥离它。

## 4. 选算子

从 `operator_index.json` 选，检查：

- 输入 arity 和 contracts；
- 输出 mode / dims；
- 参数 schema（严格；不能写未知参数）；
- 页面里的算法规则/边界；
- 源码/测试链接。

如果两个算子名字相近，读两页的“Processing rules”再决定。不要用未注册算子。

## 5. 用户没有目标时

给出 1–3 个候选，不要直接写 YAML。每个候选包含：

```text
建议：<一句话>
能回答：<问题>
需要：<Reader/算子链>
前提：<数据要求/假设>
输出：<表格/图片>
局限：<不能回答什么>
```

让用户选一个；若用户说“你决定”，选最保守、最容易验证的方案，并在 ANALYSIS 中写明理由。

## 6. 写 YAML

必须：

- 任务目录 `tasks/<slug>/`；
- 数据在 `input/`；
- YAML 用相对路径；
- 输出名唯一；
- 图片文件名只写文件名；
- 不写 `_input_names`（内部键，写了会被剥离）；
- 不写 schema 外参数。

命名：

- 用户给定名字：用用户的；
- 用户让 LLM 命名：`data_topic_goal`，只含字母/数字/下划线/短横线；
- 在 ANALYSIS 里解释命名理由。

## 7. 写 ANALYSIS.md

模板：`docs/templates/ANALYSIS.md`。必须包含：

- 绝对路径 → `input/` 相对路径 → 为什么；
- 数据概况；
- 目标/成功标准；
- 步骤表（算子、参数、输入→输出、为什么）；
- 图片说明（轴/颜色/阈值/怎么读/不能说明什么）；
- 假设/限制/过滤数量；
- 复现命令。

不要写“按常规流程”“适当过滤”这类无法复现的话；写具体值和理由。

## 8. 静态校验

```bash
python scripts/run.py tasks/<slug> --check
```

必须通过。失败时按错误逐项修：

- 路径：绝对路径/`input/`；
- Reader：扩展名/`reader`/参数；
- 参数：schema 类型/范围/未知键；
- 输入：是否由前序步骤产生；
- 输出：重名；
- 图片名：目录/盘符。

不要把 `--check` 失败的任务交给用户运行。

## 9. 解释要求

对每一步回答：

1. 这一步解决什么问题？
2. 为什么选这个算子，而不是相邻算子？
3. 参数值从哪来（数据分布/文献/默认值/用户要求）？
4. 输入输出维度如何衔接？
5. 失败/空结果意味着什么？
6. 这一步不能证明什么？

图片额外回答：

- 画的是什么；
- 轴/单位/对数；
- 颜色/阈值；
- 主要模式；
- 样本量/多重比较/批次等限制；
- 不能从图中得出的结论。

## 10. 严格禁止

- 编造数据、列名、样本量、P 值；
- 把绝对路径写进 YAML（除非用户明确要求单机不可移动）；
- 使用未注册 Reader/算子；
- 写 `_input_names` 或 schema 外参数；
- 未跑 `--check` 就让用户运行；
- 把探索性图说成确证性结论；
- 声称平台能自动识图（识图是 LLM 自身能力，不是 BioPipe 功能）。

## 11. 输出格式（给用户）

```text
## 数据
- 绝对路径：
- 落到：
- Reader/格式/shape/dims/labels：

## 方案
- 目标：
- 步骤表：
- 为什么这样设计：

## 文件
- task.yaml：
- ANALYSIS.md：

## 校验
- 命令：
- 结果：

## 运行
- 命令/Studio 导入步骤：

## 图片
- 文件、含义、读法、限制：
```

固定提示词模板见 `docs/prompts/route_architect.md`。
