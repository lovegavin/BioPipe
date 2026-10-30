# BioPipe SOP 验证矩阵
本文件由 `src/task`/`src/reader` 与测试引用自动生成；每次新增 Reader/算子或测试后重跑生成脚本。

当前基线：0.18 全量 pytest **606 passed / 1 skipped**（唯一 skip 为增量门在 full-suite 模式的分支）；0.19 按用户要求只跑增量，**42 passed**（新增 17 项）；0.20 按用户要求只跑增量，新增 **12 passed**、增量门 **28 passed**；0.21 按用户要求只跑增量，新增 **10 passed**、增量门 **26 passed**；0.22 新增 **8 passed**、增量门 **24 passed**；0.23 新增 **5 passed**、增量门 **21 passed**；0.24 新增 **5 passed**、增量门 **21 passed**；0.25 新增 **6 passed**、增量门 **22 passed**；0.26 新增 **5 passed**、增量门 **21 passed**；0.27 新增 **6 passed**、增量门 **22 passed**；0.28 新增 **5 passed**、增量门 **22 passed**；0.29 新增 **5 passed**、增量门 **22 passed**；0.30 新增 **5 passed**、增量门 **21 passed**；0.31 新增 **4 passed**、增量门 **20 passed**；0.32 新增 **5 passed**、增量门 **21 passed**；0.33 新增 **4 passed**、增量门 **20 passed**；0.34 新增 **4 passed**、增量门 **20 passed**；0.35 新增 **5 passed**、增量门 **21 passed**；0.36 新增 **4 passed**、增量门 **20 passed**；0.37 新增 **5 passed**、增量门 **33 passed**；0.38 新增 **5 passed**、增量门 **21 passed**；0.39 新增 **5 passed**、增量门 **21 passed**；0.40 新增 **5 passed**、增量门 **21 passed**；0.41 新增 **5 passed**、增量门 **21 passed**；0.42 新增 **5 passed**、增量门 **21 passed**；0.43 新增 **6 passed**、增量门 **22 passed**；0.44 新增 **6 passed**、增量门 **22 passed**；0.45 新增 **4 passed**、增量门 **20 passed**；0.46 新增 **5 passed**、增量门 **26 passed**，均未重跑全量。独立 SOP **29** 个；14 个 verify 脚本、49 个 demo 自测通过。

## 1. 分级
| 级别 | 含义 |
|---|---|
| S | 独立的 SOP 测试（不依赖旧 verify/demo；外部库/手算/独立解析器逐值对比） |
| A | 主题验证脚本：外部权威值、独立实现或数学不变量 |
| B | 算子 demo 自测：手工可算的小例子 |
| C | 仅契约/route/artifact 覆盖；没有独立数值 oracle |

## 2. Reader（82）
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
| `MafReader` | B | test_extension5.py（MAF 注释表、variant×field） |
| `ChainReader` | B | test_extension5.py（UCSC chain header、alignment×field） |
| `BamReader` | B | test_extension7.py（pysam BAM 子集、read×field） |
| `CramReader` | B | test_extension7.py（CRAM 需 reference；未在实际 CRAM 上跑外部 oracle） |
| `BigWigReader` | B | test_extension7.py（pyBigWig 区间） |
| `PedReader` | B | test_extension7.py（PED 家系/基因型，dosage 无参考等位基因） |
| `GfaReader` | B | test_extension7.py（GFA S 段 length/GC） |
| `GenBankReader` | B | test_extension8.py（LOCUS/FEATURES/ORIGIN 手写解析） |
| `PdbReader` | B | test_extension8.py（ATOM/HETATM 固定列） |
| `ZarrReader` | B | test_extension8.py（2D 数值数组、labels） |
| `BcfReader` | B | test_extension8.py（pysam BCF；Windows 原生不可用） |
| `BlastTabularReader` | B | test_extension10.py（BLAST outfmt6 12 列） |
| `HmmerTbloutReader` | B | test_extension10.py（HMMER tblout 常用列） |
| `InterProScanReader` | B | test_extension10.py（InterProScan TSV） |
| `EmblReader` | B | test_extension10.py（EMBL 记录/长度/GC） |
| `HmmReader` | B | test_extension10.py（HMMER3 profile 头） |
| `Mol2Reader` | B | test_extension10.py（MOL2 原子/键计数） |
| `SmiReader` | B | test_extension10.py（SMILES 近似重原子计数） |
| `BedMethylReader` | B | test_extension10.py（ENCODE bedMethyl 15 列） |

| `WigReader` | B | test_extension9.py（fixedStep/variableStep、0-based region） |
| `BroadPeakReader` | B | test_extension9.py（9 列 broadPeak） |
| `GffReader` | B | test_extension9.py（9 列 GFF2；避开 Gff3Reader 的 .gff） |
| `MmcifReader` | B | test_extension9.py（mmCIF atom_site loop） |
| `OboReader` | B | test_extension9.py（OBO [Term] 常用字段） |
| `SdfReader` | B | test_extension9.py（SDF 原子/键计数与分子量） |

| `FamReader` | B | test_extension11.py（FAM 6 列；IID 作行标签，性别/表型 <=0 转 NaN） |
| `BimReader` | B | test_extension11.py（BIM 6 列；variant 行标签） |
| `HapmapReader` | B | test_extension11.py（HapMap 剂量；首个非缺失等位基因为参照） |
| `MolReader` | B | test_extension11.py（MOL V2000 原子/键计数） |
| `XyzReader` | B | test_extension11.py（XYZ 原子坐标/原子序数） |
| `GroReader` | B | test_extension11.py（GROMACS .gro 固定列） |
| `PslReader` | B | test_extension11.py（PSL 21 列；block 字符串编码） |
| `GenePredReader` | B | test_extension11.py（genePred 10 列，空白分隔） |
| `MgfReader` | B | test_extension11.py（MGF BEGIN/END IONS 块） |
| `HmmerDomtblReader` | B | test_extension11.py（HMMER domtblout 22 列 + description） |
| `MzmlReader` | B | test_extension12_readers.py（mzML 扫描元数据、分钟/秒换算、selected ion m/z） |
| `MzxmlReader` | B | test_extension12_readers.py（mzXML scan、PT 时长、zlib 峰计数） |
| `MztabReader` | B | test_extension12_readers.py（mzTab PSM 段、MTD 元数据、section 选择） |
| `MzidentmlReader` | B | test_extension13_readers.py（mzIdentML PSM/肽段/蛋白） |
| `PepxmlReader` | B | test_extension13_readers.py（pepXML spectrum_query/search_hit） |
| `MzdataReader` | B | test_extension13_readers.py（mzDATA 谱图/cvParam） |
| `ProtXMLReader` | B | test_extension13_readers.py（protXML protein_group/protein） |
| `FcsReader` | B | test_extension15_readers.py（FCS 2.0 事件矩阵、$PnN 通道、整数位宽/字节序） |
| `Ab1Reader` | B | test_extension15_readers.py（ABIF 目录、PBAS/PCON/PLOC、FWO_ 通道映射） |

Reader SOP 覆盖：CSV/TSV/TXT/Parquet → pandas；BED/GFF3/GTF → 手写解析 + 边界；FASTA → 手写解析 + NCBI 长度/GC；GAF → 手写解析；MTX → scipy.io.mmread；H5AD/10x H5 → h5py；VCF → pysam；PLINK1 → bed_reader；PLINK2 → pgenlib；BGEN → bgen_reader。
## 3. Operator（283；下表为 89 个早期算子，0.8–0.46 新增见末尾证据）
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
- 运行中的 skip：0.18 全量 pytest 为 **606 passed / 1 skipped**；唯一 skip 是 `tests/test_incremental_gate.py` 在 full-suite 模式没有 `BIPIPE_CHANGED_MODULES` 的有意分支。桌面测试在 `frontend/dist` 存在时执行，route fixture 已全部接入。

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

## 11. 0.12.0 扩展证据

- 新增 6 个算子：UMAP、配对 t 检验、单样本 t 检验、z-score、min-max 缩放、softmax；`tests/test_extension5.py` 6 项通过。
- 新增 2 个 Reader：MAF、UCSC chain；`tests/test_extension5.py` 临时文件解析和 `pick_reader` 分派通过。
- 未修改 `src/core/`、Reader/Step 基类、runner 或 registry 发现逻辑；仅新增模块、registry 生成物、测试、图标和参考页。
- 全量 pytest 基线更新为 **540 passed / 0 skipped**；参考页 138 算子 / 40 Reader；21 条 route fixture 保持不变。

## 12. 0.13.0 扩展证据

- 新增 6 个算子：KS 两样本、Brunner-Munzel、Fligner-Killeen、置换检验、符号检验、Jarque-Bera；`tests/test_extension6.py` 5 项通过。
- 未新增 Reader；未修改 `src/core/`、Reader/Step 基类、runner 或 registry 发现逻辑；仅新增模块、registry 生成物、测试、图标和参考页。
- 全量 pytest 基线更新为 **544 passed / 0 skipped**；参考页 144 算子 / 40 Reader；21 条 route fixture 保持不变。

## 13. 0.14.0 扩展证据

- 新增 8 个算子：距离相关、偏相关、VIF、分位数变换、幂变换、稳健缩放、缩尾、秩变换；`tests/test_extension7.py` 8 项通过。
- 新增 5 个 Reader：BAM、CRAM、BigWig、PED、GFA；`tests/test_extension7.py` 临时文件解析和 `pick_reader` 分派通过。
- 未修改 `src/core/`、Reader/Step 基类、runner 或 registry 发现逻辑；仅新增模块、registry 生成物、测试、图标和参考页。
- 全量 pytest 基线更新为 **552 passed / 0 skipped**；参考页 152 算子 / 45 Reader；21 条 route fixture 保持不变。

## 14. 0.15.0 扩展证据

- 新增 6 个算子：Mantel、PLS 回归、分位数回归、bootstrap CI、silhouette、互信息；`tests/test_extension8.py` 8 项通过。
- 新增 4 个 Reader：GenBank、PDB、Zarr、BCF；BCF 依赖 pysam，原生 Windows 不可用，见 [Windows 兼容性](windows_compatibility.md)。
- 未修改 `src/core/`、Reader/Step 基类、runner 或 registry 发现逻辑；仅新增模块、registry 生成物、测试、图标和参考页。
- 全量 pytest 基线更新为 **560 passed / 0 skipped**；参考页 158 算子 / 49 Reader；21 条 route fixture 保持不变。

## 15. 0.16.0 扩展证据

- 新增 9 个算子：DBSCAN、层次聚类、GMM、孤立森林、Cramér–von Mises、Welch ANOVA、Tukey HSD、C-index、二分类指标；`tests/test_extension9.py` 12 项通过。
- 新增 6 个 Reader：WIG、broadPeak、GFF2、mmCIF、OBO、SDF；`tests/test_extension9.py` 临时文件解析和 `pick_reader` 分派通过。
- 未修改 `src/core/`、Reader/Step 基类、runner 或 registry 发现逻辑；仅新增模块、registry 生成物、测试、图标和参考页。
- 按用户要求只跑增量测试，未重跑全量：0.16 增量 **12 passed**；registry 167/55/21；参考页 167 算子 / 55 Reader；前端 113 passed。
- 边界：聚类标签编号不稳定（受随机种子/样本顺序影响）；Cramér–von Mises 仅两组；Welch ANOVA/Tukey HSD 至少三组；C-index 把 risk 方向定义为越高风险越大；分类指标只支持二分类且正类默认按标签排序后的最后一个；GFF 使用 `.gff2` 以避免与 Gff3Reader 冲突；WIG/broadPeak 为 0-based 区间；mmCIF 只解析 atom_site；OBO 只读取 Term 常用字段；SDF 不重建键连接图。

## 16. 0.17.0 扩展证据

- 新增 12 个算子：Holm、Benjamini-Yekutieli、Cohen's d/Hedges g、Cliff's delta、η²、rank-biserial、Davies-Bouldin、Calinski-Harabasz、ARI、混淆矩阵、ROC 曲线、Mann-Kendall；`tests/test_extension10.py` 10 项通过，R `p.adjust` oracle 1 项通过。
- 新增 8 个 Reader：BLAST tabular、HMMER tblout、InterProScan、EMBL、HMM、MOL2、SMI、bedMethyl；`tests/test_extension10.py` 临时文件解析和 `pick_reader` 分派通过。
- 未修改 `src/core/`、Reader/Step 基类、runner 或 registry 发现逻辑；仅新增模块、registry 生成物、测试、图标和参考页。
- 按用户要求只跑增量测试，未重跑全量：0.17 增量 **11 passed**（`tests/test_extension10.py` 10 项 + R oracle 1 项）；参考页 179 算子 / 63 Reader；21 条 route fixture 保持不变；Studio 前端 125 passed。
- 边界：Holm/BY 对 NaN p 保留 NaN；效应量只支持连续特征；Mann-Kendall 使用 tie-corrected 正态近似；聚类标签编号不稳定；SMI 的重原子计数为近似值；MOL2 不重建键级；bedMethyl 仅解析 15 列常用字段。

## 17. 严格增量测试基础设施

- `scripts/test_incremental.py`：按 `git diff`/未跟踪文件选择测试；改动 `src/core/`、Reader/Step 基类、runner 或 registry 发现逻辑时拒绝增量，要求 `--full`。
- `tests/test_incremental_gate.py`：静态检查封闭 schema、Reader 扩展名/兄弟文件消歧、算子 arity/输出契约、参考索引/页面/源码，以及改动模块的测试映射。
- `tests/test_incremental_runner.py`：覆盖核心改动拒绝、前端/文档分类、Reader 到 `pick_reader` 测试的映射。
- 新增 5 个 R oracle 测试：Wilcoxon、Friedman、Bartlett、KS、Mann-Kendall；R 包 `sva`、`Kendall`、`edgeR`、`DESeq2`、`ALDEx2` 已安装，`clusterProfiler`/`ANCOMBC` 仍受依赖链限制。
- 0.17 增量验证：文档/reference/portability + read/write gate + R oracle 共 **36 passed**；新增测试在 `-W error` 下 **14 passed**；未重跑全量。
- 日常命令：`python scripts/test_incremental.py`；周期命令：`python scripts/test_incremental.py --full`。详见 [测试范式](testing.md)。

## 18. 0.18.0 扩展证据

- 新增 14 个算子：反向互补、翻译、密码子使用、限制性酶切位点、蛋白性质、PCA loadings、HVG、细胞周期评分、Hudson Fst、GRM relatedness、RMST、target-decoy q-value、McNemar、Kendall tau。`tests/test_extension11.py` 9 项通过（8 个原测试 + `_sequence_common` 辅助测试）；Kendall tau 另有 R `cor.test(method="kendall")` oracle，R oracle 文件 6 项通过。
- 新增 10 个 Reader：FAM、BIM、HapMap、MOL、XYZ、GRO、PSL、genePred、MGF、HMMER domtblout；`tests/test_extension11.py` 临时文件解析和 `pick_reader` 分派通过。
- 未修改 `src/core/`、Reader/Step 基类、runner 或 registry 发现逻辑；仅新增模块、registry 生成物、测试、图标和参考页。
- 0.18 增量 **14 passed**（8 原算子/Reader 测试 + 6 R oracle）；全量 **606 passed / 1 skipped**（1 个 full-suite 模式有意 skip）；registry 193/73/21；参考页 193 算子 / 73 Reader；Studio 前端 139 passed 且构建通过。
- 边界：翻译使用标准遗传密码；限制性酶切为精确 motif 计数（含反向互补）；pI/MW 为常用近似；HVG 基于均值-离散度；Fst 为 Hudson 估计；GRM 使用 2p 缺失填补；RMST 为 KM 曲线下面积；q-value 为 target-decoy 单调校正；McNemar 默认连续性校正；Kendall tau 只统计成对完整观测；HapMap 以首个非缺失等位基因为参照；MOL2 不重建键级。


## 19. 0.19.0 扩展证据

- 新增 7 个算子：`tmm_normalize`（edgeR TMM）、`remove_batch_effect`（limma sum-to-zero 编码）、`mantel_haenszel`、`cochran_armitage`、`tost_equivalence`、`bland_altman`、`cumulative_incidence`（Aalen-Johansen）。
- 新增 3 个 Reader：`MzmlReader`、`MzxmlReader`、`MztabReader`；`MgfReader` 修复空峰谱的 `precursor_mz`。
- `tests/test_extension12.py` 7 项、`tests/test_extension12_readers.py` 4 项、`tests/test_r_oracles4.py` 6 项，合计 17 项通过；增量门 42 passed；R 对照为 edgeR `calcNormFactors`、limma `removeBatchEffect`、`mantelhaen.test`、`prop.trend.test`、Welch TOST 公式、`survfit`。
- 0.19 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 200/76/21；参考页 200 算子 / 76 Reader；Studio 前端 146 passed。
- 边界：TMM 使用 f75 参考和 trimmed weighted mean；批次校正仅移除 batch 设计列；MH 不默认连续性校正；CA 使用等距 scores；TOST 支持 Welch/pooled；CIF 事件码 0/1/2；质谱 Reader 只汇总扫描/记录，不展开原始峰列表。

## 20. 0.20.0 扩展证据

- 新增 8 个算子：Cohen's kappa、Fleiss' kappa、Breusch-Pagan、Durbin-Watson、Egger 回归检验、ANOSIM、Procrustes、偏 Mantel。
- 新增 4 个 Reader：mzIdentML、pepXML、mzDATA、protXML；均为 stdlib XML 摘要解析，不展开原始峰/谱图数组。
- `tests/test_extension13.py` 6 项、`tests/test_extension13_readers.py` 5 项、`tests/test_r_oracles5.py` 1 项，合计 12 项通过；R 对照使用 `vegan::anosim/procrustes/mantel.partial` 与 `lm`，Python 对照使用 statsmodels。
- 0.20 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 208/80/21；参考页 208 算子 / 80 Reader；增量门 28 passed，`-W error` 下 14 passed；Studio 前端 154 passed。
- 边界：kappa 支持无权重/线性/二次权重；Fleiss 支持 fleiss/randolph；Breusch-Pagan 使用 statsmodels 的 LM/F 版本；Durbin-Watson 只做残差自相关；Egger 为未加权 OLS；ANOSIM 使用秩和置换；Procrustes 仅旋转/平移/缩放，不做反射；偏 Mantel 对距离矩阵下三角残差化；质谱 Reader 只输出摘要字段。

## 21. 0.21.0 扩展证据

- 新增 8 个统计/临床算子：`storey_qvalue`、`delong_auc`、`dunn_test`、`decision_curve`、`ordinal_logistic`、`linear_mixed_model`、`hosmer_lemeshow`、`stuart_maxwell`。
- 未新增 Reader；尝试安装 `flowCore`（依赖 `cytolib` 编译失败）与 `sangerseqR`（未安装），FCS/AB1 Reader 暂缓，原因记录在 [权威矩阵](oracle_matrix.md)。
- `tests/test_extension14.py` 8 项、`tests/test_r_oracles6.py` 2 项，合计 **10 项通过**；R 对照使用 pROC、dunn.test、dcurves、MASS、lme4、ResourceSelection、DescTools。
- 0.21 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 216/80/21；参考页 216 算子 / 80 Reader；增量门 26 passed，`-W error` 下 12 passed；Studio 前端 162 passed。
- 边界：Storey q-value 采用固定 lambda 的 pi0 与 BH 单调校正；DeLong 使用正态近似 CI；Dunn 使用标准 Holm（与 dunn.test 的非单调 P.adjust 记录差异）；决策曲线阈值为 0.01–0.99；有序 logistic 使用 statsmodels OrderedModel 的 logit/probit；LMM 为随机截距、REML 可选；Hosmer-Lemeshow 用唯一分位数切点；Stuart-Maxwell 先移除对角等于双边边际的类别。

## 22. 0.22.0 扩展证据

- 新增 2 个 Reader：`FcsReader`（FCS 2.0/3.x 事件矩阵与通道元数据）和 `Ab1Reader`（ABIF basecall、质量、峰位置、四通道 trace）。
- `tests/test_extension15_readers.py` 7 项、`tests/test_r_oracles7.py` 1 项，合计 **8 项通过**；增量门 **24 passed**，`-W error` 下 **10 passed**；R 对照为 `flowCore::read.FCS` 与 `sangerseqR::read.abif`。
- 依赖修复：`cytolib`/`flowCore` 在 BH 1.90 下编译失败，改用 BH 1.84 用户库编译后复制到主 R 库；`sangerseqR` 从 Bioconductor 安装。
- 0.22 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 216/82/21；参考页 216 算子 / 82 Reader；Studio 前端 162 passed。
- 边界：FCS 只支持 list mode、`$DATATYPE` I/F/D；AB1 只解析 ABIF 常用 tag，不重做 basecalling；两者都不展开原始峰列表/电泳图。

## 23. 0.23.0 扩展证据

- 新增 3 个生存预测算子：`time_dependent_auc`、`brier_score`、`integrated_brier_score`；未新增 Reader。
- `tests/test_extension16.py` 4 项、`tests/test_r_oracles8.py` 1 项，合计 **5 项通过**；R 对照使用 `survivalROC::survivalROC`、`survival::coxph`、`survival::brier`。
- R 参考值：AUC@5/10/15 = **0.6552020987 / 0.8091230111 / 0.6519226986**；Brier = **0.1315697618 / 0.1807035261 / 0.2145172338**；IBS = **1.7687351192**；Cox coef **0.2425241**。
- 关键边界：t=10 有删失，按 R `brier` 的 timefix 将删失时间 +0.5；否则 Brier 为 0.17347 而非 0.1807035。
- 0.23 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 219/82/21；参考页 219 算子 / 82 Reader；增量门 21 passed；Studio 前端 165 passed。
- 边界：时间依赖 AUC 只实现 KM 法；Brier 使用 Cox PH 的 IPCW；积分 Brier 仅对给定 times 做梯形积分。

## 24. 0.24.0 扩展证据

- 新增 3 个临床预测评估算子：`calibration_slope`、`net_reclassification_improvement`、`integrated_discrimination_improvement`；未新增 Reader。
- `tests/test_extension17.py` 4 项、`tests/test_r_oracles9.py` 1 项，合计 **5 项通过**；R 对照使用 base `glm`、`qlogis` 与 NRI/IDI 公式。
- R 值：校准截距 **-0.4063779**、斜率 **3.621762**、斜率 SE **2.577094**；NRI **1.0**；IDI **0.1083333**。
- 0.24 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 222/82/21；参考页 222 算子 / 82 Reader；增量门 21 passed；Studio 前端 168 passed。
- 边界：校准截距用 `glm(y ~ 1, offset=logit(p))`；NRI 仅连续版本；IDI 只适用于二分类结局。

## 25. 0.25.0 扩展证据

- 新增 3 个回归/时间序列诊断算子：`white_test`、`chow_test`、`ljung_box`；未新增 Reader。
- `tests/test_extension18.py` 5 项、`tests/test_r_oracles10.py` 1 项，合计 **6 项通过**；R 对照 base `lm` 与 `Box.test`。
- R 参考值：White LM **5.6138306138**、p **0.3456253123**、F **1.0926275992**；Chow F **25.2160566352**、p **1.13223e-05**；Ljung-Box Q **37.7313478225**、p **4.272e-07**。
- 0.25 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 225/82/21；参考页 225 算子 / 82 Reader；增量门 22 passed；Studio 前端 171 passed。
- 边界：White 辅助回归含平方项和交叉项；Chow 按样本行顺序在 `break_fraction` 处分段；Ljung-Box 对原始去均值序列计算，不自动取回归残差。

## 26. 0.26.0 扩展证据

- 新增 2 个流式细胞术算子：`flow_transform`（arcsinh 变换）和 `flow_gate`（二维矩形门控）；未新增 Reader。
- `tests/test_extension19.py` 4 项、`tests/test_r_oracles11.py` 1 项，合计 **5 项通过**；R 对照 `flowCore::arcsinhTransform` 与 `flowCore::rectangleGate` + `filter`。
- R 参考值：变换前两行 FSC-H/FL1-H `[11.6385695024, 12.1196362926]`、`[12.1356879809, 11.1944095560]`；矩形门控 `FSC-H 100..500`、`SSC-H 50..400` 为 **6959/10000**，比例 **0.6959**。
- 0.26 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 227/82/21；参考页 227 算子 / 82 Reader；增量门 21 passed；Studio 前端 173 passed。
- 边界：arcsinh 公式为 `asinh(a + b*x) + c`，未选中的通道原样保留；矩形门控为闭区间，只支持二维轴对齐门，不实现多边形/布尔门。

## 27. 0.27.0 扩展证据

- 新增 4 个统计算子：`adf_test`（增广 Dickey-Fuller 单位根）、`kpss_test`（KPSS 平稳性）、`poisson_regression`、`negative_binomial_regression`；未新增 Reader。
- `tests/test_extension20.py` 5 项、`tests/test_r_oracles12.py` 1 项，合计 **6 项通过**；R 对照 `tseries` 0.10-63 的 `adf.test`/`kpss.test`、base `glm(poisson)`、`MASS::glm.nb`。
- R/数值参考：ADF 统计量 **-3.3953961017**（k=2，R p 表为 0.06510808，statsmodels p 0.0520060831；统计量一致，p 查表差异已记录）；KPSS 统计量 **0.1696735045**、lags 3、p 0.1；Poisson 系数 **0.8213881 / 1.0349290**；NB 系数 **0.8028424 / 1.1345920**、theta **2.261968**。
- 0.27 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 231/82/21；参考页 231 算子 / 82 Reader；增量门 22 passed；Studio 前端 177 passed。
- 边界：ADF 默认含常数和线性趋势，`regression` 可选 c/ct/n；p 值来自 statsmodels 查表，R `adf.test` 的 p 表在边界处更粗；KPSS 的渐近 p 在统计量超出表范围时截断为 0.1；Poisson/NB 均为 GLM/NB2，NB 标准误与 `glm.nb` 的信息矩阵略有差异。

## 28. 0.28.0 扩展证据

- 新增 3 个算子：`granger_causality`（Granger 因果 F 检验）、`arch_test`（ARCH LM 检验）、`flow_compensate`（流式溢漏补偿）；未新增 Reader。
- `tests/test_extension21.py` 4 项、`tests/test_r_oracles13.py` 1 项，合计 **5 项通过**；R 对照 `lmtest::grangertest`、`FinTS::ArchTest`、`flowCore::compensate`。
- R 参考值：Granger F `395.9681448 / 211.8084391 / 146.0148720`（lag 1/2/3）；ARCH LM `11.4217771216`、p `0.0436298086`；补偿首行 `[1, 0, 5]`、第二行 `[1.9897959, 0.1020408, 6]`。
- 0.28 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 234/82/21；参考页 234 算子 / 82 Reader；增量门 22 passed；Studio 前端 180 passed。
- 边界：Granger 仅做双变量、指定 `max_lag` 的 F 检验，不做协整/VAR 全模型；ARCH 使用平方序列 LM，`demean=False` 默认；flow_compensate 只做方阵溢漏矩阵的线性补偿，不做光谱拆分或自动求逆。

## 29. 0.29.0 扩展证据

- 新增 3 个回归诊断算子：`breusch_godfrey`（Breusch-Godfrey 序列相关）、`reset_test`（RESET 函数形式）、`harvey_collier`（Harvey-Collier 线性性）；未新增 Reader。
- `tests/test_extension22.py` 4 项、`tests/test_r_oracles14.py` 1 项，合计 **5 项通过**；R 对照 `lmtest::bgtest`、`lmtest::resettest`、`lmtest::harvtest`。
- R 参考值：BG LM `2.1242989892`、p `0.1449790984`、F `2.0410720144`；RESET F `14.0018972885`、p `0.0005056802`、df 1/46；Harvey-Collier t `0.4877593042`、p `0.6280371065`、df 46。
- 0.29 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 237/82/21；参考页 237 算子 / 82 Reader；增量门 22 passed；Studio 前端 183 passed。
- 边界：三者都基于同一个 OLS 设计矩阵；BG 用 LM/F 渐近结果，RESET 用拟合值幂次增广，Harvey-Collier 用递归残差 t 检验；不替代因果识别或稳健标准误。


## 30. 0.30.0 扩展证据

- 新增 3 个回归模型算子：`multinomial_logit`（多项 logit）、`conditional_logit`（条件 logit）、`robust_regression`（Huber M 稳健回归）；未新增 Reader。
- `tests/test_extension23.py` 4 项、`tests/test_r_oracles15.py` 1 项，合计 **5 项通过**；R 对照 `nnet::multinom`、`survival::clogit`、`MASS::rlm(psi=psi.huber)`。
- R 参考值：多项 logit 系数 `-0.0785675/0.6947102/0.4630492`（reference=1，outcome=2）；条件 logit 系数 `1.0291703/-0.9972766`、SE `0.5022442/0.4568622`；稳健回归系数 `0.9672461/1.8805607/-0.5415845`、scale `0.3079868`。
- 0.30 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 240/82/21；参考页 240 算子 / 82 Reader；增量门 21 passed；Studio 前端 186 passed。
- 边界：多项 logit 以排序后的第一水平为 reference；条件 logit 要求每个 stratum 恰好一个事件且至少一个对照，不含截距；稳健回归为 Huber M 估计，不提供 MM/自适应估计或稳健标准误。


## 31. 0.31.0 扩展证据

- 新增 2 个回归模型算子：`gamma_regression`（Gamma GLM，log link）、`zero_inflated_poisson`（logistic 零膨胀 + Poisson 计数）；未新增 Reader。恢复并保留既有 `quantile_regression`（0.15 ML 算子，不重复注册）。
- `tests/test_extension24.py` 3 项、`tests/test_r_oracles16.py` 1 项，合计 **4 项通过**；R 对照 `glm(y ~ x1 + x2, family=Gamma(link="log"))`、`pscl::zeroinfl(y ~ x | z, dist="poisson")`。
- R 参考值：Gamma 系数 `0.4403480/0.3146126/-0.2057134`、SE `0.05692901/0.05703248/0.04923079`；零膨胀 Poisson count `1.0500853/0.4181325`、zero `-0.7452351/1.0384099`。
- 0.31 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 242/82/21；参考页 242 算子 / 82 Reader；增量门 20 passed；Studio 前端 188 passed。
- 边界：Gamma 使用 log link、MLE 尺度参数；零膨胀 Poisson 的零模型默认仅截距，可选 `zero_predictors`；两者均不提供稳健标准误或随机效应。

## 32. 0.32.0 扩展证据

- 新增 2 个可靠性算子：`intraclass_correlation`（ICC，组内相关）、`concordance_correlation`（Lin's CCC，一致性相关系数）；未新增 Reader。
- `tests/test_extension25.py` 4 项、`tests/test_r_oracles17.py` 1 项，合计 **5 项通过**；R 对照 `irr::icc`、`DescTools::CCC`。
- R 参考值：ICC(A,1) **0.6282403440**，F(19,19) **16.0425178877**，p **5.9546426626e-08**，95% CI **-0.0850675490..0.8923981941**；Lin's CCC **0.6161839**，95% CI **0.4425713..0.7452724**，s.shift **1.665079**，l.shift **0.9898274**，C.b **0.616255**。
- 0.32 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 244/82/21；参考页 244 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 190 passed。
- 边界：ICC 支持 oneway/twoway、consistency/agreement、single/average；r0 固定为 0，按完整样本分析，不插补缺失；CCC 使用 pairwise complete 与 z-transform CI，不提供 bootstrap CI。

## 33. 0.33.0 扩展证据

- 新增 2 个方法学一致性算子：`passing_bablok`（Passing-Bablok 回归）、`deming_regression`（Deming 回归）；未新增 Reader。
- `tests/test_extension26.py` 3 项、`tests/test_r_oracles18.py` 1 项，合计 **4 项通过**；R 对照 `mcr::mcreg(method.reg="PaBa")`、`mcr::mcreg(method.reg="Deming", error.ratio=1)`。
- R 参考值：Passing-Bablok slope **1.0**、intercept **0.1**；Deming slope **1.0090793076**、intercept **0.0100638082**（x=1..10，n=10）。
- 0.33 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 246/82/21；参考页 246 算子 / 82 Reader；增量门 20 passed；`-W error` 6 passed；Studio 前端 192 passed。
- 边界：仅点估计，不输出 CI；Passing-Bablok 不做负值/重复测量校正，Deming 使用固定误差比与完整样本；不对标 R 的 CI（PaBa CI 在 C 层、Deming 有限样本约定不同）。

## 34. 0.34.0 扩展证据

- 新增 2 个配对/匹配检验算子：`roc_comparison`（DeLong 配对 ROC 比较）、`cochran_q`（Cochran's Q）；未新增 Reader。
- `tests/test_extension27.py` 3 项、`tests/test_r_oracles19.py` 1 项，合计 **4 项通过**；R 对照 `pROC::roc.test(method="delong")`、`DescTools::CochranQTest`。
- R 参考值：AUC a/b **0.8025 / 0.8850**，差值 **-0.0825**，z **-2.268139214153**，p **0.02332072292964**，95% CI **-0.1537906103..-0.0112093897**；Cochran Q **0.2857142857**，df 2，p **0.8668778997501816**，n=10，k=3。
- 0.34 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 248/82/21；参考页 248 算子 / 82 Reader；增量门 20 passed；`-W error` 6 passed；Studio 前端 194 passed。
- 边界：`roc_comparison` 要求同一样本、较高分数为阳性，不自动翻转 AUC<0.5 的方向；`cochran_q` 仅接受宽表二分类完整样本，不做事后两两比较。

## 35. 0.35.0 扩展证据

- 新增 3 个可靠性/多变量算子：`cronbach_alpha`（Cronbach's alpha）、`canonical_correlation`（典型相关）、`runs_test`（Wald–Wolfowitz runs test）；未新增 Reader。
- `tests/test_extension28.py` 4 项、`tests/test_r_oracles20.py` 1 项，合计 **5 项通过**；R 对照 `psych::alpha`、`stats::cancor`、`randtests::runs.test`。
- R 参考值：Cronbach raw_alpha **0.980952380952381**、std_alpha **0.981872040600713**、average_r **0.931228237555108**；canonical correlations **0.999512503815628 / 0.063233134692047**；runs z **0.654653670708**、p **0.512690760262**、runs **6**、n1/n2 **7/3**、n **10**。
- 0.35 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 251/82/21；参考页 251 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 197 passed。
- 边界：alpha 使用完整样本、sample variance 与平均 item 相关；canonical 使用 QR+SVD、完整样本，仅输出相关系数与平方；runs 默认中位数阈值、丢弃阈值相等值、正态近似（无连续性校正、无 exact p）。

## 36. 0.36.0 扩展证据

- 新增 2 个因子可分析性诊断算子：`kmo_test`（Kaiser-Meyer-Olkin 取样适切性）、`bartlett_sphericity`（Bartlett 球形检验）；未新增 Reader。
- `tests/test_extension29.py` 3 项、`tests/test_r_oracles21.py` 1 项，合计 **4 项通过**；R 对照 `psych::KMO`、`psych::cortest.bartlett`。
- R 参考值：KMO overall **0.691341995940012**；MSAi **0.622853474145 / 0.606878691663 / 0.829270272548 / 0.746501028684**；Bartlett chisq **62.6586540137764**、df **6**、p **1.2954623992175e-11**、n=12。
- 0.36 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 253/82/21；参考页 253 算子 / 82 Reader；增量门 20 passed；`-W error` 6 passed；Studio 前端 199 passed。
- 边界：KMO 要求完整样本、非奇异相关矩阵，p≥2；Bartlett 要求相关矩阵正定；两者只做可分析性诊断，不估计因子数或执行旋转。


## 37. 0.37.0 扩展证据

- 新增 3 个效应量/有序趋势算子：`cramer_v`（Cramér's V）、`jonckheere_terpstra`（Jonckheere-Terpstra 有序秩检验）、`varimax_rotation`（varimax 正交旋转）；未新增 Reader。
- `tests/test_extension30.py` 4 项、`tests/test_r_oracles22.py` 1 项，合计 **5 项通过**；R 对照 `DescTools::CramerV`、`DescTools::JonckheereTerpstraTest(exact=FALSE)`、`stats::varimax`。
- R 参考值：Cramér's V **0.36324157862838946**、chisq **13.194444444444445**、df 2、n 100；JT statistic **49.5**、z **3.1980107453341566**、p **0.0013837912401648556**；varimax SS loadings **1.5934753503051715 / 2.1865246496948276**。
- 0.37 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 256/82/21；参考页 256 算子 / 82 Reader；增量门 33 passed；Studio 前端 202 passed。
- 边界：Cramér's V 仅支持二维列联表、不做事后两两比较；Jonckheere-Terpstra 使用正态近似，不提供 exact p；varimax 仅正交旋转，不做斜交旋转、因子数选择或载荷显著性检验。


## 38. 0.38.0 扩展证据

- 新增 3 个有序关联/一致性算子：`somers_d`（Somers' D）、`goodman_kruskal_gamma`（Goodman-Kruskal gamma）、`kendall_w`（Kendall's coefficient of concordance W）；未新增 Reader。
- `tests/test_extension31.py` 4 项、`tests/test_r_oracles23.py` 1 项，合计 **5 项通过**；R 对照 `DescTools::SomersDelta`、`DescTools::GoodmanKruskalGamma`、`DescTools::KendallW(correct=FALSE)`。
- R 参考值：Somers' D(row) **0.44885945548197204**、D(column) **0.45218680504077097**、concordant/discordant **787/177**；gamma **0.63278008298755184**；Kendall W **0.84444444444444444**、chisq **10.133333333333333**、df **4**、p **0.038240605326664866**、S **76**、5 subjects × 3 raters。
- 0.38 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 259/82/21；参考页 259 算子 / 82 Reader；增量门 21 passed；Studio 前端 205 passed。
- 边界：Somers' D 依赖 `direction` 选择被解释变量，只对列联表计算；gamma 不提供 CI；Kendall's W 按列（rater）排名、`correct=FALSE` 语义，不做并列秩校正，也不输出事后两两比较。

## 39. 0.39.0 扩展证据

- 新增 3 个多元/稳健/分类数据检验算子：`hotelling_t2`（两样本 Hotelling's T²）、`yuen_test`（Yuen 截尾均值 t 检验）、`g_test`（列联表 G 检验）；未新增 Reader。
- `tests/test_extension32.py` 4 项、`tests/test_r_oracles24.py` 1 项，合计 **5 项通过**；R 对照 `DescTools::HotellingsT2Test`、`DescTools::YuenTTest(trim=0.2)`、`DescTools::GTest(correct="none")`。
- R 参考值：Hotelling F **22.131694828469026**、df **3/4**、p **0.0059380028788470485**（T² **99.592610**）；Yuen t **-0.566987210046772**、df **10**、p **0.5832249832837027**、diff **-1.0**、95% CI **-4.9297867967823645 / 2.9297867967823645**、trimmed means **5.5/6.5**；G **12.750352918064657**、df **4**、p **0.012562279689834366**、n=100。
- 0.39 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 262/82/21；参考页 262 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 208 passed。
- 边界：Hotelling T² 使用合并协方差、F 近似，要求完整样本与满秩协方差；Yuen 使用 `trim=0.2` 默认、Winsorized 方差与 Welch 自由度，不提供 exact p；G-test 使用 `correct="none"`，不做 Yates/Williams 校正。

## 40. 0.40.0 扩展证据

- 新增 3 个非参数/随机性算子：`van_waerden`（Van der Waerden 正态得分检验）、`bartels_rank`（Bartels 秩检验）、`woolf_test`（Woolf 同质 OR 检验）；未新增 Reader。
- `tests/test_extension33.py` 4 项、`tests/test_r_oracles25.py` 1 项，合计 **5 项通过**；R 对照 `DescTools::VanWaerdenTest`、`DescTools::BartelsRankTest`、`DescTools::WoolfTest`。
- R 参考值：Van der Waerden chi2 **6.349304**、df **1**、p **0.01174273**；Bartels RVN **0.1090909**、z **-3.2509408**、mu **2**、var **0.3383165**、p **0.001150238**；Woolf X2 **0.1481616**、df **2**、p **0.9285967**。
- 0.40 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 265/82/21；参考页 265 算子 / 82 Reader；增量门 21 passed；Studio 前端 211 passed。
- 边界：Van der Waerden 仅两组、正态得分使用平均秩；Bartels 要求 n>=10、仅正态近似、无 exact p；Woolf 需要 2x2xk 的四个计数列，零格自动 +0.5，不做三阶交互。

## 41. 0.41.0 扩展证据

- 新增 3 个边际齐性/随机性/正态性算子：`bhapkar_test`（Bhapkar 边际齐性检验）、`von_neumann`（Von Neumann 随机性检验）、`shapiro_francia`（Shapiro-Francia 正态性检验）；未新增 Reader。
- `tests/test_extension34.py` 4 项、`tests/test_r_oracles26.py` 1 项，合计 **5 项通过**；R 对照 `DescTools::BhapkarTest`、`DescTools::VonNeumannTest`、`DescTools::ShapiroFranciaTest`。
- R 参考值：Bhapkar chi2 **0.68890103881902676**、df **2**、p **0.70860961374150644**、n **60**；Von Neumann VN **0.1212121212121212**、z **-3.3259311751475229**、p **0.00088123685283041943**；Shapiro-Francia W **0.97684303482122625**、p **0.81248335763278823**。
- 0.41 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 268/82/21；参考页 268 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 214 passed。
- 边界：Bhapkar 仅方表、要求正定协方差和正校正分母，不提供 CI；Von Neumann 使用正态近似，不提供 exact p；Shapiro-Francia 仅 5–5000 个样本，使用正态化近似，不提供 exact p。

## 42. 0.42.0 扩展证据

- 新增 3 个正态性/极端反应算子：`shapiro_wilk`（Shapiro-Wilk 正态性检验）、`lillie_test`（Lilliefors 正态性检验）、`moses_test`（Moses 极端反应检验）；未新增 Reader。
- `tests/test_extension35.py` 4 项、`tests/test_r_oracles27.py` 1 项，合计 **5 项通过**；R 对照 `stats::shapiro.test`、`DescTools::LillieTest`、`DescTools::MosesTest`。
- R 参考值：Shapiro-Wilk W **0.96016416316107545**、p **0.54713405582814623**；Lilliefors D **0.081749071087235753**、p **0.97813612285642071**；Moses S **8**、p **0.0015479876160990713**（n_a=n_b=10，extreme=1）。
- 0.42 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 271/82/21；参考页 271 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 217 passed。
- 边界：Shapiro-Wilk 仅 3–5000 个样本、使用 AS R94 近似；Lilliefors 仅 >=5 个样本、使用 Dallal-Wilkinson p 近似；Moses 只做两组极端反应、使用平均秩和精确组合 p，不提供置换/CI。

## 43. 0.43.0 扩展证据

- 新增 3 个有序/多元/序列检验算子：`page_test`（Page 有序备择检验）、`mardia_test`（Mardia 多元正态性检验）、`turning_point_test`（Turning Point 序列随机性检验）；未新增 Reader。
- `tests/test_extension36.py` 5 项、`tests/test_r_oracles28.py` 1 项，合计 **6 项通过**；R 对照 `DescTools::PageTest`、`psych::mardia`、`randtests::turning.point.test`。
- R 参考值：Page L **232**、p **8.0199816518308664e-06**（8 块 × 4 处理，精确分布）；Page 正态分支 L **7480**、p **2.3535702950702129e-18**；Mardia b1p **0.12217681576367496**、b2p **10.404188899192361**、skew **1.2217681576367496**、small_skew **1.3151974873383832**、p.skew **0.99957224997298111**、p.small **0.99940493624954152**、kurtosis **-3.2497291944334936**、p.kurt **0.0011551495235322395**（n=60，p=3）；Turning Point turns **8**、z **2.2103158559821505**、p **0.027083248944000271**（n=10）。
- 0.43 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 274/82/21；参考页 274 算子 / 82 Reader；增量门 22 passed；`-W error` 8 passed；Studio 前端 220 passed。
- 边界：Page 仅支持完整区组、区组内无并列值；k<=8 且 n<=1000 用精确置换分布，否则用 Page 正态近似。Mardia 使用完整样本、协方差必须可逆，提供偏差校正前后两种偏度 p。Turning Point 仅支持无相邻并列值的单序列。

## 44. 0.44.0 扩展证据

- 新增 3 个趋势/离群/正态性检验算子：`cox_stuart_test`（Cox-Stuart 趋势检验）、`grubbs_test`（Grubbs 单离群值检验）、`anderson_darling`（Anderson-Darling 正态性检验）；未新增 Reader。
- `tests/test_extension37.py` 5 项、`tests/test_r_oracles29.py` 1 项，合计 **6 项通过**；R 对照 `randtests::cox.stuart.test`、`outliers::grubbs.test`、`nortest::ad.test`。
- R 参考值：Cox-Stuart t **10**、n **10**、p **0.001953125**；Grubbs G **2.709117334893635**、U **0.19267515923566875**、p **0.00093820829159652064**（离群值 25，n=11）；Anderson-Darling A **0.18980837048798804**、p **0.88712429103709245**（n=20）。
- 0.44 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 277/82/21；参考页 277 算子 / 82 Reader；增量门 22 passed；`-W error` 8 passed；Studio 前端 223 passed。
- 边界：Cox-Stuart 奇数长度丢弃中间值，并列对从二项样本量中剔除；Grubbs 只检验一个离群值，默认单侧 p，`two_sided=true` 时按 R 实现加倍；Anderson-Darling 要求 n>=8，使用估计均值/标准差和 `nortest` 的分段 p 近似。

## 45. 0.45.0 扩展证据

- 新增 3 个精确/中位数检验算子：`binomial_test`（精确二项检验）、`mood_median_test`（Mood 中位数检验）、`boschloo_exact`（Boschloo 精确无条件检验）；未新增 Reader。
- `tests/test_extension38.py` 4 项通过；权威实现为 SciPy 1.17.1（`stats.binomtest`、`stats.median_test`、`stats.boschloo_exact`），不是 R 包。
- 参考值：二项 k=7、n=10、p0=0.5 → p **0.34375**、95% CI **0.3475471499399921..0.9332604888222655**；Mood groups `[1..5]/[2..6]/[5..9]` → statistic **7.8**、p **0.020241911445804395**、median **5**；Boschloo `[[8,2],[1,9]]` → p **0.0018352604919337544**、Fisher p **0.002738747320790664**、OR **36**。
- 0.45 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 280/82/21；参考页 280 算子 / 82 Reader；增量门 20 passed；`-W error` 6 passed；Studio 前端 226 passed。
- 边界：二项检验只接受单样本、`0<p0<1`，CI 为 Clopper-Pearson；Mood 要求至少两组、每组至少一个有限值且非常量，ties 支持 below/above/ignore，correction 为 Yates；Boschloo 严格 2×2 非负整数、行列边际非零。

## 46. 0.46.0 扩展证据

- 新增 3 个稳健/多元算子：`sen_slope`（Sen 斜率）、`mahalanobis_distance`（平方 Mahalanobis 距离）、`box_m`（Box's M 协方差齐性检验）；未新增 Reader。
- `tests/test_extension39.py` 4 项、`tests/test_r_oracles30.py` 1 项，合计 **5 passed**；Sen 斜率对照 SciPy 1.17.1 `stats.theilslopes`，Mahalanobis 对照 R base `mahalanobis`，Box's M 对照 R `biotools::boxM`。
- 参考值：Sen x=1..10、y 指定序列 → slope **1.98**、intercept **0.26**、95% CI **1.9..2.025**；Mahalanobis 8×3 距离 **3.0759981851181237 / 2.040607985480989 / 4.244782214156089 / 1.5578493647912683 / 1.3736388384754896 / 1.481624319419268 / 4.041515426497227 / 3.1839836660619767**；Box's M 3 组×8、p=2 → M **0.8753278628690389**、chi2 **0.7549123896701234**、df **6**、p **0.9932284578587726**。
- 0.46 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 283/82/21；参考页 283 算子 / 82 Reader；增量门 26 passed；`-W error` 7 passed；Studio 前端 229 passed。
- 边界：Sen 斜率要求至少 3 个完整对且 x 非常量；Mahalanobis 要求完整数值行、样本数大于特征数、协方差可逆，输出平方距离与卡方 p；Box's M 要求每组样本数大于特征数、组内/合并协方差可逆，使用 `biotools::boxM` 的卡方近似。
