# PBMC3k 单细胞图谱：H5adReader + 细胞类型分析

本示例用 BioPipe 的 `H5adReader` 读取经典 10x Genomics PBMC3k 单细胞数据，组合
PCA、UMAP、细胞类型聚合、marker 热图和随机森林分类，演示“专用 Reader + 多个
算子的可复现分析”，而不是把 CSV 当成所有数据的入口。

## 数据与来源

- 数据集：10x Genomics PBMC3k（约 2,700 个外周血单个核细胞，健康供者）。
- 处理版本：Scanpy 教程发布的 `pbmc3k_processed()`；本示例保留其
  log-normalized 表达矩阵、细胞注释和 QC 列，不重新做标准化。
- 输入文件：
  - `input/pbmc3k_processed.h5ad`：2,638 个细胞 × 1,838 个高变基因；
    `X` 为 float32，范围约 −2.849 到 10.0，已经是 log1p 归一化值。
  - `input/pbmc3k_cells.csv`：2,638 行，列为
    `sample,cell_type,cell_type_full,n_genes,percent_mito,n_counts`；
    `sample` 与 h5ad 的 `obs` index 一致。
- h5ad 内只保留表达矩阵、`obs` 的四个注释列和 `var` 的 `n_cells`；
  Scanpy 的 `uns`、`obsm`、`varm`、`layers` 未带入，避免把上游降维结果当作本示例结果。
- 数据引用：Wolf, F.A., Angerer, P. & Theis, F.J. (2018).
  SCANPY: large-scale single-cell gene expression data analysis.
  *Genome Biology*, 19, 15. <https://doi.org/10.1186/s13059-017-1382-0>。
- 原始数据：10x Genomics PBMC3k，
  <https://www.10xgenomics.com/datasets/3-k-pbm-cs-from-a-healthy-donor-1-standard-1-1-0>。
  `h5ad` 处理版本来自 Scanpy 公共数据集接口；本示例使用的是该公开处理版本，
  不是重新比对 FASTQ 的原始计数。

### 细胞类型缩写

| `cell_type` | `cell_type_full` | 细胞数 |
|---|---|---:|
| CD4 | CD4 T cells | 1,144 |
| CD8 | CD8 T cells | 316 |
| B | B cells | 342 |
| NK | NK cells | 154 |
| Mono | CD14+ Monocytes | 480 |
| FcR3A | FCGR3A+ Monocytes | 150 |
| DC | Dendritic cells | 37 |
| MK | Megakaryocytes | 15 |

这些标签来自 Scanpy 教程的 Louvain 聚类注释，是**计算注释**，不是独立病理或
流式分选真值。`cell_type_full` 保留完整名称，图中使用短标签以避免横轴重叠。

## 路线（12 步）

`task.yaml` 的 DAG：

1. **`H5adReader`** 读取 `X`，输出 `[sample, gene]`；行标签为细胞 barcode，
   列标签为基因 symbol。
2. **QC 箱线图**：`n_genes` 按 `cell_type` 分组，检查不同注释细胞的检测基因数。
3. **`pca`**：沿 `gene` 维压缩到 20 个主成分；输入矩阵为 log-normalized
   表达，PCA 内部按基因中心化/标准化。
4. **PC1、PC2 箱线图**：按 `cell_type` 展示主成分分布。
5. **`umap`**：在 1,838 个基因上计算二维嵌入，`n_neighbors=15`、
   `min_dist=0.1`、`random_state=17`。
6. **UMAP1、UMAP2 箱线图**：按 `cell_type` 展示嵌入轴分布。
7. **`aggregate`**：沿 `sample` 维按 `cell_type` 取均值，得到
   `[cell_type, gene]` 的细胞类型平均表达。
8. **`rename_dim`**：把聚合结果的 `feature` 维改名为 `cell_type`，使热图轴语义明确。
9. **`heatmap`**：选 16 个 canonical marker genes，按行 z-score，行列聚类，
   展示 8 个细胞类型的 marker 模式。
10. **`random_forest_classifier`**：用全部 1,838 个基因、500 棵树、
    25% 测试集、5 折交叉验证，预测 `cell_type`；没有用标签做特征筛选。
11. **`describe`**：输出分类报告表。

处理中没有再次 `normalize` 或 `log_transform`：输入 `X` 已经是 Scanpy 的
log1p 归一化矩阵，重复归一化会改变数值尺度。需要从原始计数重新走完整单细胞
流程时，应使用 raw counts 并显式加入 `qc_metrics`、`filter_min`、`normalize`、
`log_transform`。

## 结果

### QC：检测基因数

`n_genes` 中位数：

| 细胞类型 | 中位检测基因数 |
|---|---:|
| CD4 | 809 |
| CD8 | 824.5 |
| B | 677 |
| NK | 890 |
| Mono | 859 |
| FcR3A | 1,272 |
| DC | 1,544 |
| MK | 364 |

DC 和 FcR3A 单核细胞的检测基因数较高，MK 较低；这是这份处理后数据的描述性
特征，可能与细胞大小、RNA 含量和上游过滤有关，不能单独解释为细胞状态差异。

### PCA

前 4 个主成分解释方差：

- PC1：**0.017915**（1.79%）
- PC2：**0.014291**（1.43%）
- PC3：0.010369（1.04%）
- PC4：0.007392（0.74%）

单基因维度很大，前几个 PC 的比例看似很低是正常的；PC1/PC2 仍能反映细胞类型
结构。PC1 中位数：CD4 3.30、CD8 3.85、B 1.26、NK 3.21、Mono −9.83、
FcR3A −6.37、DC −3.33、MK −22.38。PC2 中位数：CD4 −0.48、CD8 −0.58、
B 0.37、NK 0.09、Mono 3.22、FcR3A 1.75、DC 0.54、MK −57.06。

MK 数量少（15 个）且在 PC2 上极端，PC2 箱线图的纵轴会被 MK 拉大；因此
PC2 图主要说明 MK 是极端小群，不适合用来比较其余细胞类型之间的细微差异。

### UMAP

UMAP 使用 15 个邻居、`min_dist=0.1`、随机种子 17。UMAP 轴本身没有绝对单位，
箱线图只用于展示各注释细胞在嵌入轴上的分布范围；它不是分类精度的证据，也不能
把 UMAP 距离解释为真实转录组距离。图中 Mono/FcR3A 在 UMAP1 上偏低，MK 在
UMAP2 上偏高，但 CD4/CD8/NK 等群有大量重叠；这说明二维嵌入没有把全部注释
完全分开。

### Marker 热图

热图使用 16 个 canonical markers：

`LTB, MAL, GZMK, CCL5, CD79A, MS4A1, NKG7, GNLY, S100A8, FCN1,
FCGR3A, IFITM3, FCER1A, CST3, PPBP, PF4`

图中可见：

- B 细胞：`CD79A`、`MS4A1` 高；
- NK：`NKG7`、`GNLY` 高；
- CD8：`GZMK`、`CCL5` 较高；
- 单核细胞：`S100A8`、`FCN1`、`FCGR3A`、`IFITM3` 较高；
- DC：`FCER1A`、`CST3` 较高；
- MK：`PPBP`、`PF4` 高。

这些 marker 并非完全互斥：`CCL5` 也见于 NK，`LST1`/`S100A8` 在单核细胞
亚群之间共享，`LTB` 在淋巴细胞中广泛表达。热图用于展示模式，不是诊断性
marker panel。

### 随机森林分类

- 样本：2,638；训练 1,978；测试 660；8 类。
- 特征：全部 1,838 个基因；500 棵树；`scale=true`；随机种子 17。
- 测试集 accuracy：**0.9106**
- macro precision：**0.9400**
- macro recall：**0.7961**
- macro F1：**0.8475**
- macro AUC：**0.9925**
- 5 折 CV：0.9318、0.9116、0.9167、0.9165、0.9165；
  均值 **0.9186 ± 0.0069**。

混淆矩阵（行=true，列=pred；类别顺序 B, CD4, CD8, DC, FcR3A, MK, Mono, NK）：

```
[[86,  0,  0, 0,  0, 0,   0,  0],
 [ 0,277,  8, 0,  1, 0,   0,  0],
 [ 0, 26, 52, 0,  0, 0,   0,  1],
 [ 0,  0,  0, 4,  0, 0,   5,  0],
 [ 0,  0,  0, 0, 25, 0,  12,  0],
 [ 0,  1,  0, 0,  0, 3,   0,  0],
 [ 0,  0,  0, 0,  0, 0, 120,  0],
 [ 0,  0,  5, 0,  0, 0,   0, 34]]
```

主要错误：

- CD8 → CD4：26 个；CD8 测试集 79 个中 52 个正确，recall 约 0.66；
- FcR3A → Mono：12 个；FcR3A 测试集 37 个中 25 个正确；
- DC → Mono：5 个；DC 测试集只有 9 个，估计不稳定；
- NK → CD8：5 个。

Top feature importance：`NKG7` 0.0202、`CD79A` 0.0198、`S100A8` 0.0193、
`TYROBP` 0.0193、`CD79B` 0.0185。重要性是模型内部分裂增益，不是因果效应；
高重要性也不等于 marker 特异性。

## 解释与限制

1. **输入已经是处理后的 h5ad**：`X` 为 Scanpy log1p 归一化值，且只含 1,838 个
   高变基因；本示例没有重新做 counts QC、归一化或 log 转换。因此它验证的是
   `H5adReader` 与下游算子，而不是完整的原始 FASTQ → counts 流程。
2. **注释不是独立真值**：`cell_type` 来自上游 Louvain 聚类注释；随机森林在
   预测这些注释，高 accuracy 部分反映“同一份数据、同一组 HVG、同一套注释”的
   内部一致性，不能当作独立队列的细胞类型识别性能。
3. **类别不平衡**：CD4 占 43%，MK 只有 15 个；macro recall 明显低于 accuracy，
   DC/MK/罕见亚群的测试样本很少，单类指标不稳定。
4. **没有供者重复**：PBMC3k 来自一个健康供者；不能推断人群、疾病或治疗差异。
5. **UMAP 不是统计检验**：UMAP 轴任意，箱线图只是描述性可视化；不同随机种子、
   邻居数或 `min_dist` 会改变布局。
6. **marker panel 非诊断**：16 个 marker 只覆盖主要谱系，不能替代流式/病理
   分型；`FCGR3A`、`S100A8` 等在同一谱系内也有异质性。
7. **没有做差异表达或细胞比例检验**：本示例聚焦 Reader + 结构/分类/可视化；
   细胞类型比例、条件差异需要额外设计（供者、条件、重复）。
8. **数值尺度**：PCA 在基因维中心化/标准化；`aggregate` 对 log-normalized
   值取均值，得到的是“平均 log 表达”，不是原始 counts 的几何均值。

## 复现

在项目根目录：

```bash
python scripts/run.py examples/route_combinations/pbmc3k_single_cell_atlas --check
python scripts/run.py examples/route_combinations/pbmc3k_single_cell_atlas
```

输出写入 `output/`：

- `figures/qc_genes_by_cell_type.png`
- `figures/pca_pc1_by_cell_type.png`
- `figures/pca_pc2_by_cell_type.png`
- `figures/umap1_by_cell_type.png`
- `figures/umap2_by_cell_type.png`
- `figures/cell_type_mean_heatmap.png`
- `steps/*.json`、`run_summary.txt/json`

本示例不新增算子或 Reader；registry 仍为 402 个算子、85 个 Reader、21 条 route。
