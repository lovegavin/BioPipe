# 更新记录

BioPipe 使用语义化版本和 git tag。当前源码版本：**0.9.0（2026-10-29）**。
更早版本从 git tag/history 查；本页只保留当前版本摘要。

## 0.9.0 — 2026-10-29

**主题：批次校正与 ssGSEA。**

- 新增算子 `combat`：基于 Scanpy 的 ComBat，另有 `mean_center` 轻量模式；适配 metadata 批次列和 sample 轴。
- 新增算子 `ssgsea`：按 GSVA `ssgsea` 的 rank-sum 路径实现；输出 sample × gene-set 分数。
- 新增 route：`single_cell_batch`（单细胞去批次 + marker score）、`rnaseq_ssgsea`（RNA-seq ssGSEA）。
- 当前：91 算子 / 19 Reader / 21 route；全部严格 schema/contracts。
- 验证：**494 passed / 0 skipped**（2026-10-29）；21/21 route 用仓库 fixture 实际执行；`ssgsea` 与 R GSVA 1.28 对拍；参考页生成检查；Studio 前端 **68 passed**；R oracle **7 passed**。
- 边界：`combat` 未与 R `sva::ComBat` 做独立数值对拍；`ssgsea` 只覆盖 GSVA 的 rank-sum 变体。

## 0.8.0 — 2026-10-27

**主题：第一批按路径热度扩展 Reader、算子和 route。**

- 新增 3 个 Reader：`GmtReader`（GMT 基因集）、`LoomReader`（Loom 单细胞）、`BiomReader`（BIOM JSON/HDF5）。
- 新增 11 个算子：`gsea`、`ora`、`doublet_detect`、`pseudobulk`、`marker_score`、`meta_analysis`、`prs`、`protein_rollup`、`limma_de`、`ancom_bc`、`aldex2`。
- 新增 5 条 route：`rnaseq_de_enrichment`、`single_cell_loom`、`gwas_meta_prs`、`proteomics_limma`、`microbiome_diff`。
- 当前：89 算子 / 19 Reader / 19 route；全部严格 schema/contracts。
- 全 route fixture 验证：19 条 route 均在 pytest 内实际执行；Multi-omics 相关矩阵前增加方差 top-500 预筛选。
- 新增 Reader/算子/route 单测与端到端 smoke test；`doublet_detect`/`marker_score` 直接调用 Scanpy，`aldex2`/`ancom_bc` 为独立 log-ratio 实现并在文档中明确边界。
- 验证：**488 passed / 0 skipped**（2026-10-29）；19/19 route 用仓库 fixture 实际执行；参考页生成检查；Studio 新算子展示补齐，前端 **66 passed**；新增 `tests/test_r_oracles.py` 6 个 R 4.3.3/Bioc 3.18 对拍（limma 普通 t、fgsea ES、metafor FE/DL、phyper、独立 log-ratio/Welch），全部通过；`limma_de` 默认 eBayes 先验、`ancom_bc`/`aldex2` 完整 R 包行为仍未对拍。

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
