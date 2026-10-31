# BioPipe Protocol Suite v2

状态：Active（2026-10-23 起按维护者授权执行；决策 1=B，其余按推荐/最优判断；底层数据协议如需再改，先确认）  
适用范围：`src/core`、`src/reader`、`src/task`、`src/web`、`biopipe_sdk`、`biopipe`、`routes/`、桌面端  
原则：先协议、后实现；先测试、后优化。扩展遵循同一协议。

> 入口：[文档首页](README.md) / [架构总览](architecture.md)。

> 阅读约定：**MUST** 为硬性要求，**SHOULD** 为默认要求（偏离需写明理由），**MAY** 为可选。
> 【现状】表示当前代码已基本满足；【收紧】表示后续优化必须补齐；【新增】表示本协议新增的约定。
> 本文件是总协议；`docs/operator_protocol.md`、`docs/package_protocol.md` 等作为实现细节文档，冲突时以本文件为准。

---

## 0. 目标与非目标

### 0.1 目标

1. **Reader 准确**：对标准格式的列、坐标、缺失、压缩、编码、方向有明确、可测试的定义；不静默猜测。
2. **算子准确**：每个算子有唯一、可复现的数学定义、输入/输出契约、缺失值策略和独立参考测试。
3. **桌面简单**：常用操作路径短、默认值合理、错误能直接指出字段和修法；高级选项渐进展开。
4. **扩展独立**：新 Reader/算子只依赖 `biopipe_sdk` 和公开协议，不修改引擎、不改 JSON 索引、不依赖私有路径。

### 0.2 非目标

- 不把 BioPipe 变成 FASTQ/BAM/mzML/CZI 等原始数据的前端；输入边界见 `docs/input_formats.md`。
- 不在本协议周期内新增 Reader 或算子；只修正现有实现、契约、参数和文档。
- 不承诺“任意算法都能自动流式/自动省内存”；只承诺如实声明能力并在边界处失败。

---

## 1. P1 — 核心数据协议（Form）

### 1.1 结构

`Form` 是引擎唯一的内存数据容器：

```python
Form(
    data: np.ndarray,          # 数值张量，不允许 object dtype
    dims: list[str],           # 有序、唯一、非空
    labels: dict[str, dict[str, int]],
    info: dict,
    axis_info: dict[str, list[str]],
)
```

### 1.2 硬性规则

- **MUST**：`len(dims) == data.ndim`；`dims` 不含重复项。
- **MUST**：每个 dim 都有 labels；labels 的值是 `int`，覆盖 `0..size-1` 的每个位置，且一个位置只能有一个 label。
- **MUST**：`labels` 是跨算子对齐的身份键。除明确的“按位置”算子（如 `transpose`、`pivot` 的轴展开）外，不得按行号硬拼不同 Form。
- **MUST**：`axis_info[dim]` 中列出的每个 `info` 字段，必须是长度等于该轴大小的 1-D list/array；同一字段不得同时绑定两个轴。
- **MUST**：`subset_axis` 必须同时裁剪 data、labels 和 `axis_info` 声明的字段；不得只裁 data。
- **MUST**：算子不得原地修改输入 Form 的 data/info/labels；分支可能共享同一输入。返回新 Form。
- **MUST**：`Form.validate()` 在任何输出进入 Context 前执行；失败必须抛出明确错误。

### 1.3 数值与精度

- **MUST**：不允许静默的有损 dtype 转换。整数坐标、计数、长度在转换后必须仍能精确还原。
- **MUST**：基因组坐标（BED/GFF/GTF/CSV/Parquet 的 start/end/pos，区间算子的 start/end/length）超过 `2**24` 时使用 float64；仅当 float32 转换逐值精确时才允许压缩为 float32（`src/core/numeric.py::compact_numeric`）。
- **MUST**：普通表达矩阵、计数矩阵可继续使用 float32；不得为了统一而把所有数据强制成 float64。
- **SHOULD**：算子内部统计使用 float64 累加；输出按“无损优先”压缩。
- **MUST**：`missing_code` 默认 `np.nan`；若使用有限哨兵（如 `-9`），必须在 `info["missing_code"]` 声明，并在所有算子中一致处理。

### 1.4 语义字段

以下字段是约定，不是强制枚举；Reader 必须如实填写，算子必须按声明消费：

| 字段 | 含义 |
|---|---|
| `missing_code` | 缺失标记，通常 `np.nan` |
| `representation` | `hard_call` / `dosage` / `counts` / `scores` / `comparison` / `sequence_codes` / `regression` / `clusters` / `distance` / 领域自定义 |
| `ploidy` | 基因型倍性；`hard_call`/`dosage` 必填 |
| `encoders` | `{dim: {label: encoder}}`，编码列的逆变换 |
| `alphabet` / `alphabet_map` | 序列字母表与代码映射 |
| `chrom` / `pos` | 轴平行坐标，必须进入 `axis_info` |

---

## 2. P2 — Reader 协议

### 2.1 职责

Reader 只负责把一种“分析就绪”的文件/文件组读成 Form。**MUST NOT** 推断文件之外的生物学含义，**MUST NOT** 把某个流程的中间格式伪装成通用格式。

### 2.2 必备声明

每个 Reader **MUST** 在源码类上声明：

| 声明 | 要求 |
|---|---|
| `name` | 稳定 ID；内置可用类名，外部插件必须带命名空间 |
| `version` | 语义版本 |
| `extensions` | 小写后缀列表 |
| `parameters_schema` | 严格 JSON Schema；`additionalProperties: false`（全部内置 Reader 已补齐） |
| `output_contract` | `reader_contract(...)` 或等价 port 声明 |
| `read(path, dims, labels, **args) -> Form` | 唯一读取入口 |
| `file_input` | 文件选择器提示：`dims`、`labels`、`compression`、`companions` |
| `dependencies` / `dependency_imports` | 字面量列表；可选解析器依赖 |
| `requires_siblings` / `excludes_siblings` | 同 basename 的必需/排除伴随文件 |
| `handles_compression` | 仅当 Reader 自己解析压缩文件时为 True |

**MUST**：`file_input`、`extensions`、`requires_siblings`、`excludes_siblings`、`handles_compression` 与运行时路由使用同一份声明，不能各写一套。

### 2.3 路由规则

- **MUST**：`pick_reader` 对同一路径必须返回唯一 Reader；多匹配/零匹配必须报错并列出候选/已知扩展名。
- **MUST**：压缩外层后缀（`.gz/.bz2/.xz`）的处理只有两种：Reader 自己处理（`handles_compression=True` 且 `file_input.compression` 声明），或框架解压到临时目录后交给 Reader。
- **MUST**：解压临时文件保留原 basename 和主扩展名；同目录 sibling 查找不能因解压而失效；解析器生成的索引文件随临时目录清理。
- **MUST**：`.bed` 必须区分 PLINK 二进制（有 `.bim/.fam`）与 UCSC BED；不得靠改后缀绕过。

### 2.4 标准格式语义

每个 Reader **MUST** 在模块 docstring 中写明：

1. 坐标基准（0-based 半开 / 1-based 闭区间）；
2. 轴方向（如 variant × sample、gene × cell、record × field）；
3. 缺失表示（`.`、`NA`、`-9`、NaN）；
4. 标签来源（header、ID 列、行号、barcode）；
5. 重复值、空行、注释、header 的处理；
6. 压缩与伴随文件规则；
7. dtype/精度策略。

#### 2.4.1 文本表（CSV/TSV/TXT/Parquet/BED/GFF3/GTF）

- **MUST**：读取行后使用 `rstrip("\r\n")`，不是只去 `\n`。
- **MUST**：空行用 `if not line.strip()` 跳过。
- **MUST**：`track`/`browser`/`#` 注释按“首个 token”匹配，不用 `startswith("track")` 误伤 `tracking` 数据行。
- **MUST**：BED 优先按 tab 切分；只有整行无 tab 时才回退任意空白，保留 `name` 中的空格。
- **MUST**：GFF3/GTF 在 `##FASTA` 处停止，不把内嵌序列当记录。
- **MUST**：GFF3 允许 `##` 指令与 `#` 注释；GTF 允许 `#` 注释；两者都要求 9 列。
- **MUST**：CSV/TSV 的 `columns`、`info_columns`、label 列索引都相对于原始文件列序；列选择后仍保持该语义。
- **SHOULD**：重复列名、空 header、越界 label 列、列数不一致必须报错，不能静默取第一列。

#### 2.4.2 序列（FASTA）

- **MUST**：允许空记录（连续 `>`），并保持 id 与 sequence 一一对应；首个 `>` 之前出现序列必须报错。
- **MUST**：大小写不敏感；`U` 与 `T` 映射到同一代码；`N`/未知字符有明确代码。
- **MUST**：字母表推断必须区分 DNA/RNA/protein；含 `X/B/Z/J/O/*` 的序列不得误判为 DNA。
- **SHOULD**：不同长度序列用 NaN 右侧填充，`labels["position"]` 覆盖 0..max_len-1。

#### 2.4.3 基因型（VCF/PLINK/BGEN）

- **MUST**：VCF 只输出 hard call 的 ALT 计数；多等位拆行；`./.`、`0/.` 等缺失记 NaN；混合倍性报错；样本数/allele 索引越界报错。
- **MUST**：PLINK1/PLINK2 只接受完整三元组；样本/变异数与矩阵一致；缺失记 NaN；倍性固定 2。
- **MUST**：BGEN 只接受双等位二倍体；三列概率和必须为 1；复杂/非二倍体报错；dosage = P(AB)+2P(BB)。
- **MUST**：`chrom`/`pos` 进入 `axis_info`（VCF/PLINK 已做；BGEN 待补）。

#### 2.4.4 单细胞（H5AD/MTX/10x H5）

- **MUST**：H5AD 的 `obs`/`var` 索引长度与矩阵轴一致；`layer` 不存在时报错；稀疏矩阵 densify 前声明内存。
- **MUST**：MTX 只接受 10x MEX 布局；`features.tsv`/`genes.tsv`、`barcodes.tsv` 必须存在；1-based 索引；重复条目求和；截断/超量报错。
- **MUST**：10x H5 校验 `matrix/{shape,data,indices,indptr,barcodes,features}`；`feature_type` 过滤后标签与 `feature_types`/`genome` 同步。

#### 2.4.5 功能注释（GAF）

- **MUST**：GAF 2.2 固定 17 列；`!` 注释跳过；`db_object_synonym` 进入 info 并声明轴平行；空字段保留。
- **MUST**：gzip 按 magic 或后缀识别；不得把 `.GZ` 当普通文本。

### 2.5 磁盘读取协议

大文件 **SHOULD** 实现 `dense-writer-v1`：

- `supports_disk_read = True`、`disk_protocol = "dense-writer-v1"`；
- `probe()` 只读 header/index，返回 `file_bytes`、`shape`（2D）、`dtype`、`dense_bytes`、`preparation_bytes`；
- `read_to_disk()` 用提供的 writer 分块写入，返回 metadata；
- **MUST**：`dense_bytes == product(shape) * dtype.itemsize`；`preparation_bytes` 包含临时磁盘；
- **MUST**：不得先收齐所有 chunk 再拼接；不得绕过 writer 自行分配整矩阵；
- **MUST**：普通读取与磁盘读取的数值/标签/info 必须逐值一致，并有测试。

### 2.6 错误

- **MUST**：抛出 `ReaderError`，消息包含：文件、行/列（可得时）、期望值、实际值。
- **MUST NOT**：对无法识别的必填字段静默填默认值；对不支持的压缩/格式静默降级。
- **SHOULD**：错误消息中包含下一步修法（例如“先转换为 VCF”“检查 barcodes 行数”）。

### 2.7 Reader 验收

每个 Reader **MUST** 至少覆盖：

1. 最小合法文件；
2. 标准格式边界（CRLF、空行、注释、header、重复标签、空记录）；
3. 缺失/越界/截断/错误列数；
4. 压缩与未压缩结果一致；
5. 普通读取 vs 磁盘读取一致（如支持）；
6. 至少一份真实公开数据与外部数值参考（按 `input_formats.md` 的输入说明）。

---

## 3. P3 — Operator 协议

### 3.1 职责

算子只做一件事，并用唯一的数学定义描述它。一个算子 **MUST NOT** 通过大量 `method` 分支拼接多个不相关算法；ML 模型必须一模型一算子。

### 3.2 必备声明

| 声明 | 要求 |
|---|---|
| `name` / `version` | 稳定 ID；语义版本 |
| `title` / `category` / `icon` | 面向用户的展示信息 |
| `inputs_arity` | 0–20 或 `"*"` |
| `input_contracts` | 每个端口一条；`"*"` 一条重复契约 |
| `output_contract` | 明确的 mode；Form 输出或 report |
| `parameters_schema` | 严格 JSON Schema；所有公开参数在此声明 |
| `output_parameter` / `outputs` | 动态 `output` 或固定输出名 |
| `estimate_memory` | 临时 workspace 与输出字节数；不能返回负数 |
| `dependencies` / `dependency_imports` | 字面量列表 |

### 3.3 行为规则

- **MUST**：不修改输入 Form；返回新 Form。
- **MUST**：轴操作走 `subset_axis`/metadata helper，不直接切 data。
- **MUST**：输出必须通过 `Form.validate()` 和输出契约校验。
- **MUST**：缺失值策略明确（传播 NaN / 删除 / 填充），并在 docstring 与测试中说明。
- **MUST**：输入按 label 对齐；若按位置对齐，必须在参数/契约中显式声明。
- **MUST**：report 算子不得注册 Form；Form 算子必须注册声明的输出。
- **MUST**：绘图算子输出文件使用相对路径，图由 `_plot_helpers` 统一保存；report 不嵌入完整矩阵。
- **MUST**：失败抛 `StepError`，消息包含算子名、参数、期望/实际。

### 3.4 参数协议（易用性核心）

- **MUST**：参数名使用 `snake_case`；维度用 `dim`/`*_dim`，输出用 `output`，标签用 `*_label`；不得新增 `axis` 与 `dim` 混用。
- **MUST**：每个参数有 `title`；非显而易见的参数有 `description`；单位写入 `description` 或 `x-ui-unit`。
- **MUST**：能用安全默认值的参数必须给 `default`；只有确实无法默认的参数才 `required`。
- **MUST**：枚举参数使用 `enum`；数值参数有 `minimum`/`maximum`。
- **MUST**：`additionalProperties: false`。拼错参数必须报错，不得静默忽略。
- **SHOULD**：参数分“常用/高级”。建议在 schema 中增加：
  ```json
  {"x-ui-group": "basic" | "advanced", "x-ui-order": 10, "x-ui-unit": "bp"}
  ```
  桌面端默认只展示 `basic`，`advanced` 折叠。
- **MUST**：不得暴露仅内部使用的参数（如 `_input_names`）；`output` 由引擎单独处理。

### 3.5 输出契约

输出 mode 必须是以下之一（与现有实现一致）：

`unknown` / `declare` / `project` / `choose` / `passthrough` / `transform` / `subset` / `select` / `drop` / `rename` / `transpose` / `concat` / `attach` / `report` / `none` / `pca` / `regress` / `correction` / `compare_groups` / `cox_regression` / `logrank_test`

- **MUST**：`declare` 的 schema 与实际输出一致；
- **MUST**：`transform` 清除旧的 genotype/representation/encoder 语义；
- **MUST**：`project` 删除轴时同步删除其 `axis_info` 和 encoders；
- **MUST**：`concat` 按 label 对齐，冲突时报错，不静默丢列。

### 3.6 算子验收

每个算子 **MUST** 至少覆盖：

1. 手工可算的小例子（数值逐项断言）；
2. 独立实现/外部参考或数学不变量（不能只查 shape）；
3. NaN 与有限缺失哨兵；
4. 错误维度/错误 representation/越界参数；
5. metadata 传播（labels、axis_info、encoders、missing_code）；
6. 输出契约与参数默认值；
7. 内存估计与（如声明）流式/全量一致性。

---

## 4. P4 — 契约与校验协议

### 4.1 端口契约

`port(...)` 支持：

- `ndim`、`numeric`；
- `dims`（可绑定 `param(...)`）；
- `labels`/`labels_any`/`labels_axis`；
- `info` 规则：`type`、`optional`、`const`、`enum`、`min`、`items`；
- `parallel`（轴注释）；
- `values`：`hard_call`/`dosage`/`allele_count`/`pvalue`。

**MUST**：端口契约只描述结构与语义保证，不检查具体生物学含义；不要硬编码 `representation == "dosage"` 除非该值就是接口约定。

### 4.2 三态

- `compatible`：声明层面满足；
- `incompatible`：已知冲突，画布拒绝连线/执行前失败；
- `unknown`：需要运行时确认，允许保存但在执行边界校验。

**MUST**：未知不等于通过；执行时必须对真实数据再校验一次。

### 4.3 校验边界

**MUST**：Reader 输出、每个算子的每个输入、每个新注册输出都校验；流式算子对 metadata 和每个 block 校验；校验掩码有界（≤65,536 元素/块）。

---

## 5. P5 — 注册表与包协议

### 5.1 单一事实来源

- **MUST**：Reader/算子参数、契约、版本、依赖只在源码类声明。
- **MUST**：`biopipe/builtin_packages.json` 与 `src/web/builtin_routes.json` 只由 `python -m biopipe registry build` 生成，不手改。
- **MUST**：源码与生成物不一致时 `registry check` 非零退出。
- **MUST**：生成失败不覆盖旧索引；写入原子；维护锁串行化。

### 5.2 包与所有权

- 6 个内置 provider：`biopipe-readers`、`biopipe-core`、`biopipe-genetics`、`biopipe-expression`、`biopipe-plots`、`biopipe-microbiome`。
- **MUST**：ID 全局唯一；已归属的 ID 不得移到另一个 provider；外部插件必须命名空间化（`lab.foo`）。
- **MUST**：包版本、算子版本、实现哈希、dependencies 进入 descriptor；运行中的 job 保留 pin。

### 5.3 扩展三条路径

1. **单文件 drop-in**：`*.py` + 刷新算子库；适合自包含扩展；
2. **wheel 插件**：`plugin init/check/test/build/install`；适合多文件、依赖、分发；
3. **route**：`routes/<name>/task.yaml` + 可选 `route.json`；保存/注册后成为可复用节点。

**MUST**：三条路径都走同一 descriptor 校验、同一依赖检查、同一 job pin；不得有“只有 GUI 能用”的旁路。

---

## 6. P6 — 路线与图协议

- **MUST**：`Graph` 节点类型为 `source`/`operator`/`route`；边有明确 `sourceHandle`/`targetHandle`，输入顺序由端口决定。
- **MUST**：编译时拒绝环、悬空边、重复输出名、错误 arity、已知不兼容连线；输出确定性的拓扑序。
- **MUST**：保存 ≠ 注册。保存产生 route 快照；注册后才进入算子库；版本递增可审计。
- **MUST**：route 节点嵌入完整快照 + `plugin_lock`；展开时内部 ID/输出名/图文件名命名空间化；嵌套上限 6 层、1000 节点、5000 边。
- **MUST**：route 接口的 inputs/outputs 契约参与静态校验；占位 source 不读取原文件。

---

## 7. P7 — 桌面端协议（简单易用）

### 7.1 主路径

新用户完成一次分析 **SHOULD** 不超过 3 个主要动作：

1. 选择数据（或打开 demo）；
2. 添加算子/路线并连线；
3. 运行。

### 7.2 输入面板

- **MUST**：显示识别到的 Reader、形状、维度名、标签来源、缺失值策略、压缩状态。
- **MUST**：Reader 参数按 schema 生成；常用参数默认展开，高级参数折叠。
- **MUST**：文件组（PLINK/MTX）明确列出缺失的伴随文件及修法。
- **MUST**：上传只代表传输完成；解析结果与错误在输入预览/运行前可见。

### 7.3 参数面板

- **MUST**：只展示 `basic` 参数；高级参数一键展开；搜索可定位参数。
- **MUST**：字段级校验在失焦/运行前显示；错误直接指出字段名和期望。
- **MUST**：不出现没有 title 的参数；不出现“A 或 B”的模糊说明。
- **MUST**：修改参数立即使旧结果标记 stale；不得静默复用旧结果。

### 7.4 画布与运行

- **MUST**：不兼容连线在连线时阻止并说明原因；`unknown` 允许保存但运行前校验。
- **MUST**：运行只有一个主按钮；预算、进度、取消、错误在同一面板可见。
- **MUST**：结果面板展示真实 figures、表格预览、下载；不把完整张量塞进 UI。
- **MUST**：运行中禁止改图；完成后明确“结果是否过期”。

### 7.5 错误与可访问性

- **MUST**：用户错误用中文短句 + 字段定位 + 修法；内部 traceback 进日志，不直接铺在画布。
- **MUST**：键盘可达；焦点可见；支持 reduced motion；浅色/深色主题对比度达标。
- **SHOULD**：空状态给一个明确入口（打开 demo/选择数据），不放大段说明。

### 7.6 桌面验收清单

- [ ] 新用户从空画布到 demo 运行 ≤ 3 个主要动作。
- [ ] 任意算子参数面板中，必填项 ≤ 2 且都有默认值或明确示例。
- [ ] 所有参数有 title；高级参数默认折叠。
- [ ] 任一格式错误能在输入面板定位到文件/字段。
- [ ] 不兼容连线在连线时被拒绝并解释。
- [ ] 运行结果可下载，失败有可复制的诊断。
- [ ] 没有“原始 JSON”作为常规路径；仅高级模式提供。

---

## 8. P8 — 扩展独立性协议

### 8.1 只依赖公开 SDK

外部扩展 **MUST** 只 import：

- `biopipe_sdk`（`Operator`、`Step`、`Reader`、`Form`、`port`、`param`、`reader_contract`、`project_metadata`、`run_operator` 等）；
- 标准库与声明的第三方依赖。

**MUST NOT** import `src.*` 私有模块、修改引擎文件、读取 profile 内部 JSON、依赖开发者路径。

### 8.2 身份与隔离

- **MUST**：外部 ID 带命名空间（`lab.scale`）；不得覆盖内置 ID。
- **MUST**：一个分发一个 provider；不得跨插件 import 私有代码；共享代码发布为独立依赖包。
- **MUST**：每个扩展声明 `parameters_schema`、`output_contract`、`version`、`dependencies`；缺一不可。
- **MUST**：依赖冲突走私有目录 + 子进程，同一 Python；不得 monkeypatch 全局。

### 8.3 扩展生命周期

- **MUST**：安装/刷新是事务性的；失败保留上一代 registry；运行中的 job 不受影响。
- **MUST**：保存的图/job 保留插件 pin；升级/卸载不改变历史。
- **MUST**：插件测试可在仓库外独立运行（`biopipe plugin test` 或 `run_operator`）。

### 8.4 允许/禁止矩阵

| 动作 | 外部扩展 | 内置维护者 |
|---|---|---|
| 新增 Reader/算子 | 允许（走三条路径） | 允许（+ registry build） |
| 修改 `src/core` | 禁止 | 仅维护者，需全量测试 |
| 手改 `builtin_packages.json` | 禁止 | 禁止（生成物） |
| 依赖 `src.*` | 禁止 | 不推荐；内置也应只用 SDK |
| 声明 stream/disk | 允许，需真实实现 | 允许，需真实实现 |
| 覆盖内置 ID | 禁止 | 仅同 provider 的兼容替换 |

---

## 9. P9 — 测试与验证协议

### 9.1 四层测试

1. **单元/契约测试**（pytest）：Form、contracts、reader/operator 边界；
2. **算子 demo 自测**（`tasks/*_demo/test_*.py`）：手工可算 + 独立参考；
3. **主题验证脚本**（`tasks/verify_*.py`）：外部权威数值/独立实现/数学不变量；
4. **端到端**（route demo/Studio job）：真实数据、完整 DAG、输出产物。

### 9.2 硬性门禁

- **MUST**：`python -m pytest -q` 全绿（允许有明确理由的 skip，不允许无理由 skip）。
- **MUST**：`python -m biopipe registry check` 干净。
- **MUST**：`ruff check --select F` 为 0；`compileall` 通过。
- **MUST**：14 个 `verify_*.py` 全过。
- **MUST**：49 个 demo 自测全过。
- **SHOULD**：CI 构建 frontend 并运行 `npm test`/`npm run build`；本机没有 dist 时桌面测试必须显式 skip。
- **MUST**：测试不得依赖网络；真实数据通过 `download.sh` 获取，fixture 进仓库要小且可复现。

### 9.3 覆盖矩阵

每个 Reader/算子 **MUST** 在 `docs/sop_matrix.md` 或扩展文档中有测试映射：文件、覆盖点、未覆盖分支。未覆盖分支要写明原因（如 plot 无数值契约、logit 分支未验）。

---

## 10. P10 — 文档与发布协议

- **MUST**：README 只写“当前源码树”的能力；历史 release notes 保留发布时数字，不回填。
- **MUST**：算子/Reader 数量以生成注册表为准；文档中的数字必须可被 `registry check` 验证。
- **MUST**：每个协议/扩展页只保留一个权威版本；重复说明改为链接。
- **MUST**：新增/修改 Reader/算子时同步：docstring、参数说明、测试、`docs/` 对应页。
- **SHOULD**：每个版本附“已验证/未验证”声明，禁止把“测试通过”写成“数学上完备”。

---

## 11. P11 — 错误与诊断协议

- **MUST**：错误类型：`ReaderError`、`ManifestError`、`StepError`、`ValidationError`、`ContextError`；不要用裸 `Exception` 作为用户错误。
- **MUST**：结构化 event 写入 `events.jsonl`；用户可见信息与内部 traceback 分离。
- **MUST**：CLI stdout 只输出 JSON；诊断进 stderr；退出码区分 revision conflict / not connected / invalid request。
- **MUST**：失败不产生“半成品结果”被下游误用；失败 step 不注册输出。
- **SHOULD**：错误消息模板：`<operator/reader>: <what>; expected <...>, got <...>; <next action>`。

---

## 12. P12 — 资源与性能协议

- **MUST**：预算在运行前固定；不中途扫描全机内存。
- **MUST**：每个算子声明 `estimate_memory`；流式/磁盘能力必须真实实现，不能只设 flag。
- **MUST**：memory_report 如实记录估算、RSS 峰值、spill、artifact；声明“无硬性 RSS 保证”。
- **MUST**：大数据路径优先磁盘/分块；全量 densify 必须显式声明内存需求。
- **SHOULD**：输出 dtype 按“无损优先”压缩，避免无谓 double 内存。

---

## 13. P13 — 当前实现与协议的差距

| 协议 | 现状 | 需要补齐 |
|---|---|---|
| P1 Form | 基本满足 | 统一 dtype 精度测试；更多算子输出精度审计 |
| P2 Reader | 85 个已声明 schema；title/category/description/platforms 已进入 SDK；精度/FASTA/GFF/BED 已修 | Reader 分类仍全为 Data；每个 Reader 的格式语义表与真实数据覆盖；BGEN 坐标 |
| P3 Operator | 395 个严格 schema；30 个 legacy 已迁移；category 已归一为 6 类并有 catalog integrity 测试 | 仍需逐个审计未覆盖的数学分支；图标未全覆盖 |
| P4 Contract | 三态 + 运行时校验已实现；Step/Reader 基类强制严格参数 | 更多负例覆盖；输出 mode 逐项测试 |
| P5 Registry | 生成物干净；source 为唯一参数真源；`operator_ui.json` 已只保留展示元数据（1485→258 行） | 无 |
| P6 Route | 21 条；编译/展开/注册已实现 | 21 条 route 均有仓库 fixture 并实际执行；7 条 0.8/0.9 新 route 另有独立 smoke test |
| P7 Desktop | 参数 title/group/unit 由 schema 提供；算子/Reader 功能预览、Reader 库、平台徽标已接入 | 图标仍部分回退；`x-ui-*`、错误定位未接入 |
| P8 Extension | SDK/wheel/drop-in/route 已实现 | 外部插件测试矩阵与私有 import 扫描 |
| P9 Testing | 29 个独立 SOP + 0.18 全量 606 pytest + 0.19 增量 42 + 0.20 增量 12 + 0.21 增量 10 + 0.22 增量门 24 + 0.23 新增 5 / 增量门 21 + 0.24 新增 5 / 增量门 21 + 0.25 新增 6 / 增量门 22 + 0.26 新增 5 / 增量门 21 + 0.27 新增 6 / 增量门 22 + 0.28 新增 5 / 增量门 22 + 0.29 新增 5 / 增量门 22 + 0.30 新增 5 / 增量门 21 + 0.31 新增 4 / 增量门 20 + 0.32 新增 5 / 增量门 21 + 0.33 新增 4 / 增量门 20 + 0.34 新增 4 / 增量门 20 + 0.35 新增 5 / 增量门 21 + 0.36 新增 4 / 增量门 20 + 0.37 新增 5 / 增量门 33 + 0.38 新增 5 / 增量门 21 + 0.39 新增 5 / 增量门 21 + 0.40 新增 5 / 增量门 21 + 0.41 新增 5 / 增量门 21 + 0.42 新增 5 / 增量门 21 + 0.43 新增 6 / 增量门 22 + 0.44 新增 6 / 增量门 22 + 0.45 新增 4 / 增量门 20 + 0.46 新增 5 / 增量门 26 + 0.47 新增 5 / 增量门 21 + 0.48 新增 5 / 增量门 21 + 0.49 新增 5 / 增量门 21 + 0.50 新增 5 / 增量门 21 + 0.51 新增 5 / 增量门 21 + 0.52 新增 5 / 增量门 21 + 0.53 新增 5 / 增量门 21 + 0.54 新增 5 / 增量门 21 + 0.55 新增 5 / 增量门 21 + 0.56 新增 5 / 增量门 21 + 0.57 新增 5 / 增量门 21 + 0.58 新增 5 / 增量门 21 + 0.59 新增 5 / 增量门 21 + 0.60 新增 5 / 增量门 21 + 0.61 新增 5 / 增量门 21 + 0.62 新增 5 / 增量门 21 + 0.63 新增 5 / 增量门 21 + 0.64 新增 5 / 增量门 21 + 0.65 新增 5 / 增量门 21 + 0.66 新增 5 / 增量门 21 + 0.67 新增 5 / 增量门 21 + 0.68 新增 5 / 增量门 21 + 0.69 新增 5 / 增量门 21 + 0.70 新增 5 / 增量门 21 + 0.71 新增 5 / 增量门 21 + 0.72 新增 5 / 增量门 21 + 0.73 新增 5 / 增量门 21 + 0.74 新增 5 / 增量门 21 + 0.75 新增 5 / 增量门 21 + 0.76 新增 5 / 增量门 21 + 0.77 新增 5 / 增量门 21 + 0.78 新增 7 / 增量门 23；0.79 新增 5 / 增量门 21 + 0.80 新增 7 / 增量门 23 + 0.81 新增 9 / 增量门 25 + 0.83 新增 9 / 增量门 25 + 0.82 新增 7 / 增量门 22（另 1 skipped） + 251 verify + 49 demo；frontend 39（0.84 起按 Vitest 实际用例）；0.84 全量 `974 passed, 1 skipped` + 0.85 新增 6 / 增量门 100 + 0.86 新增 6 / 增量门 22 + 0.87 新增 7 / 增量门 28 + 0.88 新增 7 / 增量门 25 + 0.89 新增 4 / 增量门 20 + 0.90 新增 5 / 增量门 21 + 0.91 新增 4 / 增量门 20 + 0.92 新增 3 / 增量门 19 + 0.93 新增 4 / 增量门 20 + 0.94 新增 6 / 增量门 22 + 0.95 新增 4 / 增量门 20 + 0.96 新增 5 / 增量门 19；见 [SOP 矩阵](sop_matrix.md) | 10 个 plot 为 route artifact，4 个有 demo 逐值 |
| P10 Docs | 计数已同步 | 历史 release 保持；扩展页去重 |
| P11 Errors | 类型/事件已有 | 用户消息模板统一 |
| P12 Resource | 预算/准入/spill 已实现 | H5AD/10x full 模式 densify |

---

## 14. 决策记录

> 2026-10-23：维护者确认第 1 项为 **B（一次性严格）**；其余授权按推荐/最优判断执行。以下保留为决策记录。

1. **legacy 参数收紧** — **已选 B**
   - 30 个 legacy 已迁移为严格 schema；650 个 task 步骤、111 个 YAML 文件通过严格校验；旧 YAML 的 `min_count` 等无效参数已修正。
2. **参数 UI 分组**
   - A（推荐）：在 schema 增加 `x-ui-group`/`x-ui-order`/`x-ui-unit`，桌面默认只显示 basic。
   - B：不改 schema，由前端维护每个算子的参数分组表。
3. **精度策略**
   - A（推荐）：坐标/计数无损优先，普通矩阵保持 float32。
   - B：所有数值统一 float64（更简单，但内存翻倍）。
4. **Reader 缺失值**
   - A（推荐）：统一 NaN + `missing_code` 声明；有限哨兵只在 Reader 内转换。
   - B：保留各格式原生哨兵，算子自行判断。
5. **桌面改造范围**
   - A（推荐）：保留现有画布/布局，做参数分组、输入预览、错误定位、空状态和结果面板的渐进式简化。
   - B：重新设计信息架构/布局（成本高，回归风险大）。
6. **外部扩展 ID**
   - A（推荐）：外部必须 `lab.*` 命名空间；内置保留历史 ID。
   - B：所有新 ID 强制命名空间（包括内置新增）。
7. **测试门禁**
   - A（推荐）：14 verify + 49 demo + 606 pytest（0.18 全量基线；1 个 full-suite 模式有意 skip）+ registry check + ruff F 全过才算完成；frontend 构建纳入 CI。
   - B：pytest + registry check 为准，verify/demo 作为发布前检查。
8. **BGEN/H5AD 是否纳入本轮**
   - A（推荐）：纳入 BGEN 的 `chrom/pos` 元数据与 H5AD/10x 的磁盘路径；不新增 Reader/算子。
   - B：本轮只修协议/参数/测试，功能增强留到下一轮。

---

## 附录 A — 命名与参数约定

- 维度：`dim`、`*_dim`；不要 `axis`。
- 输出：`output`；不要 `out_name`/`result_key`。
- 标签：`*_label`；不要 `*_name` 混用。
- 方法：`method` 只用于同契约的算法族；ML 一模型一算子。
- 布尔：`scale`/`standardize`/`pairwise`；避免 `do_*`。
- 数值：单位写入 description；坐标注明 0/1-based。
- 错误：`<name>: <field>=<value> <problem>; expected <...>`。

## 附录 B — 输入格式边界（摘要）

支持：CSV/TSV/TXT/Parquet、FASTA、GFF3/GTF、VCF/PLINK1/PLINK2/BGEN（双等位二倍体）、BED、H5AD/MTX、10x H5、GAF。  
不支持：FASTQ、BAM/CRAM、CZI/LIF/ND2/OME-TIFF、MRC、IDAT、FCS、ABF、FID、CBF。
新增 Reader 四条准入：真实公开数据、外部数值参考、至少一条 route 使用、不是流程图中间格式。

## 附录 C — 输出 mode 速查

| mode | 承诺 |
|---|---|
| `passthrough` | 保留第一输入 schema |
| `subset`/`select`/`drop` | 过滤标签，保留语义 |
| `transform` | 保留轴，清除旧 genotype 语义，声明新 representation |
| `project` | 保留/删除轴，可追加轴；`derived` 清除旧语义 |
| `choose` | 按参数选择子规则 |
| `declare` | 完整声明输出 schema |
| `rename`/`transpose`/`concat`/`attach` | 对应元数据操作 |
| `unknown` | 仅运行时校验 |
| `report`/`none` | 不产生 Form；注册 Form 即错误 |

## 附录 D — 交付检查清单

- [ ] 协议条款逐条映射到代码/测试。
- [ ] 每个 Reader/算子有 docstring、参数 title/description、边界测试。
- [ ] 每个输出有契约与运行时校验。
- [ ] `registry check` 干净，生成物未手改。
- [ ] 全量 pytest / verify / demo 通过；skip 有理由。
- [ ] 桌面上常用路径 ≤ 3 步，错误可定位。
- [ ] 外部插件不 import `src.*`、不改核心、不覆盖内置 ID。
- [ ] 文档数字与注册表一致；历史 release notes 不回填。
