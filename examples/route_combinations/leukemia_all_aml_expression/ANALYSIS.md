# Leukemia ALL/AML expression: GCT reader + differential expression + classification

本示例用 GSEA 官方 Leukemia 表达数据验证 `GctReader` 与表达谱算子的组合：读取 GCT、PCA 分组视图、Mann-Whitney 差异检验、BH 校正、显著基因热图，以及在全部基因上训练随机森林区分 ALL/AML。

> 这是方法演示，不是临床诊断或预后结论。数据只有 48 个样本、一个平台，且没有独立验证集。

## 数据来源

- 数据集：GSEA 示例数据 `Leukemia`，48 个样本，24 个 ALL、24 个 AML；10,056 个基因。
- 表达矩阵：`input/Leukemia.gct`，GCT 1.2；样本 ID 为 `ALL_1...ALL_24`、`AML_1...AML_24`。
- 分组：`input/leukemia_samples.csv`，两列 `sample,group`，`group` 取 `ALL` 或 `AML`。
- 来源页面：GSEA Data Sets，<https://www.gsea-msigdb.org/gsea/datasets.jsp>。
- 本示例的实际下载副本来自 GitHub 镜像 `suhasvasaikar/GSEA_PHP` 的 `Leukemia.gct` / `Leukemia.cls`，仅作为传输副本；数据内容按 GSEA 示例页核对。
- 引用：Armstrong, S.A. et al. (2002). MLL translocations specify a distinct gene expression profile that distinguishes a unique leukemia. *Nature Genetics*, 30, 41–47. <https://doi.org/10.1038/ng809>；GSEA 方法见 Subramanian, A. et al. (2005). *PNAS*, 102, 15545–15550. <https://doi.org/10.1073/pnas.0506580102>。

## GCT 与读取语义

`GctReader` 读取 `#1.2` 头、行列数和 `NAME / DESCRIPTION / samples...` 表头，输出维度为 `[sample, gene]`：

- 行是基因，列是样本；读入后转置为样本 × 基因。
- `DESCRIPTION` 列进入 `info["gene_description"]`，不进入数值矩阵。
- 样本 ID 和基因名分别成为 `sample`、`gene` 轴标签。
- 表达值可以是负数；本数据是已归一化的芯片表达值，不是原始 counts。
- 本文件的表达单元格完整：`input/Leukemia.gct` 中没有空的表达值；176 处 `NA` 是基因名/描述中的子串（如 `NAT8`、`PNAS-4`），不是缺失表达值。运行时 `impute` 报告 `no missing values to fill`，与此一致。
- 作为读取层加固，`GctReader` 现在也接受空字符串、`NA`、`na`、`NaN`、`null`、`--` 作为缺失值（NaN）；对应的回归测试在 `tests/test_extension3.py`，本数据不会触发该分支。

## Route

`task.yaml` 共 11 步：

1. `impute`（median，`dim=gene`）：防御性处理缺失；本数据实际无缺失，因此是 no-op。
2. `pca`（`dim=gene`，4 个主成分）：把 10,056 个基因压缩为样本级 PC1–PC4。
3. `boxplot`：PC1 按 `group` 分组。
4. `boxplot`：PC2 按 `group` 分组。
5. `compare_groups`（Mann-Whitney，ALL vs AML，`dim=gene`）：对每个基因做两组秩和检验。
6. `select`：从检验结果中取出 `P` 列。
7. `bh_adjust`：Benjamini-Hochberg FDR，得到 `qvalue`。
8. `filter_by`：保留 `qvalue <= 0.05` 的基因。
9. `heatmap`：在显著基因中按方差取前 40 个，按基因做 row z-score，行列层次聚类。
10. `random_forest_classifier`：在**全部 10,056 个基因**上训练，300 棵树，25% 测试集，5 折 CV；不在随机森林前做标签驱动的基因筛选，避免特征选择泄漏。
11. `describe`：汇总随机森林报告。

为什么没有用 `volcano`：`compare_groups` 同时计算 `log2FC = log2((mean_b + 0.5) / (mean_a + 0.5))`。GCT 表达值有负数，部分基因的组均值接近或低于零，`log2FC` 会变成 NaN 或无生物学意义；运行日志会出现一次 `invalid value encountered in log2` 警告。本 route 只使用 Mann-Whitney 的 `P` 值和 BH `qvalue`，不解释 `log2FC`。这是 `compare_groups` 在“有符号表达值”上的已知限制，不是本数据读取错误。

## 结果

### PCA

解释方差：

| 主成分 | 比例 |
|---|---:|
| PC1 | 20.24% |
| PC2 | 16.59% |
| PC3 | 7.54% |
| PC4 | 4.91% |

PC1 中位数：ALL `-16.81`，AML `24.06`；PC2 中位数：ALL `31.26`，AML `-25.16`。两个主成分都能看到组间分离，但组内仍有明显个体差异；AML 有一个 PC1 约 `-251`、PC2 约 `-157` 的离群样本，均值受其影响，图中位数更稳健。

### 差异表达

- 对 10,056 个基因做 Mann-Whitney 检验，BH 后 **5,261 个基因 q < 0.05**（约 52.3%）。
- 最高显著性的基因 q 值约 `2.72e-6`；这些基因在 ALL 中更高，方向与 ALL 的淋巴/前体细胞表型一致：

| 基因 | q | ALL 均值 | AML 均值 |
|---|---:|---:|---:|
| MYLK | 2.72e-6 | 1099.6 | -173.1 |
| SMARCA4 | 2.72e-6 | 7891.9 | 1537.0 |
| MME | 2.72e-6 | 12545.5 | 1015.3 |
| DNTT | 2.72e-6 | 9477.6 | 20.0 |
| BLNK | 2.72e-6 | 8255.0 | 83.1 |
| POU2AF1 | 2.72e-6 | 4616.3 | -4.8 |
| TCL1A | 2.72e-6 | 21442.5 | 658.5 |
| CD24 | 2.72e-6 | 13183.7 | 694.9 |
| ZNF423 | 2.72e-6 | 1194.5 | -187.4 |
| CD79B | 2.72e-6 | 8618.7 | -454.5 |

`DNTT`、`CD24`、`CD79B`、`BLNK`、`POU2AF1`、`TCL1A` 等 ALL 高表达基因与 B 细胞/淋巴前体程序相符；但这里只做描述性差异分析，没有校正批次、没有独立验证，不能据此作诊断或机制结论。

### 随机森林

- 样本 48，特征 10,056；训练 36、测试 12；5 折 CV。
- 测试集 accuracy / macro precision / macro recall / macro F1 / AUC 均为 `1.0000`，混淆矩阵 `[[6, 0], [0, 6]]`。
- CV accuracy `0.9714 ± 0.0571`（各折 `1.0, 1.0, 1.0, 0.8571, 1.0`）。
- 重要性最高的特征：`TCFL5` 0.0200、`NPY` 0.0167、`MYLK` 0.0167、`PSD3` 0.0123、`POU2AF1` 0.0100。
- 测试集只有 12 个样本；完美准确率不能当作泛化能力证据。这里没有在随机森林前用 q 值筛基因，避免了最直接的标签泄漏；但同一份 48 个样本仍同时用于调参/描述，CV 也可能偏乐观。

### 热图

`output/figures/top_significant_genes.png` 展示 5,261 个 FDR 显著基因中方差最大的 40 个，按基因 row z-score，行列均聚类：

- 样本大致分为 ALL 与 AML 两个块，和 PCA 的分组一致。
- 行标签保留基因名，可看到 HLA 区域基因（如 `HLA-C /// HLA-B`、`HLA-DPB1`）、核糖体蛋白基因（`RPL*`、`RPS*`）以及免疫/髓系相关基因（如 `IGHM`、`CD79A`、`MPO`、`ELA2`）。
- 这是“显著基因中方差最大的 40 个”，不是按效应量排序的 top 40；热图用于看整体结构与样本聚类，不替代差异统计。

## 图

- `output/figures/pca_pc1_by_group.png`：PC1 箱线图，组标签为 ALL/AML。
- `output/figures/pca_pc2_by_group.png`：PC2 箱线图。
- `output/figures/top_significant_genes.png`：FDR 显著基因中 top-variance 40 个基因的热图。

## 局限

- 48 个样本、单一 GSEA 示例数据集；ALL/AML 是强分离的经典教学数据，结果不代表其他队列。
- 没有独立测试集；随机森林的 12 个测试样本和 5 折 CV 都在同一小数据内。
- `compare_groups` 的 `log2FC` 对有符号 GCT 值无意义；本分析有意不使用它。Mann-Whitney 的 P 值仍有效，但 BH 假设检验之间独立或正相关，基因间强相关时 FDR 只是近似。
- 没有做批次校正、标准化方法比较、特征稳定性选择或外部验证。
- 没有临床结局、治疗信息或生存时间；不能从 ALL/AML 分类推导预后或治疗建议。
- 热图的行聚类和样本聚类是描述性的，不是正式聚类显著性检验。

## 复现

在仓库根目录：

```bash
python scripts/run.py examples/route_combinations/leukemia_all_aml_expression --check
python scripts/run.py examples/route_combinations/leukemia_all_aml_expression
```

只读校验不写 `output/`；完整运行写入该示例的 `output/figures/`、`output/steps/`、`output/run_summary.{txt,json}`。运行环境需要 `scikit-learn`、`scipy`、`numpy`、`pandas`、`matplotlib`（BioPipe 的常规依赖）。
