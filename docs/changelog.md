# 更新记录

## 0.21.0 — 2026-10-31
- 新增 8 个算子：Storey q-value、DeLong AUC、Dunn 检验、决策曲线、有序 logistic、线性混合模型、Hosmer-Lemeshow、Stuart-Maxwell。
- 当前：216 算子 / 80 Reader / 21 route；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension14.py` 8 项、`tests/test_r_oracles6.py` 2 项，新增 **10 passed**；增量门 **26 passed**，`-W error` 下 **12 passed**；R 对照 pROC/dunn.test/dcurves/MASS/lme4/ResourceSelection/DescTools；registry clean；参考页 216/80；Studio 前端 **162 passed**。
- 未新增 Reader：`flowCore` 因 `cytolib` 编译失败、`sangerseqR` 未安装，FCS/AB1 暂缓。
- 边界：Storey 固定 lambda；DeLong 正态近似；Dunn 标准 Holm；决策曲线 0.01–0.99；有序 logistic/logit-probit；LMM 随机截距；HL 唯一分位数切点；Stuart-Maxwell 移除等边际类别。

## 0.20.0 — 2026-10-31
- 新增 8 个算子：Cohen's kappa、Fleiss' kappa、Breusch-Pagan、Durbin-Watson、Egger 回归检验、ANOSIM、Procrustes、偏 Mantel。
- 新增 4 个 Reader：mzIdentML、pepXML、mzDATA、protXML；MGF 空峰谱修复沿用 0.19。
- 当前：208 算子 / 80 Reader / 21 route；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension13.py` 6 项、`tests/test_extension13_readers.py` 5 项、`tests/test_r_oracles5.py` 1 项，新增 **12 passed**；R 对照 vegan/lm，Python 对照 statsmodels；registry clean；参考页 208/80；增量门 **28 passed**，`-W error` 下 **14 passed**；Studio 前端 **154 passed**。
- 边界：kappa 支持无权重/线性/二次；Fleiss 支持 fleiss/randolph；ANOSIM/Procrustes/偏 Mantel 采用 vegan 语义；质谱 Reader 只输出摘要字段，不展开原始峰。

## 0.19.0 — 2026-10-30
- 新增 7 个算子：TMM 归一化、limma 风格批次效应移除、Mantel-Haenszel、Cochran-Armitage 趋势、TOST 等价检验、Bland-Altman、竞争风险累积发生率。
- 新增 3 个 Reader：mzML、mzXML、mzTab；修复 MGF 空峰谱 precursor 丢失。
- 当前：200 算子 / 76 Reader / 21 route；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension12.py` 7 项、`tests/test_extension12_readers.py` 4 项、`tests/test_r_oracles4.py` 6 项，新增 **17 passed**；增量门 **42 passed**；R 对照 edgeR/limma/mantelhaen.test/prop.trend.test/t.test/survfit；registry clean；参考页 200/76；Studio 前端 **146 passed**。
- 边界：TMM 采用 edgeR 的 f75 参考与 trimmed weighted mean；批次校正采用 sum-to-zero 编码；Mantel-Haenszel 默认不做连续性校正；Cochran-Armitage 使用等距 scores；TOST 支持 Welch/pooled；Bland-Altman 使用正态近似 LoA；CIF 为 Aalen-Johansen，事件 0/1/2；mzML/mzXML/mzTab 只输出摘要，不展开原始峰列表。

## 0.18.0 — 2026-10-30
- 新增 14 个算子：反向互补、翻译、密码子使用、限制性酶切位点、蛋白性质；PCA loadings、HVG、细胞周期评分、Hudson Fst、GRM 亲缘矩阵、RMST、peptide q-value、McNemar、Kendall tau。
- 新增 10 个 Reader：FAM、BIM、HapMap、MOL、XYZ、GRO、PSL、genePred、MGF、HMMER domtbl。
- 当前：193 算子 / 73 Reader / 21 route；未修改核心层。
- 验证：增量 `tests/test_extension11.py` 9 项 + R `cor.test(kendall)` oracle 6 项全部通过；全量 pytest **606 passed / 1 skipped**（唯一 skip 为增量门 full-suite 模式分支）；registry clean；参考页 193/73；Studio 前端 **139 passed**，构建通过。
- 边界：翻译使用标准遗传密码、不支持线粒体/非标准密码表；限制性酶切位点只做精确 motif 计数；蛋白 pI/MW 为常用近似；HVG 基于均值-离散度；Fst 使用 Hudson 估计；RMST 需组列且基于 KM；peptide q-value 使用 target-decoy；McNemar 默认连续性校正；Kendall 为成对完整观测；HapMap 以首个非缺失等位基因为参考；MOL2/PDB 不重建键级；PSL/genePred 只解析常用字段。

BioPipe 使用语义化版本和 git tag。当前源码版本：**0.21.0（2026-10-31）**。
更早版本从 git tag/history 查；本页只保留当前版本摘要。

## 0.17.0 — 2026-10-30
- 新增 12 个算子：Holm、Benjamini-Yekutieli、Cohen's d/Hedges g、Cliff's delta、η²、rank-biserial、Davies-Bouldin、Calinski-Harabasz、ARI、混淆矩阵、ROC 曲线、Mann-Kendall。
- 新增 8 个 Reader：BLAST tabular、HMMER tblout、InterProScan、EMBL、HMM、MOL2、SMI、bedMethyl。
- 当前：179 算子 / 63 Reader / 21 route；未修改核心层。
- 验证：按用户要求只跑增量 **11 passed**（`tests/test_extension10.py` 10 项 + R `p.adjust` oracle 1 项），未重跑全量；registry clean；参考页 179/63；Studio 前端 **125 passed**。
- 边界：Holm/BY 对 NaN p 保留 NaN；效应量只支持连续特征；Mann-Kendall 使用 tie-corrected 正态近似；聚类标签编号不稳定；SMI 的重原子计数为近似值；MOL2 不重建键级；bedMethyl 仅解析 15 列常用字段。

## 0.16.0 — 2026-10-30
- 新增 9 个算子：DBSCAN、层次聚类、GMM、孤立森林、Cramér–von Mises、Welch ANOVA、Tukey HSD、C-index、二分类指标。
- 新增 6 个 Reader：WIG、broadPeak、GFF2、mmCIF、OBO、SDF。
- 当前：167 算子 / 55 Reader / 21 route；未修改核心层。
- 验证：按用户要求只跑 **增量测试 12 passed**（`tests/test_extension9.py`），未重跑全量；registry clean；参考页 167/55；Studio 前端 **113 passed**。
- 边界：聚类标签不稳定；Cramér–von Mises 仅两组；Welch ANOVA/Tukey HSD 至少三组；C-index 的 risk 越高表示风险越大；分类指标仅二分类；GFF Reader 使用 `.gff2` 避免与 Gff3Reader 冲突；WIG/broadPeak 0-based；mmCIF 仅 atom_site；OBO 仅 Term；SDF 不重建键图。

## 0.15.0 — 2026-10-30
- 新增 6 个算子：Mantel 检验、PLS 回归、分位数回归、bootstrap 置信区间、silhouette、互信息。
- 新增 4 个 Reader：GenBank、PDB、Zarr、BCF。
- 当前：158 算子 / 49 Reader / 21 route；未修改核心层。
- 验证：**560 passed / 0 skipped**（2026-10-30）；registry clean；参考页 158/49；新增测试 `tests/test_extension8.py` 8 项；Studio 前端 **104 passed**。
- 边界：Mantel 使用 Pearson 相关 + 置换，p 的分辨率为 `1/(n_perm+1)`；PLS 对单目标暴露一维 `coef_` 适配器；分位数回归使用 sklearn `QuantileRegressor`（无 `max_iter`）；bootstrap 为 percentile CI；GenBank/PDB 为常用子集解析；Zarr 只接受 2D 数值数组；BCF 需 pysam，原生 Windows 不可用（见 [Windows 兼容性](windows_compatibility.md)）。

## 0.14.0 — 2026-10-30
- 新增 8 个算子和 5 个 Reader：距离相关、偏相关、VIF、分位数/幂变换、稳健缩放、缩尾、秩变换；BAM、CRAM、BigWig、PED、GFA。
- 当前：152 算子 / 45 Reader / 21 route；未修改核心层。
- 验证：**552 passed / 0 skipped**（2026-10-30）；registry clean；参考页 152/45；新增测试 `tests/test_extension7.py` 8 项；Studio 前端 **98 passed**。
- 边界：BAM/CRAM 只暴露常用字段；CRAM 必须提供 reference；PED dosage 不含参考等位基因；BigWig 只读取区间值；GFA 只读取 S 段；距离相关不提供 p 值；VIF 对完全共线特征返回 inf。

## 0.13.0 — 2026-10-30
- 新增 6 个统计算子：KS 两样本、Brunner-Munzel、Fligner-Killeen、置换检验、符号检验、Jarque-Bera。
- 当前：144 算子 / 40 Reader / 21 route；未修改核心层。
- 验证：**544 passed / 0 skipped**（2026-10-30）；registry clean；参考页 144/40；新增测试 `tests/test_extension6.py` 4 项；Studio 前端 **90 passed**。
- 边界：K-S/置换检验的 p 值基于有限重采样或渐近近似；Fligner-Killeen 依赖 scipy 当前版本 API。

## 0.12.0 — 2026-10-30
- 新增 6 个算子：UMAP、配对 t 检验、单样本 t 检验、z-score、min-max 缩放、softmax。
- 新增 2 个 Reader：MAF、UCSC chain。
- 当前：138 算子 / 40 Reader / 21 route；未修改核心层。
- 验证：**540 passed / 0 skipped**（2026-10-30）；registry clean；参考页 138/40；新增测试 `tests/test_extension5.py` 6 项；Studio 前端 **84 passed**。
- 边界：UMAP 依赖 umap-learn；z-score 是 axis-wise 便捷算子，与既有 `scale_features` 有功能重叠；MAF/chain 只校验固定列/头，不验证完整规范。

## 0.11.0 — 2026-10-30
- 新增 10 个算子：谱嵌入、LLE、Gaussian 随机投影、主题 LDA、Wilcoxon、Friedman、Bartlett、Normaltest、Bonferroni、Fisher 合并 p 值。
- 新增 6 个 Reader：PAF、SAM、BEDPE、cytoband、Clustal、NEXUS。
- 当前：132 算子 / 38 Reader / 21 route；未修改核心层，扩展仍通过声明和生成式 registry 完成。
- 验证：**534 passed / 0 skipped**（2026-10-30）；registry clean；参考页 132/38；新增测试 `tests/test_extension4.py` 9 项；Studio 前端 **78 passed**。

## 0.10.0 — 2026-10-29
- 新增 31 个算子：线性/弹性网/贝叶斯岭/Huber/Theil-Sen 回归，Kernel PCA、Truncated SVD、因子分析、MDS、Isomap、BH FDR、Mann-Whitney，以及 11 个树模型/朴素贝叶斯/判别分析/随机梯度模型。
- 新增 13 个 Reader：Excel、GCT、bedGraph、narrowPeak、NumPy、JSON 表、FAI、FASTQ、HDF5、PLINK MAP、PHYLIP、Newick、Stockholm。
- 当前：122 算子 / 32 Reader / 21 route；全部严格 schema/contracts；未修改核心层。
- 验证：**525 passed / 0 skipped**（2026-10-29）；参考页生成检查；registry clean；新增算子/Reader 测试 31 个，Excel/HDF5/Newick 等边界单独覆盖。

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
