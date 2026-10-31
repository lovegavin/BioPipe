# QIIME 2 moving pictures：微生物组 BIOM 读取与群落结构

## 数据来源

- 主数据：QIIME 2 官方 moving-pictures 教程的特征表 `table.qza`，<https://docs.qiime2.org/2024.10/data/tutorials/moving-pictures/table.qza>（57,130 字节）。解包后得到 BIOM 2.1 文件 `feature-table.biom`。
- 分类注释：同一教程的 `taxonomy.qza`，<https://docs.qiime2.org/2024.10/data/tutorials/moving-pictures/taxonomy.qza>（78,354 字节）；解包后得到 `taxonomy.tsv`。本示例把每个 feature 的最深分类名与 6 位 feature hash 组合成可读标签，例如 `g__Bacteroides [4b5eeb]`，并作为 BIOM 的 `observation/metadata` 写入 `input/feature-table.biom`。
- 样本：34 个，770 个 taxa，2,327 个非零值，总计数 153,807。样本 ID 为 `L1S105`、`L1S140`、…、`L6S93`。
- **重要限制**：教程的 `sample_metadata.tsv`（含 body site）在本次运行中无法稳定下载；本示例没有 body-site 标签。`input/sample_metadata.csv` 的 `subject` 由样本 ID 的 `L*` 前缀派生（L1–L6），只用于检验个体间差异，不是 body site、时间点或临床分组。
- 引用：Bolyen, E. et al. (2019). Reproducible, interactive, scalable and extensible microbiome data science using QIIME 2. *Nature Biotechnology*, 37, 852–857. <https://doi.org/10.1038/s41587-019-0209-9>；原始 moving-pictures 数据来自 Caporaso, J.G. et al. (2011). Moving pictures of the human microbiome. *Genome Biology*, 12, R50. <https://doi.org/10.1186/gb-2011-12-5-r50>。

## 读取与预处理

`BiomReader` 以 `dims: [sample, taxon]` 读取 BIOM，taxonomy 参数打开后使用分类标签。QIIME 2 的 BIOM 有一个空的 `observation/metadata` HDF5 group；原实现把它当 dataset 切片，触发：

    TypeError: Accessing a group is done with bytes or str, not <class 'slice'>

本示例修复了该分支：dataset 按 JSON-per-row 解析，空 group 或缺 group 视为没有 taxonomy；并在 `tests/test_new_readers.py` 增加空 group 与 taxonomy dataset 的回归测试。

读取后的处理：

1. `filter_min(dim=taxon, min_value=10, min_samples=10)`：保留在至少 10 个样本中计数 ≥10 的 taxa；770 → 29。这个阈值是为了去掉低丰度/低 prevalence 的噪声，不是生物学“核心菌群”定义。
2. alpha 多样性在过滤后的 29 个 taxa 上计算，因此这里的 richness/Shannon 是**过滤 panel 内**的多样性，不能与未过滤的全表 richness 直接比较。
3. Bray-Curtis 距离基于同一过滤表；`pcoa` 取前两个坐标；`permanova` 用 999 次置换，随机种子 17。
4. 按 subject 求 taxa 平均丰度（`aggregate`），`rename_dim` 把聚合后的 `feature` 轴改为 `subject`；`hvg` 在 6 个 subject 均值上选 20 个方差最大的 taxa，`filter_by` 保留这些 taxa；热图按 taxa 行做 z-score。

## 路线

`task.yaml` 共 13 步：

1. `BiomReader` 读取 `sample × taxon`，并带 taxonomy 标签。
2. `filter_min` 过滤低丰度 taxa。
3. `diversity` 计算 Shannon、richness、evenness。
4. `boxplot` 展示 Shannon 按 subject 的分布。
5. `distance_matrix` 计算 Bray-Curtis。
6. `pcoa` 取 2 个坐标。
7. `boxplot` 展示 PCoA1 按 subject。
8. `boxplot` 展示 PCoA2 按 subject。
9. `permanova` 检验 subject 对群落距离的解释。
10. `aggregate` 按 subject 求 taxa 平均丰度。
11. `rename_dim` 将聚合后的 `feature` 轴改为 `subject`。
12. `hvg` 选 20 个高变 taxa，`filter_by` 保留。
13. `heatmap` 展示 subject × top taxa 的聚类热图。

## 结果

### 样本与过滤

- 34 个样本，6 个 subject：L1 8、L2 8、L3 6、L4 3、L5 6、L6 3。
- 770 个 taxa；过滤后 29 个 taxa；20 个进入热图。
- 过滤后 alpha 多样性中位数：
  - L1：Shannon 1.3316，richness 7.0
  - L2：Shannon 2.1781，richness 16.5
  - L3：Shannon 1.8296，richness 10.0
  - L4：Shannon 2.2991，richness 24.0
  - L5：Shannon 1.9469，richness 12.0
  - L6：Shannon 1.9216，richness 14.0
- L1 的多样性最低；L4/L2 较高。但 L4、L6 各只有 3 个样本，不能把组间差异当作稳定总体差异。

### PCoA

- PCoA1 解释 **33.94%**，PCoA2 解释 **21.07%**，累计 **55.01%**。
- PCoA1 上 L1 明显偏负（约 −0.55），L3 范围较宽（约 −0.40 到 0.20），其余 subject 多在 0.0–0.3。
- PCoA2 上 L1、L5、L6 偏负，L2、L3 偏正；L4 位于中间。
- 这些坐标来自过滤后的 29 个 taxa，不能外推到完整 770-taxa 群落。

### PERMANOVA

- subject 分组：6 组，n=34，999 次置换。
- **F = 8.571，R² = 0.6048，P = 0.001**。
- subject 解释了约 60% 的 Bray-Curtis 距离变异。这个结果符合“同一受试者的重复样本更相似”的预期，但本数据没有 body-site 标签，不能把 R² 解释为 body-site 效应；同时同一受试者的样本并非独立，置换检验的独立性假设并不严格成立。

### 热图

- 20 个高变 taxa 按 subject 平均丰度聚类；列顺序反映样本相似性，行是 taxa。
- 最明显的模式是 L1 与 L4 的分离：Bacteroides（多个 feature）、`s__prausnitzii`、`s__uniformis`、Veillonellaceae 等在 L1 相对富集；L4 则以另一组 taxa 为主。
- L2/L3/L5/L6 的差异主要体现在 Prevotella、Fusobacterium、Neisseriaceae、Dialister 等类群。
- 热图标签使用“最深分类名 + feature hash”，因为 QIIME 2 的 taxonomy 中有大量未分类到属/种、且分类名重复的 feature；hash 保证标签唯一。完整分类谱保留在 `taxonomy.tsv` 来源中，不在图中展开。

## 图

- `output/figures/shannon_by_subject.png`：6 个 subject 的 Shannon 箱线图（过滤 panel 内）。
- `output/figures/pcoa_pc1_by_subject.png`：PCoA1 按 subject。
- `output/figures/pcoa_pc2_by_subject.png`：PCoA2 按 subject。
- `output/figures/top_taxa_by_subject.png`：20 个高变 taxa 的 subject 均值聚类热图。

## 局限

- 没有 body-site 元数据；`subject` 是从样本 ID 前缀派生的，不是独立提供的分组变量。
- 只有一个 QIIME 2 教程表、34 个样本、6 个受试者；L4/L6 只有 3 个样本，组内估计不稳定。
- 过滤阈值（≥10 counts、≥10 samples）是分析选择；不同阈值会改变 taxa 数、alpha 多样性和 PERMANOVA 的 R²。
- `filter_min` 后的 29 个 taxa 不是完整群落；alpha 多样性、Bray-Curtis 和热图都只描述这个过滤 panel。
- 同一受试者的重复样本违反 PERMANOVA 的独立样本假设；这里只作探索性描述，不作因果或临床结论。
- 未做 rarefaction、组成性数据变换、混合模型或重复测量校正；这些会改变推断。
- 本示例用于验证 `BiomReader` + 微生物组算子的组合，不构成生态学或医学结论。

## 复现

在项目根目录：

    python scripts/run.py examples/route_combinations/qiime_moving_pictures_microbiome --check
    python scripts/run.py examples/route_combinations/qiime_moving_pictures_microbiome

运行后在 `output/` 生成 `figures/`、`steps/`、`run_summary.json`。测试会把示例复制到临时目录执行，避免把运行产物写入仓库。
