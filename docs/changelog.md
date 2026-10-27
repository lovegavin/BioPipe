# 更新记录

BioPipe 使用语义化版本和 git tag。当前源码版本：**0.8.0（2026-10-27）**。
更早版本从 git tag/history 查；本页只保留当前版本摘要。

## 0.8.0 — 2026-10-27

**主题：第一批按路径热度扩展 Reader、算子和 route。**

- 新增 3 个 Reader：`GmtReader`（GMT 基因集）、`LoomReader`（Loom 单细胞）、`BiomReader`（BIOM JSON/HDF5）。
- 新增 11 个算子：`gsea`、`ora`、`doublet_detect`、`pseudobulk`、`marker_score`、`meta_analysis`、`prs`、`protein_rollup`、`limma_de`、`ancom_bc`、`aldex2`。
- 新增 5 条 route：`rnaseq_de_enrichment`、`single_cell_loom`、`gwas_meta_prs`、`proteomics_limma`、`microbiome_diff`。
- 当前：89 算子 / 19 Reader / 19 route；全部严格 schema/contracts。
- 新增 Reader/算子/route 单测与端到端 smoke test；`doublet_detect`/`marker_score` 直接调用 Scanpy，`aldex2`/`ancom_bc` 为独立 log-ratio 实现并在文档中明确边界。
- 验证：**460 passed / 17 skipped**（2026-10-27）；5 条新 route 实际运行；参考页生成检查；Studio 新算子展示补齐，前端 **66 passed**；本机无 R，`limma_de`/`ancom_bc`/`aldex2` 为独立近似实现，未做 R 外部 oracle 对比。

## 0.7.0 — 2026-10-27

**主题：严格契约、Agent/SOP 文档、Studio 导入修复。**

- 16 个 Reader / 78 个算子全部严格 schema（`additionalProperties: false`）；30 个 legacy 算子迁移到源码声明，`operator_ui.json` 只保留展示元数据。
- Reader/算子参数补齐 title、basic/advanced 分组、单位；`Step`/`Reader` 基类强制严格校验。
- 新增 78 个算子页、16 个 Reader 页、机器索引、SOP/LLM/用户手册、ANALYSIS 模板和路线架构师提示词。
- 新增 `biopipe inspect` 与 `scripts/run.py tasks/<dir> --check`。
- 修复 Studio 导入：从 `code_root` 搜索任务输入；支持 YAML 绝对路径；跨盘 job 不再调用 `os.path.relpath`；重选文件保留 Reader 参数；`_input_names` 在边界剥离。
- heatmap 增加 `max_cells`/`max_pixels`，阻止 5247×5247 相关矩阵触发 168 GiB 渲染分配。
- 验证：440 passed / 12 skipped、14/14 verify、49/49 demo、registry check、ruff、compileall、portability。
- Windows 环境快照：[conda](../windows-biopipe-conda.yml) / [pip](../windows-biopipe-pip-freeze.txt)。

## 更早版本

| 版本 | 说明 |
|---|---|
| 0.4.1 | 已发布的 Windows 桌面版；64 算子、15 Reader、5 路线 |
| 0.3.x | 上游引擎/桌面迭代 |
| 0.2.x | 早期桌面与协议 |

历史发布说明不单独维护；需要追溯时从 git tag/release history 查看。
