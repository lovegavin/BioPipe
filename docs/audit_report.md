# 历史审计报告

> 这是 2026-10 的历史审计记录，不是当前规范。当前入口：[docs/README.md](README.md)。
> 2026-10-23 增量：本文件 §1–§8 记录 10-22 第一轮审计。随后按协议 v2 完成了严格参数 schema、`operator_ui.json` 参数去重、参数标题/分组、独立 Reader SOP 与核心算子 SOP。最新测试数字与覆盖矩阵见文末“2026-10-23 增量”及 [SOP 矩阵](sop_matrix.md)。

**BioPipe 审计、加固与架构梳理报告**

日期：2026-10-22  
范围：当前 `main` 工作树（HEAD `6262172`，包含未提交的交接文档）  
原则：先备份、再修改；每批修改独立测试；不新增 Reader/算子。

## 0. 执行摘要

- **完整备份**：`~/biopipe-backup-20261022-201452`（6.7 GB，3337 个文件，含 `.git` 和未提交文档）。
- **基线**（修环境前）：`366 passed / 20 failed`；其中 4 个是缺依赖，16 个是测试脚手架/环境问题。
- **最终全量测试**：`389 passed / 12 skipped / 0 failed`（详见 §6）。
- **独立验证脚本**：14 个脚本、251 项检查最终全部通过；期间 `verify_go_enrichment` 曾因 pivot 上限过紧回归，修正后 `10/10`。
- **注册表一致性**：`python -m biopipe registry check` 最终为 `changed: []`。
- **静态检查**：`ruff check --select F` 为 0；`compileall` 通过。
- **净代码量**：删除 `snapshot.txt`（17,544 行）、`src/reader/schemas.py`（99 行）以及 TSV/GFF/GTF 重复实现，整体约 **-18,000 行**；有效逻辑改动约 690 行。

结论：这轮不是“把代码重写一遍”，而是先把**数据正确性、注册表事实来源、测试可信度和文档计数**这四件事钉死；架构层面的剩余债务在 §5 明确列出。

## 1. 备份与回滚

备份是完整副本，不是 git bundle，因此未提交内容和被忽略的输入数据也在内：

```bash
# 备份位置
~/biopipe-backup-20261022-201452

# 回滚（把当前工作树移开，再恢复备份）
mv ~/biopipe ~/biopipe-broken-$(date +%Y%m%d-%H%M%S)
cp -a ~/biopipe-backup-20261022-201452 ~/biopipe

# 或者只回滚代码/文档，保留输入数据
rsync -a --delete \
  --exclude 'tasks/*/input/' --exclude 'tasks/*/output/' \
  ~/biopipe-backup-20261022-201452/ ~/biopipe/
```

本次没有提交 commit，所有改动都在工作树中，可用 `git diff` 审阅。

测试环境只做了依赖安装，未改仓库：`fastapi 0.159.1`、`uvicorn 0.54.0`、`build 1.6.1`、`mcp 1.30.0`、`ruff 0.17.1`、`pytest-timeout 2.4.0`、`py-spy 0.4.2`。不需要时可 `pip uninstall`。

## 2. 基线与测试方法

环境：`~/miniconda3/envs/biopipe/bin/python`，Python 3.11.15。

基线命令与结果：

```bash
cd ~/biopipe
python -m pytest -q
python -m biopipe registry check
for f in tasks/verify_*.py; do python "$f"; done
```

基线问题分三类：

1. **环境**：缺少 `fastapi/uvicorn/build`，12 个测试模块无法收集；`remember_runtime` 也因缺 `fastapi` 返回 False。
2. **测试脚手架过时**：内置路线已从 5 条增长到 14 条，但 `test_builtin_routes.py` 仍断言 5 条；`test_registry_maintenance.py` 仍断言 6 条；`frontend/dist` 未构建时桌面测试直接失败；根目录残留 `tmp.txt` 触发 portability 检查。
3. **真实缺陷**：坐标精度、GFF3 `##FASTA`、BED 解析、FASTA 空记录等（见 §3）。

## 3. 已修复的真实缺陷

### 3.1 基因组坐标被 float32 静默改写（High）

**现象**：BED 的 `chromStart=100000001` 读入后变成 `100000000.0`，`chromEnd=100000010` 变成 `100000008.0`。人类染色体位置最大约 2.5e8，而 float32 只能精确表示到 2^24（16,777,216）。

**影响**：`interval_merge`、`interval_overlap`、`annotation_gaps`、`peak_nearest_gene` 的边界、长度、最近基因距离都可能在千万级坐标上偏移数 bp。更严重的是，旧验证脚本的独立实现也读同一份 float32 数据，两边“错得一样”，所以 `verify_interval_analysis.py` 之前是 **假绿**。

**修复**：

- 新增 `src/core/numeric.py::compact_numeric`：先按 float64 解析，能无损转 float32 才转，否则保留 float64。
- CSV/TSV/Parquet/BED/GFF3/GTF 的数值列改为 float64 解析 + 末次无损压缩；普通表达矩阵仍然保持 float32。
- 所有输出坐标/长度的算子（`interval_merge`、`interval_stats`、`interval_overlap`、`annotation_gaps`、`gene_structure`、`gff_feature_stats`、`peak_nearest_gene`）改用同一 helper。

**证据**：

- 修复前：`chromStart 100000001 -> 100000000.0`，`chromEnd 100000010 -> 100000008.0`。
- 修复后：BED/GFF3/GTF/CSV/Parquet 坐标精确；`interval_merge` 的 start/end 精确。
- `verify_interval_analysis.py` 的 `total_bp` 从 `290119808` 变为 `290119782`（26 bp 虚假增量消失），并在输出精度修复后由 `7/8` 恢复为 `8/8`。

新增测试：`tests/test_reader_precision.py`（6 个读取精度用例 + 1 个 interval_merge 输出精度用例）。

### 3.2 GFF3/GTF 的 `##FASTA` 段被当成注释记录

**问题**：GFF3 规范允许文件末尾跟 `##FASTA` + 序列。旧实现只跳过 `#` 开头的行，`##FASTA` 之后的序列行会被当成 9 列记录，导致“列数不一致”或污染注释表。

**修复**：`src/reader/readers/_gff_base.py::_load_rows` 在 `##FASTA` 处 `break`。GFF3 和 GTF 共享同一实现。

新增测试：`tests/test_reader_conformance.py::test_gff3_stops_before_embedded_fasta`（以及 GTF 版本）。

### 3.3 BED 解析不符合标准格式

**问题**：

- `line.split()` 会按任意空白切分，导致 `name` 字段含空格（如 `CTCF binding site`）时列错位。
- 不跳过 `#` 注释行；带注释的 BED 会报列数不一致。
- 纯空格对齐的旧 BED 需要兼容。

**修复**：`bed_reader.py::_load` 优先按 `\t` 切分，只有整行没有 tab 时才回退到任意空白；跳过空行和 `#` 注释；仍识别 `track`/`browser` 前缀。

新增测试：`test_bed_skips_comments_and_preserves_spaces_in_tab_fields`、`test_bed_accepts_plain_whitespace_when_tabs_are_absent`。

### 3.4 FASTA 空记录和字母表推断

**问题**：

- 连续两个 `>`（空序列）时，旧实现不会为第一个记录追加空串，导致 `ids` 与 `seqs` 长度错位，最终 Form 校验失败或数据错行。
- 文件在第一个 `>` 之前出现序列时，旧实现静默接受，最终 id/sequence 数量不一致。
- 蛋白序列含 `X/B/Z/J/O/*` 时，旧 `_infer_alphabet` 会误判为 `dna`。

**修复**：

- `_parse_fasta` 在每次遇到 `>` 时关闭上一条记录（即使为空），并显式拒绝“首个 header 之前出现序列”。
- 蛋白字母集加入 `BXZJOU*`；若出现 `E/F/I/L/P/Q/X/Z/J/*` 等蛋白特征字母，优先判为 `protein`。
- 保留空记录的 `(n, max_len)` 矩形，空行填 NaN。

新增测试：`test_fasta_keeps_empty_records_aligned`、`test_fasta_rejects_sequence_before_header`、`test_fasta_alphabet_inference_handles_protein_unknowns`。

### 3.5 注册表漂移：Reader 参数只存在于生成物

**问题**：`builtin_packages.json` 里有 H5AD 的 `layer`、BED/GFF/GTF/Parquet 的 `encoders`、TXT 的 `reader` 等参数，但源码类没有 `parameters_schema`；它们来自 `src/reader/schemas.py` 的 fallback。结果是“源码不是事实来源”：重新生成索引、单独导入 reader、写插件测试时行为可能不同。

**修复**：

- 给全部 16 个 Reader 在源码中声明 `parameters_schema`：H5AD `layer`，BED/GFF/GTF/Parquet `encoders`，TXT `reader/header/sep/columns/info_columns/encoders`，MTX/FASTA/PLINK/BGEN/VCF 空 schema，10x H5 的两个参数保留并补充标题/说明。
- `src/reader/__init__.py::_discover` 遇到无 schema 的 Reader 直接报错；`biopipe/registry.py::scan_sources` 移除 `builtin_schema` fallback。
- 删除 `src/reader/schemas.py`。

验证：`test_reader_and_operator_options_are_discoverable` 通过；`registry check` 干净；全部 16 个 reader 均有 schema。

### 3.6 内置 manifest 缓存漏掉同尺寸修改

**问题**：`biopipe/packages.py::bundled_state` 只用 `mtime_ns/ctime_ns/size` 做缓存键。在同一时间粒度内把 `"version": "1.0"` 改成 `"2.0"`（同尺寸），缓存可能继续返回旧版本。

**修复**：索引文件额外加入 SHA-256；manifest 很小，成本可忽略。`test_builtin_pins.py::test_builtin_cache_tracks_edits_and_manifest_without_restart` 从失败变为通过。

### 3.7 测试脚手架过时/不可移植

- `tests/test_builtin_routes.py`：不再硬编码 5 条路线；改为对 `BUNDLE` 全量断言，并新增 `test_all_shipped_route_graphs_compile` 覆盖 14 条路线的编译；没有合成数据的 9 条路线显式 `pytest.skip`（真实数据由各自 route demo 覆盖）。
- `tests/test_registry_maintenance.py`：`built.routes == 6` 改为 `== len(discovery["routes"])`。
- `tests/test_portability.py`：`frontend/dist` 不存在时跳过复制；桌面 worker 测试显式 skip。
- `tests/test_desktop.py`：桌面服务器测试在缺少 `frontend/dist` 时 skip，保留 draft/worker 测试。
- 删除根目录调试残留 `tmp.txt`；`portability` 的开发者路径检查恢复通过。

### 3.8 重复实现、死代码与生成物

- **TSV**：`tsv_reader.py` 原为 343 行 CSV 复制品；改为 `CsvReader` 子类（约 20 行），`default_sep="\t"`、`format_name="TSV"`；错误前缀按实际格式显示。
- **GFF3/GTF**：两份 220 行实现合并为 `_gff_base.py`；子类只保留列名、扩展名、显示名。
- **compare_groups.py**：删除重复 import 和重复类属性/`estimate_memory`（后定义覆盖前定义）。
- **pivot.py**：`_MAX_CELLS = 200_000_000_0`（2e9 cells，约 8 GB float32）改为 `500_000_000`（约 2 GB）。真实 GO GAF pivot 是 19,702 × 17,894 = 3.52 亿 cells，2e8 会误杀，5e8 既能容纳真实流程又能拦住更大的意外分配。
- **cox_regression.py**：删除重复的 lifelines import 块和未使用的 `ConvergenceError`。
- **snapshot.txt**：删除 17,544 行已过期的全仓库快照（生成物，不是源码），并在 `.gitignore` 中加入 `snapshot.txt`。
- **未使用 import**：`ruff --select F401` 从 102 个降到 0；`F841/F811/F541` 也清零。

### 3.9 文档与当前代码脱节

- `README.md`：顶部从“64 operators / 15 readers / five routes”改为当前 **78 / 16 / 14**，并注明 0.4.1 发布版仍是 64/15/5；Reader 路由段从 15 改为 16；包说明从“39 operators”改为六个包。
- `docs/route_operators.md`：内置模板表从 5 条补全为 14 条（输入/输出/节点数来自 `builtin_routes.json`）。
- `docs/package_protocol.md`：包条目数改为 44/7/7/12/8/16。
- `docs/operator_protocol.md`：移除“31 legacy / 13 Readers”等过期数字，改为“以生成注册表为准”。
- `docs/desktop.md`：首次启动模板列表改为当前 14 条的代表性列表。
- `docs/releases/v5.md`：在 baseline scope 下补充“patches 之后为 16/78/14”。

## 4. 参数与易用性审计

### 4.1 现状

- 78 个算子全部有 `parameters_schema`；16 个 Reader 现在也全部在源码中声明。
- 仍有 **30 个 legacy 算子** 的 schema 来自 `src/task/operator_ui.json`，`additionalProperties: True`，拼错的参数会被静默忽略。这是历史兼容层，不是本轮能安全全量收紧的部分。
- 参数很多的算子集中在绘图和区间分析：
  - `peak_nearest_gene` 16 个、`heatmap` 15 个、`barplot/dotplot/forest_plot/ma_plot/violin` 14 个、`interval_overlap` 13 个、`manhattan/kaplan_meier` 12 个。
  - 这些参数多数是“选择列/标签/样式”，不是算法参数；真正需要收敛的是默认值、标题和分组，而不是简单删参数。
- 区间/注释类算子的 `*_field` 参数已经通过默认值支持标准列名，但跨格式时仍需显式覆盖；GTF/GFF 的自动列名解析已由 `_annotation_columns.py` 覆盖。

### 4.2 已做的易用性改进

- H5AD 的 `layer` 现在会出现在 UI 参数里，并带标题/说明。
- BED/GFF/GTF/Parquet 的 `encoders` 现在显式暴露。
- TXT 的委托 Reader、分隔符、列选择、info 列、编码器全部可见。
- 10x H5 的 `feature_type`/`feature_id_field` 增加标题和说明。
- TSV 现在继承 CSV 的完整参数（包括 `sep`），错误消息显示 `TSV reader` 而不是 `CSV reader`。

### 4.3 尚未做的（明确列出）

- 把 30 个 legacy 算子迁移为严格 schema。建议按包分批：先 `quality_control`（maf/hwe/missing/ld_prune/filter_min），再 `data`（select/drop/rename_dim/transpose/concat/attach_info），最后 plots。每批都要用现有 YAML 做兼容性扫描。
- 合并 `operator_ui.json` 与类声明这两个 UI 参数来源；目前 `build_catalog` 仍会用它覆盖 legacy 算子的展示字段。
- 为 9 条没有合成 fixture 的内置路线补测试数据，或把它们改成“编译 + 真实 demo”两层测试。
- 把 frontend 构建纳入测试环境，否则桌面服务器测试永远 skip。

## 5. 架构梳理与剩余风险

### 5.1 当前架构（稳定部分）

```
Manifest (task.yaml)
  → Reader (16) → Form (ndarray + dims + labels + info + axis_info)
  → Step/Operator (78, 6 packages) → Contract 校验 → 输出/导出
  → Context/Runner → run_summary + events.jsonl + memory_report.json
```

- **数据契约**：`input_contracts`/`output_contract` 做静态三态分析（compatible/incompatible/unknown），执行边界再做真实数据校验；`axis_info` 是轴平行元数据唯一合法入口。
- **资源运行时**：固定预算、逐步准入、最远下次使用淘汰、流式 `describe`、磁盘 `dense-writer-v1`；memory_report 明确“估算准入，不是硬保证”。
- **Studio**：FastAPI loopback + 每进程 token；`Graph` 编译成确定性拓扑序的 `task.yaml`；`JobService` 起独立 `scripts/run.py` 子进程；`DocumentHub` 用 revision CAS 统一 UI/Agent 编辑与 undo。
- **包/注册表**：`biopipe registry build` 生成 `builtin_packages.json` 和 `builtin_routes.json`；不要手改。
- **Agent**：CLI/MCP 都是 loopback HTTP 适配层，默认 `context+edit`，`--allow-run` 才执行。

### 5.2 剩余风险

1. **legacy 算子参数宽松**：30 个算子的拼写错误不会报错，只会被忽略；这是最容易造成“参数没生效”的地方。
2. **BGEN 缺 chrom/pos**：`BgenReader` 只输出 dosage，没有像 VCF/PLINK 一样把染色体/位置放进 `info` + `axis_info`；需要时可作为下一轮 Reader 元数据增强。
3. **H5AD/10x 全量路径仍 densify**：磁盘路径存在，但 `read()` 仍 `toarray()`；超大单细胞矩阵在 full 模式仍可能 OOM。
4. **前端未构建**：本环境没有 `frontend/dist`，12 个 skip 中 3 个是桌面/端口测试；`npm test`/`npm run build` 未执行。
5. **生成物与源码的边界**：`biopipe/builtin_packages.json` 和 `src/web/builtin_routes.json` 是生成物；`snapshot.txt` 这类快照不要再次提交。
6. **文档历史数字**：`docs/releases/v0.3.x`、`v0.4.1` 保留发布时的数字，不应改成当前值；当前状态以 README 顶部和生成注册表为准。

## 6. 测试证据

| 测试 | 命令 | 结果 |
|---|---|---|
| 全量 pytest | `python -m pytest -q` | **389 passed, 12 skipped, 0 failed** |
| 独立验证脚本 | `tasks/verify_*.py` | 14 个脚本、251 项检查全过；`verify_go_enrichment` 修正 cap 后 `10/10` |
| Demo 自测 | `tasks/*_demo/test_*.py` + `tests/reader_crlf/test_*.py` | 50 个文件全部通过（修复 3 个过时测试后） |
| 注册表 | `python -m biopipe registry check` | `changed: []`, `errors: []` |
| 精度回归 | `pytest tests/test_reader_precision.py` | 7 passed |
| 格式回归 | `pytest tests/test_reader_conformance.py` | 7 passed |
| 静态检查 | `ruff check --select F` | 0 issues |
| 语法 | `python -m compileall -q src biopipe biopipe_sdk` | OK |
| 前端 | `npm test` / `npm run build` | 未运行（无 `frontend/dist`，WSL 内无 node） |

12 个 skip 的构成：9 条内置路线没有合成 fixture（真实数据由 route demo 覆盖）+ 2 个桌面服务器测试 + 1 个桌面 worker 测试（均因 `frontend/dist` 缺失）。

## 7. 变更批次

| 批次 | 内容 | 主要验证 |
|---|---|---|
| A1 | 数值无损压缩，Reader 坐标精度 | `test_reader_precision.py` |
| A2 | 区间/注释算子输出精度 | `verify_interval_analysis.py` |
| A3a | GFF3/GTF `##FASTA`、BED 注释/空格 | `test_reader_conformance.py` |
| A3b | TSV 改为 CSV 子类 | CSV/TSV/upstream 测试 |
| A3c | GFF3/GTF 合并为 `_gff_base` | `verify_gtf_annotation.py` |
| A4 | 过时测试修复 + 全路线编译测试 | 31 passed / 12 skipped |
| A5 | FASTA 空记录/蛋白字母表 | 14 passed |
| A6 | manifest 缓存 hash | `test_builtin_pins.py` 8 passed |
| A7 | 重复定义/死代码/pivot cap | 39 passed + transform 34/34 + stats 10/10 |
| A8 | README/协议/路线文档同步 | `git diff` 审阅 |
| A9 | 16 个 Reader 源码声明 schema | 55 passed + registry check |
| A10 | 删除 `schemas.py`/`snapshot.txt` | 67 passed + registry check |
| A11 | 清理 102 个 unused imports / 剩余 F 类问题 | 全量 389 passed |
| A12 | `compare_groups` 保留 `title/category/builtin_package`，避免标题与包归属漂移 | `registry check` |
| A13 | `TxtReader` 保留原参数描述，避免 UI 说明丢失 | `registry check` |
| A14 | pivot 上限改为 5e8；cluster_axis 测试函数改名；GC skew 补 `cumulative_gc` 文档/断言 | cluster 10/10、gc_skew 全过、GO 10/10 |

## 8. 后续建议（按优先级）

1. **收紧 30 个 legacy 算子的参数 schema** ✅ 2026-10-23 已完成：严格 schema + 兼容性扫描 + `operator_ui.json` 参数去重。
2. **给 BGEN 补 `chrom`/`pos`**：与 VCF/PLINK 对齐，便于 `annotate`/`manhattan`/区间分析。
3. **给 9 条路线补合成 fixture 或真实 demo 集成测试**，把 skip 降到 0。
4. **修复 H5AD/10x 的 full 模式 densify**：优先让 `read()` 也走磁盘/分块路径，或在超阈值时自动选择 disk。
5. **在 CI 中构建 frontend**，让桌面/端口测试真正执行。
6. **保持单一事实来源** ✅ 参数已只在源码声明；`operator_ui.json` 仅保留展示元数据。

---

**诚实声明**：本轮修复的是“可复现、有测试证据”的问题；没有声称已经覆盖 78 个算子的所有数学分支。`verify_*.py` 已覆盖的 251 项检查、pytest 的 389 项测试是本报告（10-22）的客观边界；30 个 legacy 算子已于 10-23 完成严格化。BGEN 坐标、H5AD/10x full 模式等仍未闭环，见文末增量。


---

## 2026-10-23 增量：严格 schema 与独立 SOP

### 参数与协议

- 30 个 legacy 算子全部迁移为源码严格 schema（`src/task/step/steps/_legacy_schemas.py`），`additionalProperties: false`，`legacy_parameters = False`。
- `Step`/`Reader` 基类进一步统一强制 `additionalProperties: false`；16 个 Reader、78 个算子全部由 `tests/test_schema_strictness.py` 断言，新增扩展不能退回宽松模式。
- `src/task/operator_ui.json` 只保留 title/category/description/icon，文件从 1,485 行降到 258 行；参数不再有第二来源。
- 111 个 task/YAML、650 个步骤通过严格参数校验；`min_count`、无效 `filter_min rules` 等静默忽略的参数已修正。
- 参数 schema 增加统一的 `title`、`x-ui-group`、`x-ui-order`、`x-ui-unit` 归一化；无标题参数不再进入 UI。

### 独立 SOP 测试

- `tests/sop/test_readers_sop.py` + `test_genotype_readers_sop.py`：16 个 Reader，全部与独立解析器/库对比（pandas、scipy、h5py、pysam、bed_reader、pgenlib、bgen_reader）。
- `tests/sop/test_core_operators_sop.py`：11 个核心变换与 pandas/NumPy 逐值对比。
- `tests/sop/test_report_contracts_sop.py`：14 个绘图/report 算子契约、严格 schema、标题覆盖。
- 共 29 个独立 SOP 测试；矩阵见 [docs/sop_matrix.md](sop_matrix.md)。

### 最终测试

- 全量 pytest：**440 passed, 12 skipped, 0 failed**（含 29 个 SOP）。
- `biopipe registry check`：`changed: []`。
- 14 个 verify 脚本与 49 个 demo 自测在严格 schema 后复跑通过（见 SOP 矩阵的复现命令）。
- 额外修复：`concat` 缺省输出名、`filter_min` YAML 参数、测试专用严格的 report/stream schema、`tree_snapshot.txt` 过期生成物。

### 仍未闭环

- 绘图算子：4 个有 demo 逐值测试（barplot/dotplot/violin/enrichment_plot），line 有直接 PNG artifact 测试，其余 10 个由 5 条 route 的 PNG artifact 覆盖；绘图本身无数值契约，因此不设数值 oracle。
- 9 条内置 route 缺合成 fixture；3 个桌面测试因 `frontend/dist` 缺失而 skip。
- BGEN 的 `chrom/pos` 元数据、H5AD/10x full 模式 densify 仍是下一阶段。


### 2026-10-23 可用性改造增量

- 修复 `_input_names` 泄漏：runner、graph 编译校验、YAML 导入、任务导出边界统一剥离；新增 3 个回归测试（直接 runner、YAML import、Graph compile）。
- 修复 heatmap 大矩阵 OOM：`max_cells`（默认 400 万）在转 float64/绘图前拒绝超大选中矩阵；`max_pixels`（默认 4000 万）限制自动 figsize 像素预算；新增 2 个回归测试。
- 新增 `python scripts/run.py tasks/<dir> --check`：静态校验路径、Reader 选项、参数、输入来源、输出重名和图片名。
- 新增 `python -m biopipe inspect <path> --json`：输出 Reader、shape、dims、labels、缺失、范围和编码摘要。
- 新增 78 个算子页、16 个 Reader 页、JSON 索引、SOP/LLM/用户手册、ANALYSIS 模板和固定提示词；`scripts/build_reference_docs.py --check` 做完整性门禁。
- `tasks/sop_demo` 走通“绝对路径 → input/ → task.yaml → ANALYSIS.md → --check → 实际运行 → PNG”全流程。
