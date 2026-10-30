# 测试范式：严格增量 + 周期性全量

BioPipe 的扩展速度很快，逐批重跑全量测试既慢，也容易让“绿色”变成形式。当前测试策略是：

- **日常改动只跑增量测试**，但增量门槛不降低；
- **全量测试按周期或跨层改动触发**，不随每次新增 Reader/算子运行；
- 新增模块必须有测试映射，否则增量运行直接失败。

## 1. 日常命令

```bash
# 查看本次改动的选择结果，不执行
python scripts/test_incremental.py --dry-run

# 严格增量：静态 gate + 改动模块相关测试 + ruff E9/F
python scripts/test_incremental.py
```

`--full` 只用于周期节点：

```bash
python scripts/test_incremental.py --full
```

它会运行全量 pytest、前端测试和构建。全量仍建议在发布前、核心层改动后、每约 3 个扩展批次或用户明确要求时执行。

## 2. 增量选择规则

`scripts/test_incremental.py` 从以下来源取改动：

```text
git diff --name-only HEAD
git ls-files --others --exclude-standard
```

分类规则：

| 改动路径 | 动作 |
|---|---|
| `src/task/step/steps/foo.py` | 找引用 `foo` / `FooStep` 的测试，并强制执行 gate |
| `src/reader/readers/foo_reader.py` | 找引用该类/模块的测试，要求测试包含 `pick_reader` |
| `tests/test_*.py` | 直接加入本次选择 |
| `docs/**`、`README.md`、`AGENTS.md`、reference 索引 | 文档链接、reference、portability 测试 |
| `frontend/**` | `npm test -- --run` + `npm run build` |
| `src/core/**`、Reader/Step 基类、runner、registry 发现逻辑 | **拒绝增量**，必须 `--full` |
| 未归类源码 | 至少运行 gate |

如果新增模块找不到测试映射，脚本直接失败，不进入“先跑再说”。

## 3. 静态 gate

`tests/test_incremental_gate.py` 不执行具体算子，做以下审计：

- 所有 registry 的参数 schema：
  - `type: object`
  - `additionalProperties: false`
  - 参数有类型、`oneOf`、`enum` 或 `$ref`
  - `required` 字段存在
  - 默认值符合类型、`minimum`/`maximum`/`exclusive*`/`enum`
- Reader：
  - 扩展名非空、统一小写、以 `.` 开头
  - 扩展名冲突只允许由 sibling 条件明确消歧（如 PLINK `.bed` 与普通 BED）
  - `file_input.dims` 与 `file_input.labels` 一致
- 算子：
  - `inputs_arity` 与 `contracts.inputs` 数量一致；`*` 表示变长
  - 有输出契约；声明 Form 输出时必须有 `output_parameter`
- 参考文档：
  - `operator_index.json` / `reader_index.json` 的 ID 与 registry 完全一致
  - 每个页面包含 `## Processing rules`
  - `source`、`doc` 路径存在
  - `scripts/build_reference_docs.py --check` 通过
- 改动模块：
  - 新增/修改的 Reader/算子必须被至少一个测试引用
  - Reader 测试必须实际调用 `pick_reader`
  - 算子测试必须包含断言，不接受纯 import

## 4. 新模块的最低测试标准

### 普通算子

- 手工可计算的小数据，断言精确数值或严格不等式；
- 维度、标签、输出行/列顺序；
- 至少一个错误路径（缺输入、组数不对、非有限值等）。

### 统计算子

- 手工值 + 不变量：
  - p/q 在 `[0,1]`；
  - 校正后 `q >= p`，排序关系正确；
  - 效应量方向与分组方向一致；
  - ROC 包含 `(0,0)`、`(1,1)` 端点；
  - 混淆矩阵行和等于真实类别计数。
- 有权威实现的，优先加外部 oracle；至少要有手工值，不能只测 shape。

### Reader

- 最小有效 fixture，断言 dims、labels、关键字段、数值和缺失值；
- `pick_reader` 分派；
- 截断/坏列/空文件至少一种错误路径。

### 文档/前端

- 新算子必须补 `operatorPresentation.ts` 图标，无 placeholder；
- 参考页、索引、计数、链接同步；
- 前端测试和构建通过。

## 5. 外部 oracle

优先使用 WSL 中的权威实现，避免在 Windows 侧维护测试环境：

- R：`limma`、`fgsea`、`metafor`、`GSVA`、`sva`、`Kendall`、`edgeR`、`DESeq2`；
- Python：scipy、statsmodels、scikit-learn、lifelines、umap-learn；
- 格式：以规范/权威文档的手工记录为准，例如 BLAST outfmt6、HMMER tblout、ENCODE bedMethyl。

当前 oracle 入口：

```bash
pytest -q tests/test_r_oracles.py tests/test_r_oracles2.py tests/test_r_oracles3.py
```

只在本批涉及相关算子时运行，不要求每次全跑。

## 6. 失败条件

- 新增模块没有测试映射；
- 未说明原因的 skip；
- 新增/修改测试在 `-W error` 下出现 warning；
- schema 开放（`additionalProperties` 不是 `false`）；
- Reader 扩展名冲突且无 sibling 消歧；
- 参考页缺失、索引不一致、计数不一致；
- 新算子测试只有 shape/finite，没有数值或契约断言；
- 前端图标回退到 placeholder。

## 7. 全量触发条件

1. 修改 `src/core/`、Reader/Step 基类、runner、registry 发现逻辑；
2. 发布新 minor 版本前；
3. 每约 3 个扩展批次；
4. 路由/注册表生成逻辑改动；
5. 用户明确要求。

全量包括：pytest、route fixtures、verify/demo 矩阵、前端测试与构建、registry check。增量通过不等于可以跳过发布前全量。

## 8. 已知边界

- `-W error` 只对本次新增/修改的测试启用，避免存量 warning 阻断增量；
- 静态 gate 不能证明数值正确，数值正确性仍由手工值和 oracle 测试负责；
- R 包缺失时 oracle 测试按环境 skip；发布前应确认关键 R 包在 WSL 可用；
- 原生 Windows 不支持 `pysam`/`pyBigWig` 的 Reader 仍按 [Windows 兼容性](windows_compatibility.md) 处理。
