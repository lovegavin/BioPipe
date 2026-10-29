# BioPipe SOP 验证矩阵
本文件由 `src/task`/`src/reader` 与测试引用自动生成；每次新增 Reader/算子或测试后重跑生成脚本。

当前基线：全量 pytest **534 passed / 0 skipped**；独立 SOP **29** 个；14 个 verify 脚本、49 个 demo 自测通过。

## 1. 分级
| 级别 | 含义 |
|---|---|
| S | 独立的 SOP 测试（不依赖旧 verify/demo；外部库/手算/独立解析器逐值对比） |
| A | 主题验证脚本：外部权威值、独立实现或数学不变量 |
| B | 算子 demo 自测：手工可算的小例子 |
| C | 仅契约/route/artifact 覆盖；没有独立数值 oracle |

## 2. Reader（38）
| Reader | 级别 | 证据/独立 oracle |
|---|---|---|
| `BedReader` | S | test_readers_sop.py / test_genotype_readers_sop.py |
| `BgenReader` | S | test_readers_sop.py / test_genotype_readers_sop.py |
| `CsvReader` | S | test_readers_sop.py / test_genotype_readers_sop.py |
| `FastaReader` | S | test_readers_sop.py / test_genotype_readers_sop.py |
| `GafReader` | S | test_readers_sop.py / test_genotype_readers_sop.py |
| `Gff3Reader` | S | test_readers_sop.py / test_genotype_readers_sop.py |
| `GtfReader` | S | test_readers_sop.py / test_genotype_readers_sop.py |
| `H5adReader` | S | test_readers_sop.py / test_genotype_readers_sop.py |
| `MtxReader` | S | test_readers_sop.py / test_genotype_readers_sop.py |
| `ParquetReader` | S | test_readers_sop.py / test_genotype_readers_sop.py |
| `Plink1Reader` | S | test_readers_sop.py / test_genotype_readers_sop.py |
| `Plink2Reader` | S | test_readers_sop.py / test_genotype_readers_sop.py |
| `TenxH5Reader` | S | test_readers_sop.py / test_genotype_readers_sop.py |
| `TsvReader` | S | test_readers_sop.py / test_genotype_readers_sop.py |
| `TxtReader` | S | test_readers_sop.py / test_genotype_readers_sop.py |
| `VcfReader` | S | test_readers_sop.py / test_genotype_readers_sop.py |
| `GmtReader` | B | test_new_readers.py（GMT 手写解析、集合成员/重复集合） |
| `LoomReader` | B | test_new_readers.py（HDF5 matrix/row_attrs/col_attrs） |
| `BiomReader` | B | test_new_readers.py（标准 BIOM：行=观测、列=样本；JSON 与 HDF5 布局一致） |
| `ExcelReader` | B | test_extension3.py（openpyxl 往返） |
| `GctReader` | B | test_extension3.py（GCT 1.2/1.3 方向） |
| `BedGraphReader` | B | test_extension3.py（4 列区域） |
| `NarrowPeakReader` | B | test_extension3.py（10 列 peak） |
| `NpyReader` | B | test_extension3.py（NPZ 数组） |
| `JsonTableReader` | B | test_extension3.py（records/columns） |
| `FaiReader` | B | test_extension3.py（FAI 5 列） |
| `FastqReader` | B | test_extension3b.py（FASTQ 质量） |
| `H5Reader` | B | test_extension3b.py（2D HDF5） |
| `MapReader` | B | test_extension3b.py（PLINK MAP） |
| `PhylipReader` | B | test_extension3b.py（PHYLIP） |
| `NewickReader` | B | test_extension3b.py（Newick 树） |
| `StockholmReader` | B | test_extension3b.py（Stockholm） |
| `PafReader` | B | test_extension4.py（12 列 PAF） |
| `SamReader` | B | test_extension4.py（11 列 SAM） |
| `BedpeReader` | B | test_extension4.py（10 列 BEDPE） |
| `CytobandReader` | B | test_extension4.py（5 列 cytoband） |
| `ClustalReader` | B | test_extension4.py（Clustal 对齐） |
| `NexusReader` | B | test_extension4.py（NEXUS MATRIX） |

Reader SOP 覆盖：CSV/TSV/TXT/Parquet → pandas；BED/GFF3/GTF → 手写解析 + 边界；FASTA → 手写解析 + NCBI 长度/GC；GAF → 手写解析；MTX → scipy.io.mmread；H5AD/10x H5 → h5py；VCF → pysam；PLINK1 → bed_reader；PLINK2 → pgenlib；BGEN → bgen_reader。
## 3. Operator（132；下表为 89 个早期算子，0.8–0.11 新增见末尾证据）
| Operator | 包 | 级别 | 证据 |
|---|---|---|---|
| `aggregate` | biopipe-microbiome | A | verify_transform_operators.py |
| `annotate` | biopipe-core | A | verify_transform_operators.py |
| `annotation_gaps` | biopipe-core | A | verify_gtf_annotation.py, verify_operators.py |
| `attach_info` | biopipe-core | A | verify_transform_operators.py |
| `barplot` | biopipe-microbiome | B | test_barplot.py |
| `bin` | biopipe-core | A | verify_transform_operators.py |
| `boxplot` | biopipe-plots | C | test_builtin_routes.py route artifact |
| `cluster_axis` | biopipe-core | A | verify_single_cell.py, verify_stats_operators.py |
| `combat` | biopipe-core | B | test_extension2_operators.py, single_cell_batch route |
| `compare_groups` | biopipe-expression | A | verify_existing_operators.py |
| `concat` | biopipe-core | S | tests/sop + verify_transform_operators.py, test_core_operators_sop.py |
| `correction` | biopipe-genetics | A | verify_existing_operators.py |
| `correlation` | biopipe-microbiome | A | verify_existing_operators.py |
| `cox_regression` | biopipe-expression | A | verify_stats_operators.py |
| `describe` | biopipe-core | B | test_contracts.py, test_memory_runtime.py |
| `distance_matrix` | biopipe-microbiome | A | verify_existing_operators.py |
| `diversity` | biopipe-microbiome | A | verify_existing_operators.py |
| `dotplot` | biopipe-plots | B | test_dotplot.py |
| `drop` | biopipe-core | S | tests/sop + verify_transform_operators.py, test_core_operators_sop.py |
| `enrich_go` | biopipe-core | A | verify_go_enrichment.py, verify_stats_operators.py |
| `enrichment_plot` | biopipe-core | B | test_enrichment_plot.py + test_plot_artifacts_sop.py |
| `explode` | biopipe-core | A | verify_transform_operators.py |
| `filter_by` | biopipe-core | S | tests/sop + test_filter_by.py, test_single_cell_route.py, verify_single_cell.py, verify_transform_operators.py, test_core_operators_sop.py |
| `filter_min` | biopipe-expression | S | tests/sop + test_single_cell_route.py, verify_existing_operators.py, verify_single_cell.py, test_core_operators_sop.py |
| `find_orfs` | biopipe-core | A | verify_operators.py, verify_sequence_features.py |
| `forest_plot` | biopipe-plots | C | test_builtin_routes.py route artifact |
| `gc_skew_profile` | biopipe-core | A | verify_operators.py |
| `gene_list_to_hits` | biopipe-core | A | verify_go_enrichment.py |
| `gene_structure` | biopipe-core | A | verify_gtf_annotation.py, verify_operators.py |
| `gff_feature_stats` | biopipe-core | A | verify_gtf_annotation.py, verify_operators.py |
| `gradient_boosting_classifier` | biopipe-core | A | verify_ml_classification.py |
| `gradient_boosting_regressor` | biopipe-core | A | verify_ml_regression.py |
| `heatmap` | biopipe-plots | C | test_builtin_routes.py route artifact |
| `histogram` | biopipe-plots | C | test_builtin_routes.py route artifact |
| `hwe` | biopipe-genetics | A | verify_genetics_operators.py |
| `impute` | biopipe-expression | A | verify_existing_operators.py, verify_ml_classification.py, verify_ml_regression.py |
| `interval_merge` | biopipe-core | A | verify_interval_analysis.py, verify_operators.py |
| `interval_overlap` | biopipe-core | A | verify_interval_analysis.py, verify_operators.py |
| `interval_stats` | biopipe-core | A | verify_interval_analysis.py, verify_operators.py |
| `join` | biopipe-microbiome | A | verify_multi_omics.py, verify_transform_operators.py |
| `kaplan_meier` | biopipe-plots | C | test_builtin_routes.py route artifact |
| `kmer_count` | biopipe-core | A | verify_operators.py |
| `lasso_regression` | biopipe-core | A | verify_ml_regression.py |
| `ld_prune` | biopipe-genetics | A | verify_bgen_qc.py, verify_genetics_operators.py |
| `line` | biopipe-plots | C | test_builtin_routes.py route artifact + test_plot_artifacts_sop.py |
| `linear_regression` | biopipe-core | A | verify_ml_regression.py |
| `log_transform` | biopipe-expression | S | tests/sop + test_ml_classification.py, test_ml_regression.py, test_multi_omics_route.py, test_single_cell_route.py, verify_existing_operators.py, verify_ml_classification.py, verify_ml_regression.py, verify_multi_omics.py, verify_single_cell.py, test_core_operators_sop.py |
| `logistic_regression` | biopipe-core | A | verify_ml_classification.py |
| `logrank_test` | biopipe-expression | A | verify_stats_operators.py |
| `ma_plot` | biopipe-plots | C | test_builtin_routes.py route artifact |
| `maf` | biopipe-genetics | A | verify_bgen_qc.py, verify_genetics_operators.py |
| `manhattan` | biopipe-plots | C | test_builtin_routes.py route artifact |
| `missing` | biopipe-genetics | A | verify_bgen_qc.py, verify_existing_operators.py, verify_ml_classification.py, verify_ml_regression.py |
| `motif_scan` | biopipe-core | A | verify_sequence_features.py |
| `normalize` | biopipe-expression | S | tests/sop + test_ml_classification.py, test_ml_regression.py, test_multi_omics_route.py, test_single_cell_route.py, verify_existing_operators.py, verify_ml_classification.py, verify_ml_regression.py, verify_multi_omics.py, verify_single_cell.py, test_core_operators_sop.py |
| `order_axis` | biopipe-core | A | verify_transform_operators.py |
| `pca` | biopipe-genetics | A | verify_bgen_qc.py, verify_existing_operators.py, verify_multi_omics.py |
| `peak_nearest_gene` | biopipe-core | A | verify_operators.py |
| `permanova` | biopipe-microbiome | A | verify_stats_operators.py |
| `pivot` | biopipe-core | A | verify_go_enrichment.py, verify_transform_operators.py |
| `prioritize` | biopipe-core | A | verify_transform_operators.py |
| `qc_metrics` | biopipe-core | S | tests/sop + test_qc_metrics.py, test_single_cell_route.py, verify_operators.py, verify_single_cell.py, test_core_operators_sop.py |
| `random_forest_classifier` | biopipe-core | A | verify_ml_classification.py |
| `random_forest_regressor` | biopipe-core | A | verify_ml_regression.py |
| `rank_axis` | biopipe-core | A | verify_existing_operators.py, verify_multi_omics.py, verify_single_cell.py |
| `reduce` | biopipe-microbiome | A | verify_single_cell.py, verify_stats_operators.py |
| `reduce_axis` | biopipe-core | A | verify_existing_operators.py |
| `regress` | biopipe-genetics | A | verify_genetics_operators.py |
| `rename_dim` | biopipe-core | S | tests/sop + verify_transform_operators.py, test_core_operators_sop.py |
| `ridge_regression` | biopipe-core | A | verify_ml_regression.py |
| `scale_features` | biopipe-core | S | tests/sop + test_scale_features.py, verify_operators.py, test_core_operators_sop.py |
| `scatter` | biopipe-plots | C | test_builtin_routes.py route artifact |
| `select` | biopipe-core | S | tests/sop + verify_transform_operators.py, test_core_operators_sop.py |
| `sequence_stats` | biopipe-core | A | verify_operators.py, verify_sequence_features.py |
| `svm_classifier` | biopipe-core | A | verify_ml_classification.py |
| `svm_regressor` | biopipe-core | B | test_ml_regression.py |
| `ssgsea` | biopipe-expression | A | test_ssgsea_matches_r_gsva (R GSVA 1.28), rnaseq_ssgsea route |
| R oracle（GSVA） | A | `test_ssgsea_matches_r_gsva` 与 `GSVA::gsva(ssgseaParam(...))` 逐值对拍；R/GSVA 缺失时 skip |
| `transpose` | biopipe-core | S | tests/sop + test_ml_classification.py, test_ml_regression.py, verify_ml_classification.py, verify_ml_regression.py, verify_transform_operators.py, test_core_operators_sop.py |
| `violin` | biopipe-plots | B | test_violin.py |
| `volcano` | biopipe-plots | C | test_builtin_routes.py route artifact |

## 4. Route 端到端
- 21/21 route graph 通过 `test_all_shipped_route_graphs_compile` 编译。
- 21/21 route 由 `test_each_shipped_route_executes_repository_fixture` 用仓库内 fixture 实际执行到全部输出；5 条 0.8.0 route 另有 `test_extension_routes.py` smoke test，2 条 0.9.0 route 由同一 fixture 测试覆盖。
- 49/49 demo 测试通过。
- 原“9 条旧 route 无 pytest fixture”的缺口已关闭；Multi-omics 在相关矩阵前增加 `rank_axis(top_n=500)`，避免 5247×5247 超限。

## 5. 缺口
- 10 个 C 级绘图算子由 route 的 PNG artifact 覆盖；line/enrichment 另有直接 artifact 测试；绘图无数值契约，不设数值 oracle。
- C 级且非绘图：无。
- 运行中的 skip：无；全量 pytest 为 **534 passed / 0 skipped**。桌面测试在 `frontend/dist` 存在时执行，route fixture 已全部接入。

## 6. 复现命令
```bash
python -m pytest -q                    # 全量单元/契约/route
python -m pytest -q tests/sop          # 独立 SOP
python -m biopipe registry check       # 注册表
for f in tasks/verify_*.py; do python "$f"; done
for f in tasks/*_demo/test_*.py; do python "$f"; done
```


## 7. 0.8.0 扩展证据（2026-10-27）

新增 3 个 Reader、11 个算子。以下按 **B/C** 如实标注，不把“单元测试”冒充外部 oracle：

| 组件 | 级别 | 证据/边界 |
|---|---|---|
| GmtReader / LoomReader / BiomReader | B | 手写格式解析测试；尚未与 loompy/biom-format 逐值对拍 |
| ora | B | 超几何 p 值手算 + 独立 SciPy；与 R base `phyper` 逐值对拍 |
| gsea | B | 经典加权 KS 分数 + 固定 seed 的基因集置换；ES 与 `fgsea::calcGseaStat` 对拍，p 值零分布不同 |
| doublet_detect / marker_score | B | 直接封装 Scanpy Scrublet / score_genes；测试验证封装与输出契约，不重复证明上游算法 |
| meta_analysis | B | 固定效应/随机效应手算；beta/se/z/p/Q/I2 与 `metafor::rma(FE/DL)` 对拍；I2 为百分比 |
| R oracle（`tests/test_r_oracles.py`） | B | 6 个测试：limma 普通 t、fgsea ES、metafor FE/DL、phyper、独立 log-ratio/Welch；R 或包缺失时自动 skip |
| prs | B | 剂量×权重手算；未处理 effect allele/strand 推断 |
| protein_rollup | B | shared-peptide 手算；尚未与 MaxQuant proteinGroups 对拍 |
| limma_de | B | 平衡两组手算 + 独立线性模型；`prior_df=0` 的 logFC/t/p 与 R `limma::lmFit` 对拍；默认 eBayes 先验未对拍 |
| ancom_bc / aldex2 | C | 独立 log-ratio 实现；核心 diff/p 与 R base log-ratio+Welch 公式对拍；完整 R ANCOMBC/ALDEx2 未对拍 |

因此这些组件暂不作为“科学结论已外部验证”的 stable 依据；route 用于可运行示例，后续需补 L2/L3 oracle。

## 8. 0.9.0 扩展证据

| 算子 | 级别 | 证据 |
|---|---|---|
| `combat` | B | `test_extension2_operators.py` 的 batch/mean-center 对齐测试；`single_cell_batch` route 实际运行 |
| `ssgsea` | A | `test_ssgsea_matches_r_gsva` 与 R GSVA 1.28 `method="ssgsea"` 对拍；`rnaseq_ssgsea` route 实际运行 |

## 9. 0.10.0 扩展证据

- 新增 31 个算子全部通过 `tests/test_extension3.py` / `tests/test_extension3b.py` 的合成数据运行测试；覆盖分类、回归、投影、组间检验、BH 校正和 Mann-Whitney。
- 新增 13 个 Reader 通过 `tests/test_extension3.py` / `tests/test_extension3b.py` 的临时文件解析测试；Excel、HDF5、Newick、FASTQ 等均验证 axis/dims/labels。
- 扩展未修改 `src/core/`、Reader/Step 基类、runner 或 registry 发现逻辑；仅新增模块、测试、生成式 registry 和参考页。
- 全量 pytest 基线更新为 **525 passed / 0 skipped**；参考页 122 算子 / 32 Reader；21 条 route fixture 仍全部执行。

## 10. 0.11.0 扩展证据

- 新增 10 个算子：SpectralEmbedding、LocallyLinearEmbedding、GaussianRandomProjection、TopicLDA、Wilcoxon、Friedman、Bartlett、Normaltest、Bonferroni、FisherCombined；`tests/test_extension4.py` 9 项通过。
- 新增 6 个 Reader：PAF、SAM、BEDPE、cytoband、Clustal、NEXUS；`tests/test_extension4.py` 全部临时文件解析通过。
- 未修改 `src/core/`、Reader/Step 基类、runner 或 registry 发现逻辑；仅新增模块、registry 生成物、测试和参考页。
- 全量 pytest 基线更新为 **534 passed / 0 skipped**；参考页 132 算子 / 38 Reader；21 条 route fixture 保持不变。
