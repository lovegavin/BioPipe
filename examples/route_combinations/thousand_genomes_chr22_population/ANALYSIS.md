# 1000 Genomes chr22 群体结构示例

本示例用 BioPipe 的 `VcfReader` 读取一段真实的 1000 Genomes Phase 3 VCF，组合变异质控、PCA、Hudson FST 与基因组亲缘关系矩阵（GRM），演示“专用 Reader + 多个算子”的可复现群体遗传学分析。示例只使用已有 Reader 与算子，不新增注册项。

## 数据来源

- 项目：1000 Genomes Project Phase 3（20130502 释放版），人类参考基因组 GRCh37。
- 原始文件：`ALL.chr22.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz`，来自 EBI FTP：
  <https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/>。
- 样本面板：`integrated_call_samples_v3.20130502.ALL.panel`，包含 2504 个样本的 `pop`、`super_pop` 与 `gender`。
- 本示例为控制文件体积，固定选取 100 个样本，每个 super-population 20 个（AFR/AMR/EAS/EUR/SAS），并把区间限制在 chr22:16,000,000–16,200,000（GRCh37，约 200 kb）。样本清单保存在 `input/kg_samples.csv`，不是随机抽样。
- 引用：1000 Genomes Project Consortium et al. (2015). A global reference for human genetic variation. *Nature*, 526, 68–74. <https://doi.org/10.1038/nature15393>。

## 文件

- `input/kg_chr22_region.vcf`：100 个样本、1,663 个 VCF 记录；`VcfReader` 把多等位记录拆成 ALT 等位基因行，缺失基因型为 NaN；本区间所有样本基因型完整、ploidy=2。
- `input/kg_samples.csv`：100 行 × 3 列（`sample`、`pop`、`super_pop`），用于分组；`gender` 未进入本示例分析。
- `task.yaml`：13 步的扁平 DAG。
- `output/`：运行后生成；不纳入版本库。

## 质量控制

1. **MAF ≥ 0.05**：1,663 → 109 个变异（移除 1,554 个低频/单例变异）。
2. **缺失率 ≤ 0.10**：109 → 109（本区间无缺失基因型）。
3. **HWE p ≥ 1×10⁻⁶**：109 → 97（移除 12 个严重偏离 HWE 的变异）。

最终用于 PCA、FST 和 GRM 的是 **97 个变异 × 100 个样本**。这些阈值是为了让示例在小文件上可读，不是群体遗传学的最佳实践；真实分析应做 LD 修剪、分层质控和更多敏感性分析。

## 路线

1. `maf`：按 `variant` 维过滤 MAF。
2. `missing`：按缺失率过滤。
3. `hwe`：按 HWE 精确检验 p 值过滤。
4. `describe`：记录 QC 后矩阵形状。
5. `pca`：对 97 个变异做 PCA，保留 4 个主成分；输入维度 `variant` 被压缩为 `sample` 分数。
6. `boxplot`：PC1 按 `super_pop` 分组（AFR/AMR/EAS/EUR/SAS）。
7. `boxplot`：PC2 按同一分组。
8. `fst`：Hudson FST，AFR vs EUR，每个变异输出 `fst/n_a/n_b/p_a/p_b`。
9. `histogram`：97 个 FST 值的分布。
10. `relatedness`：用 97 个变异计算 100×100 GRM（`min_maf=0.05`）。
11. `rename_dim`：把 GRM 的 `sample` 改为 `individual_1`。
12. `rename_dim`：把 `sample_b` 改为 `individual_2`。
13. `heatmap`：聚类行/列，隐藏 100 个样本标签，展示亲缘关系块结构。

`VcfReader` 的 GT 被编码为 ALT 等位基因剂量（0/1/2），多 ALT 记录拆成多个变异行；因此 1,663 是 Reader 展开后的变异行数，不等同于原始 VCF 的记录数。

## 结果

### PCA

四个主成分解释方差：

| 成分 | 解释方差 |
|---|---:|
| PC1 | 0.159860 |
| PC2 | 0.117049 |
| PC3 | 0.083304 |
| PC4 | 0.061562 |

PC1+PC2 合计约 **27.69%**，四个成分合计约 **42.18%**。各 super-population 的 PC 中位数：

| 群体 | PC1 中位数 | PC2 中位数 |
|---|---:|---:|
| AFR | -1.138 | 2.478 |
| AMR | -1.940 | 0.795 |
| EAS | -1.965 | -3.145 |
| EUR | -1.136 | 0.037 |
| SAS | -0.080 | 1.228 |

PC1 没有把五个群体干净分开；PC2 上 EAS 明显偏低、AFR 偏高，但组内离散度很大。这个区间只有 97 个变异，且未做 LD 修剪，PCA 只能作为描述性结构检查，不能当作祖源判定或群体分类器。

### Hudson FST（AFR vs EUR）

- 变异数：97；AFR 20 个样本，EUR 20 个样本。
- 平均 FST：**0.008607**。
- 直方图范围：**-0.052632 到 0.258373**；标准差 **0.056678**。
- 多数变异接近 0，少数位点有较高分化；Hudson 估计量在无分化时可出现负值，这是估计量的性质，不是错误。
- 这是单个 200 kb 窗口的描述性结果，不能外推到全基因组或所有 AFR/EUR 群体。

### 基因组亲缘关系（GRM）

- 矩阵：100×100；使用 97 个变异，`min_maf=0.05`。
- 对角线均值：**1.005047**（估计量下略高于 1，属正常数值现象）。
- 热图显示若干对角块和个体间相关结构；但没有把 super-population 作为行/列注释，因此不能从图直接判断群体归属，也不做亲子/同胞判定。
- GRM 使用未修剪的 LD 变异，相关值会受 LD 影响；真实亲缘分析应做 LD 修剪并校正群体结构。

## 图

- `output/figures/pca_pc1_by_superpopulation.png`：PC1 箱线图，按五个 super-population 分组；展示中位数、四分位数、须和离群点。
- `output/figures/pca_pc2_by_superpopulation.png`：PC2 箱线图；EAS 与 AFR 的分布差异比 PC1 更明显。
- `output/figures/fst_afr_eur_histogram.png`：97 个 Hudson FST 的 30-bin 直方图；可见大量接近 0 的值和右尾高分位点。
- `output/figures/relatedness_heatmap.png`：100×100 GRM 热图，行列聚类、隐藏样本标签；块结构只作描述。

## 解释与限制

- 这是**一个 200 kb 窗口、100 个样本、97 个变异**的演示，不是全基因组群体遗传学分析，也不构成任何群体/个体的生物学或医学结论。
- 样本按 super-population 固定取 20 个，不能代表 1000 Genomes 的全部样本；群体内变异远大于示例所示的组间差异。
- MAF/HWE/缺失阈值会改变结果；FST 对低频变异和样本量敏感，未计算置信区间。
- PCA 未做 LD 修剪；相关变异会重复计权，主成分方向可能随变异集变化。
- GRM 热图没有群体注释，不能单独用于祖源推断或亲缘关系判定。
- `VcfReader` 只读取硬基因型；本示例不分析定相、结构变异、CNV 或基因型质量。
- 这些图用于验证 Reader 与算子组合的可运行性和可解释性，不用于临床、法医或群体分类。

## 复现

在项目根目录：

```bash
python scripts/run.py examples/route_combinations/thousand_genomes_chr22_population --check
python scripts/run.py examples/route_combinations/thousand_genomes_chr22_population
```

运行后在 `output/` 下生成四张图和逐步 JSON 摘要；`output/` 已被忽略，不应提交。
