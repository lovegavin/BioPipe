# BioPipe SOP 验证矩阵
本文件由 `src/task`/`src/reader` 与测试引用自动生成；每次新增 Reader/算子或测试后重跑生成脚本。

当前基线：0.18 全量 pytest **606 passed / 1 skipped**（唯一 skip 为增量门在 full-suite 模式的分支）；0.19 按用户要求只跑增量，**42 passed**（新增 17 项）；0.20 按用户要求只跑增量，新增 **12 passed**、增量门 **28 passed**；0.21 按用户要求只跑增量，新增 **10 passed**、增量门 **26 passed**；0.22 新增 **8 passed**、增量门 **24 passed**；0.23 新增 **5 passed**、增量门 **21 passed**；0.24 新增 **5 passed**、增量门 **21 passed**；0.25 新增 **6 passed**、增量门 **22 passed**；0.26 新增 **5 passed**、增量门 **21 passed**；0.27 新增 **6 passed**、增量门 **22 passed**；0.28 新增 **5 passed**、增量门 **22 passed**；0.29 新增 **5 passed**、增量门 **22 passed**；0.30 新增 **5 passed**、增量门 **21 passed**；0.31 新增 **4 passed**、增量门 **20 passed**；0.32 新增 **5 passed**、增量门 **21 passed**；0.33 新增 **4 passed**、增量门 **20 passed**；0.34 新增 **4 passed**、增量门 **20 passed**；0.35 新增 **5 passed**、增量门 **21 passed**；0.36 新增 **4 passed**、增量门 **20 passed**；0.37 新增 **5 passed**、增量门 **33 passed**；0.38 新增 **5 passed**、增量门 **21 passed**；0.39 新增 **5 passed**、增量门 **21 passed**；0.40 新增 **5 passed**、增量门 **21 passed**；0.41 新增 **5 passed**、增量门 **21 passed**；0.42 新增 **5 passed**、增量门 **21 passed**；0.43 新增 **6 passed**、增量门 **22 passed**；0.44 新增 **6 passed**、增量门 **22 passed**；0.45 新增 **4 passed**、增量门 **20 passed**；0.46 新增 **5 passed**、增量门 **26 passed**；0.47 新增 **5 passed**、增量门 **21 passed**；0.48 新增 **5 passed**、增量门 **21 passed**；0.49 新增 **5 passed**、增量门 **21 passed**；0.50 新增 **5 passed**、增量门 **21 passed**；0.51 新增 **5 passed**、增量门 **21 passed**；0.52 新增 **5 passed**、增量门 **21 passed**；0.53 新增 **5 passed**、增量门 **21 passed**；0.54 新增 **5 passed**、增量门 **21 passed**；0.55 新增 **5 passed**、增量门 **21 passed**；0.56 新增 **5 passed**、增量门 **21 passed**；0.57 新增 **5 passed**、增量门 **21 passed**；0.58 新增 **5 passed**、增量门 **21 passed**；0.59 新增 **5 passed**、增量门 **21 passed**；0.60 新增 **5 passed**、增量门 **21 passed**；0.61 新增 **5 passed**、增量门 **21 passed**；0.62 新增 **5 passed**、增量门 **21 passed**；0.63 新增 **5 passed**、增量门 **21 passed**；0.64 新增 **5 passed**、增量门 **21 passed**；0.65 新增 **5 passed**、增量门 **21 passed**；0.66 新增 **5 passed**、增量门 **21 passed**；0.67 新增 **5 passed**、增量门 **21 passed**；0.68 新增 **5 passed**、增量门 **21 passed**；0.69 新增 **5 passed**、增量门 **21 passed**；0.70 新增 **5 passed**、增量门 **21 passed**；0.71 新增 **5 passed**、增量门 **21 passed**；0.72 新增 **5 passed**、增量门 **21 passed**；0.73 新增 **5 passed**、增量门 **21 passed**；0.74 新增 **5 passed**、增量门 **21 passed**；0.75 新增 **5 passed**、增量门 **21 passed**；0.76 新增 **5 passed**、增量门 **21 passed**；0.77 新增 **5 passed**、增量门 **21 passed**；0.78 新增 **7 passed**、增量门 **23 passed**；0.79 新增 **5 passed**、增量门 **21 passed**；0.80 新增 **7 passed**、增量门 **23 passed**；0.81 新增 **9 passed**、增量门 **25 passed**；0.82 新增 **7 passed**、增量门 **22 passed**（另 1 skipped）；0.83 新增 **9 passed**、增量门 **25 passed**；0.84 分类/目录定向 **20 passed**、全量 **974 passed, 1 skipped**、前端 **39 passed**；0.85 新增 **6 passed**、增量门 **100 passed**、前端 **39 passed**；0.86 新增 **6 passed**、增量门 **22 passed**、前端 **39 passed**；0.87 新增 **7 passed**、增量门 **28 passed**、前端 **39 passed**；0.88 新增 **7 passed**、增量门 **25 passed**、前端 **39 passed**；0.89 新增 **4 passed**、增量门 **20 passed**、前端 **39 passed**。独立 SOP **29** 个；14 个 verify 脚本、49 个 demo 自测通过。

## 1. 分级
| 级别 | 含义 |
|---|---|
| S | 独立的 SOP 测试（不依赖旧 verify/demo；外部库/手算/独立解析器逐值对比） |
| A | 主题验证脚本：外部权威值、独立实现或数学不变量 |
| B | 算子 demo 自测：手工可算的小例子 |
| C | 仅契约/route/artifact 覆盖；没有独立数值 oracle |

## 2. Reader（85）
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
## 3. Operator（388；下表为 89 个早期算子，0.8–0.81 新增见末尾证据）
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

## 47. 0.47.0 扩展证据

- 新增 3 个事后比较/变点算子：`scheffe_test`（Scheffe 全成对比较）、`nemenyi_test`（Nemenyi 全成对比较）、`pettitt_test`（Pettitt 单变点检验）；未新增 Reader。
- `tests/test_extension40.py` 4 项、`tests/test_r_oracles31.py` 1 项，合计 **5 passed**；Scheffe/Nemenyi 对照 `DescTools::ScheffeTest` / `DescTools::NemenyiTest`，Pettitt 对照 `trend::pettitt.test`。
- R 参考值（18 个样本、A/B/C 各 6）：Scheffe B-A diff **3.0**、95% CI **0.068774863320079316..5.9312251366799238**、p **0.044508331150382108**；C-A p **4.4835604069060167e-05**；C-B p **0.0076727193384942011**。Nemenyi B-A rank diff **4.8333333333333339**、p **0.2595187845582884734**；C-A rank diff **10.9166666666666661**、p **0.0011563817007307353**；C-B rank diff **6.0833333333333321**、p **0.1187327830527096229**。Pettitt y=1..10,9..18：U **98**、p **0.0020978278652555764**、并列变点 K **9/11**。
- 0.47 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 286/82/21；参考页 286 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 232 passed。
- 边界：Scheffe 使用单因素 ANOVA 残差均方与 F 分布，要求至少两组、每组至少一个完整值且残差自由度大于 0；Nemenyi 使用平均秩和 studentized range（df=Inf），要求至少两组；Pettitt 使用平均秩，返回首个最大变点并在 info 中保留全部并列变点。

## 48. 0.48.0 扩展证据

- 新增 3 个事后/区组算子：`conover_test`（Conover 全成对比较）、`games_howell`（Games-Howell 不等方差比较）、`quade_test`（Quade 区组秩检验）；未新增 Reader。
- `tests/test_extension41.py` 4 项、`tests/test_r_oracles32.py` 1 项，合计 **5 passed**；Conover 对照 R `DescTools::ConoverTest`，Games-Howell 对照 R `PMCMRplus::gamesHowellTest`，Quade 对照 R `stats::quade.test`。
- R 参考值（18 个样本、A/B/C 各 6）：Conover B-A rank diff **4.8333333333333339**、Holm p **0.010462063490453718**；C-A p **2.5080247917311833e-05**；C-B p **0.0044497715042364737**。Games-Howell B-A q **3.9279220242478630**、p **0.047125923759940624**；C-A q **9.1651513899116797**、p **0.00018923503262868735**；C-B q **5.2372293656638176**、p **0.010381720683943052**。Quade 5 块×3 处理：F **18**、df **2/8**、p **0.0010928215285841132**。
- 0.48 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 289/82/21；参考页 289 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 235 passed。
- 边界：Conover 要求至少两组、有限值，默认 Holm 校正并支持 bonferroni/BH/BY/none；Games-Howell 使用组内方差与 Welch 自由度，要求每组至少两个值；Quade 要求完整、无缺失的随机区组设计，区组内允许并列秩。

## 49. 0.49.0 扩展证据

- 新增 3 个区组/趋势算子：`durbin_test`（Durbin 平衡不完全区组检验）、`skillings_mack`（Skillings-Mack 缺失区组检验）、`cuzick_test`（Cuzick 有序组趋势检验）；未新增 Reader。
- `tests/test_extension42.py` 4 项、`tests/test_r_oracles33.py` 1 项，合计 **5 passed**；三者均对照 R `PMCMRplus`（`durbinTest`、`skillingsMackTest`、`cuzickTest`）。
- R 参考值：Durbin 4 块×4 处理、k=3、r=3，chi2 **7.5**、df **3**、p **0.057558451972636406**；Skillings-Mack 5 块×4 处理、15 个观测，chi2 **9.4090909090909083**、df **3**、p **0.02431840851015896**；Cuzick A/B/C 各 6，z **3.5418343613549821**、p **0.00039735490558644653**、T **407.5**。
- 0.49 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 292/82/21；参考页 292 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 238 passed。
- 边界：Durbin 要求平衡不完全区组（每块 k 个处理、每处理 r 次、k<t）；Skillings-Mack 允许缺失但要求每个区组至少两个观测、所有处理由共现图连通且协方差非奇异；Cuzick 要求有序组，默认得分 1..k，支持 `group_scores`、单双侧与连续性校正，不做并列校正。

## 50. 0.50.0 扩展证据

- 新增 3 个方差/精确检验算子：`levene_test`（Levene 方差齐性，中心为均值）、`brown_forsythe`（Brown-Forsythe 稳健方差齐性，中心为中位数）、`barnard_test`（2×2 Barnard 精确无条件独立性检验）；未新增 Reader。
- `tests/test_extension43.py` 4 项、`tests/test_r_oracles34.py` 1 项，合计 **5 passed**；Levene/Brown-Forsythe 对照 R `DescTools::LeveneTest`，Barnard 对照 SciPy 1.17.1。
- R 参考值（15 个样本、A/B/C 各 5）：Levene F **3.5958295790964074**、p **0.059760241554658484**；Brown-Forsythe F **0.48166623810748233**、p **0.6291982673370824**。Barnard `[[8,2],[1,9]]`：statistic **3.1462660248284626**、p **0.0018215179443359397**、OR **36**、n **20**。
- 0.50 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 295/82/21；参考页 295 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 241 passed。
- 边界：Levene/Brown-Forsythe 要求至少两组、每组至少两个有限值；Barnard 要求 2×2 非负整数计数、行/列边际非零，`integration_points` 取 1..4096，p 为 SciPy 无条件精确算法结果。

## 51. 0.51.0 扩展证据

- 新增 3 个尺度/离散度算子：`fligner_killeen`（Fligner-Killeen 中位数中心秩检验）、`mood_scale`（Mood 两样本尺度检验，含并列校正）、`siegel_tukey`（Siegel-Tukey 秩离散度检验，无并列时精确）；未新增 Reader。
- `tests/test_extension44.py` 4 项、`tests/test_r_oracles35.py` 1 项，合计 **5 passed**；Fligner/Mood 对照 base R，Siegel-Tukey 对照 R `PMCMRplus::siegelTukeyTest`。
- R 参考值：Fligner 3 组各 6 个 statistic **3.8539129401029886**、df **2**、p **0.14559063431450478**；Mood 两样本各 6 个 Z **-0.72323757801982935**、p **0.46953393562819462**；Siegel-Tukey 5 vs 5 无并列 W **14**、p **0.84126984126984128**。
- 0.51 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 298/82/21；参考页 298 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 244 passed。
- 边界：Fligner/Mood 每组至少两个有限值；Siegel-Tukey 有并列值时直接报错，不使用近似 p 值；大样本退回正态近似并在 info 记录 `exact=false`。

## 52. 0.52.0 扩展证据

- 新增 3 个偏度/拟合优度/方差离群算子：`agostino_skewness`（D'Agostino 偏度检验）、`chi_square_gof`（Pearson χ² 拟合优度，期望可归一化）、`cochran_c_test`（Cochran C 等组方差离群）；未新增 Reader。
- `tests/test_extension45.py` 4 项、`tests/test_r_oracles36.py` 1 项，合计 **5 passed**；分别对照 R `moments::agostino.test`、base R `chisq.test`、`outliers::cochran.test`。
- R 参考值：D'Agostino x=[1..9,20] skew **1.6060526914810145**、z **2.6471420773508192**、p **0.0081175240201695822**；χ² counts [10,20,30,40] statistic **20**、df **3**、p **0.00016974243555282649**；Cochran 3 组各 5 C **0.95238095238095233**、df1 **8**、df2 **4**、p **7.4190133887430676e-05**。
- 0.52 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 301/82/21；参考页 301 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 247 passed。
- 边界：D'Agostino n 8–46340、方差非零；χ² 期望若给出则按相对频数归一化到总计数；Cochran C 需要等组样本量、每组至少两个有限值且方差为正。

## 53. 0.53.0 扩展证据

- 新增 3 个秩尺度/离群/校准算子：`ansari_bradley`（Ansari-Bradley 秩尺度检验，正态近似）、`chisq_out_test`（χ² 方差离群检验，可选 opposite）、`calibration_curve`（分箱校准曲线，uniform/quantile）。
- `tests/test_extension46.py` 4 项、`tests/test_r_oracles37.py` 1 项，合计 **5 passed**；Ansari/χ² 离群对照 R `stats::ansari.test(exact=FALSE)` 与 `outliers::chisq.out.test`，校准曲线为自有分箱实现。
- R 参考值：Ansari x=[1..5], y=[1,4,9,16,25] AB **18**、z **1.0392304845413265**、p **0.29869755599497028**、ties=1；χ² 离群 [1,2,3,4,5,100] statistic **4.161359374447157**、p **0.04135620027516618**，opposite statistic **0.21018646286664547**、p **0.6466212955873326**。
- 校准曲线 20 样本、n_bins=5：`[0,.2,.125,0,4]`、`[.2,.4,.325,1,4]`、`[.4,.6,.525,1,4]`、`[.6,.8,.725,1,4]`、`[.8,1,.9225,1,4]`；输出列 `bin_lower,bin_upper,mean_predicted,observed_fraction,n`。
- 0.53 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 304/82/21；参考页 304 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 250 passed。
- 边界：Ansari 使用正态近似并含并列校正，不声称精确条件分布；χ² 离群要求方差为正、样本量至少 3；校准曲线要求真实标签二分类、预测概率在 [0,1]、每箱至少 1 个样本。

## 54. 0.54.0 扩展证据

- 新增 2 个回归诊断算子：`goldfeld_quandt`（Goldfeld-Quandt 异方差检验，支持中心 omitted fraction 与 greater/less/two-sided）、`rainbow_test`（Rainbow 线性偏离检验，中心子样本比例可调）。
- `tests/test_extension47.py` 4 项、`tests/test_r_oracles38.py` 1 项，合计 **5 passed**；两个算子均对照 R `lmtest::gqtest` / `lmtest::raintest`。
- R 参考值：GQ 20 样本、`fraction=0` → statistic **7.8091706001348626**、df1 **8**、df2 **8**、p **0.0043735156064267696**；Rainbow 20 样本、`fraction=0.5` → statistic **37.09507275139439**、df1 **10**、df2 **8**、p **1.298882331413825e-05**，中心子样本 **6..15**。
- 0.54 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 306/82/21；参考页 306 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 252 passed。
- 边界：两个算子均只支持单个响应 + 单个自变量 + 截距；Goldfeld-Quandt 的 `fraction` 是比例（[0,0.5)），Rainbow 的 `fraction` 是中心子样本比例（(0,1)），`center` ± `fraction/2` 必须在 [0,1]；输入缺失值会从拟合中剔除。

## 55. 0.55.0 扩展证据

- 新增 3 个分布/多元结构算子：`anscombe_glynn`（Anscombe-Glynn 峰度检验，two-sided/greater/less）、`bonett_seier`（Bonett-Seier Geary 峰度检验）、`mauchly_test`（Mauchly 球形检验，卡方近似）。
- `tests/test_extension48.py` 4 项、`tests/test_r_oracles39.py` 1 项，合计 **5 passed**；Anscombe/Bonett 对照 R `moments`，Mauchly 对照 base R `stats:::mauchly.test.SSD`。
- R 参考值：Anscombe 12 样本 → kurt **2.1341104474559254**、z **-0.42227346311066044**、p **0.6728254253719288**；Bonett → tau **4.9861111111111107**、z **-1.0951999132137393**、p **0.27342906371823772**；Mauchly 6 样本 × 3 特征 → W **0.00012919496245979595**、chi2 **33.329477397827**、df **5**、p **7.0069860189294373e-06**。
- 0.55 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 309/82/21；参考页 309 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 255 passed。
- 边界：Anscombe-Glynn 要求 n≥8 且方差非零，Bonett-Seier 要求 n≥3；Mauchly 要求至少 3 个特征、样本数大于特征数、协方差非奇异、无缺失值；Mauchly 使用卡方近似（含 w2 修正），不是精确分布。

## 56. 0.56.0 扩展证据

- 新增 3 个有序/对照组秩检验：`chacko_test`（有序备择）、`fligner_wolfe`（对照组 vs 其余，正态近似 + 并列校正）、`mack_wolfe`（已知峰伞形检验，正态近似）。
- `tests/test_extension49.py` 4 项、`tests/test_r_oracles40.py` 1 项，合计 **5 passed**；全部对照 R `PMCMRplus::chackoTest`、`flignerWolfeTest(dist="Normal")`、`mackWolfeTest(p=3)`。
- R 参考值：Chacko 4 组×6 → H **5.6716666666666651**、df 3、p **0.12872406680233608**；Fligner-Wolfe 对照 A → z **1.9503674363248837**、p **0.025566170105179833**；Mack-Wolfe 峰值 C → Ap **98**、z **1.6001893827313254**、p **0.054778288391342869**。
- 0.56 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 312/82/21；参考页 312 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 258 passed。
- 边界：三个算子均要求每组至少 2 个有限值；Fligner-Wolfe 的 `control` 必须在组顺序中且被置首；Mack-Wolfe 需要 `peak` 且只做单侧 greater；Chacko 只做 greater/less；均为秩/正态近似，不声称精确分布；Mack-Wolfe 有并列时精确方差不可用。

## 57. 0.57.0 扩展证据

- 新增 3 个全成对均值比较算子：`tukey_test`（等方差合并 MSE、studentized range）、`tamhane_t2`（Welch df + Sidak）、`snk_test`（Student-Newman-Keuls step-down）。
- `tests/test_extension50.py` 4 项、`tests/test_r_oracles41.py` 1 项，合计 **5 passed**；对照 R `PMCMRplus::tukeyTest`、`tamhaneT2Test`、`snkTest`。
- R 参考值（A=1..5、B=2..12 step2、C=10..18 step2、D=9..21 step2；n=5/6/5/7）：
  - Tukey p：B-A **0.26502273475490234**、C-A **0.00044739595759790696**、D-A **6.5625131024704686e-05**、C-B **0.017760584803845236**、D-B **0.0030277846633985916**、D-C **0.96066284890560794**。
  - Tamhane T2 p：B-A **0.26157925285918715**、C-A **0.0028593777811823928**、D-A **0.00085746647125883868**、C-B **0.049165728391977526**、D-B **0.025759111282225411**、D-C **0.99826546041815489**。
  - SNK p：B-A **0.074054575763289443**、C-A **0.00023621084901115363**、D-A **6.5625131024704686e-05**、C-B **0.003696209233425396**、D-B **0.0016288889014157704**、D-C **0.63062071739806569**。
- 0.57 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 315/82/21；参考页 315 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 261 passed。
- 边界：三个算子都要求每组至少 2 个有限值；Tukey 使用合并方差和 studentized range；Tamhane 使用 Welch df 与 Sidak 全成对校正；SNK 为 step-down，不做单调化；均为近似分布，不声称精确。

## 58. 0.58.0 扩展证据

- 新增 3 个聚类验证/一致性算子：`silhouette_score`（欧氏距离均值轮廓系数）、`adjusted_rand_index`（两划分调整兰德指数）、`normalized_mutual_info`（arithmetic/geometric/max/min 四种归一化）。
- `tests/test_extension51.py` 4 项、`tests/test_r_oracles42.py` 1 项，合计 **5 passed**；对照 R `cluster::silhouette`、`aricode::ARI`、`aricode::NMI`。
- R 参考值（6 样本 2 维；labels A=[0,0,0,1,1,1]、B=[0,0,1,1,1,1]）：
  - silhouette **0.9722473303668445**；ARI **0.32432432432432434**。
  - NMI arithmetic **0.47870397138568005**、geometric **0.4791387674918639**、max **0.45914791702724483**、min **0.5**。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 318/82/21；参考页 318 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 264 passed。
- 边界：轮廓系数要求 2 个及以上簇且每簇至少 2 个样本；ARI/NMI 只使用两表共享样本，缺失标签报错；NMI 参数只允许 arithmetic/geometric/max/min；均为确定性指标。

## 59. 0.59.0 扩展证据

- 新增 3 个聚类验证/一致性算子：`dunn_index`（最小簇间距离/最大簇内直径）、`adjusted_mutual_info`（调整互信息）、`silhouette_samples`（逐样本轮廓系数）。
- `tests/test_extension52.py` 4 项、`tests/test_r_oracles43.py` 1 项，合计 **5 passed**；对照 R `clusterCrit`、`aricode`、`cluster`。
- R 参考值（6 样本 2 维；labels [0,0,0,1,1,1] 与 [0,0,1,1,1,1]）：
  - Dunn **30.67572330035593**。
  - AMI max **0.33746780635745904**。
  - silhouette samples **0.9689982614384166 / 0.9739300984276602 / 0.9739300984276602 / 0.9677329920415768 / 0.9744462659328769 / 0.9744462659328769**。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 321/82/21；参考页 321 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 267 passed。
- 边界：Dunn 与逐样本轮廓要求至少 2 簇且每簇至少 2 个样本；Dunn 簇内直径为零时报错；AMI 默认 max 归一化以对齐 R `aricode`，也支持 arithmetic/geometric/min。

## 60. 0.60.0 扩展证据

- 新增 3 个确定性算子：`box_pierce`（时间序列自相关）、`stuart_maxwell_test`（方形列联表边际齐性）、`variation_of_information`（两分区变异信息及按联合熵归一化值）。
- `tests/test_extension53.py` 4 项、`tests/test_r_oracles44.py` 1 项，合计 **5 passed**；对照 R `stats::Box.test(type="Box-Pierce")`、`DescTools::StuartMaxwellTest`、`aricode::NVI`。
- R 参考值：
  - Box-Pierce x=[1,2,3,4,5,4,3,2,1,2,3,4]，lag=3 → Q **7.5205292512163302**、df **3**、p **0.057033307356141538**。
  - Stuart-Maxwell 3×3 表 `[[20,10,5],[8,25,7],[6,9,30]]` → statistic **0.53474320241691853**、df **2**、p **0.76538859928510916**、N **120**。
  - 变异信息 labels A=[1,1,1,2,2,2,3,3,3]、B=[1,1,2,2,3,3,1,2,3] → VI **1.5810937501718234**、NVI **0.83692987891500414**、MI **0.3080654135821979**、联合熵 **1.8891591637540217**。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 324/82/21；参考页 324 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 270 passed。
- 边界：Box-Pierce 用样本自相关 `rho_k=sum((x_t-mean)(x_{t-k}-mean))/sum((x-mean)^2)`、`Q=n*sum(rho_k^2)`，要求 `lags < n`、`fitdf < lags`；Stuart-Maxwell 要求非负方形表、协方差可逆，等边际类别按 R 方式剔除；变异信息使用自然对数，NVI=VI/H(A,B)，两表按共享样本对齐，缺失标签报错。

## 61. 0.61.0 扩展证据

- 新增 3 个序列/评估算子：`acf`（样本自相关与 Bartlett 置信区间）、`pacf`（Yule-Walker 偏自相关与正态置信区间）、`precision_recall_curve`（二分类 precision-recall 曲线与 average precision）。
- `tests/test_extension54.py` 4 项、`tests/test_r_oracles45.py` 1 项，合计 **5 passed**；ACF/PACF 对照 R `stats::acf`/`stats::pacf`，PR 对照 sklearn `precision_recall_curve`/`average_precision_score`。
- R 参考值（x=[1,2,3,4,5,4,3,2,1,2,3,4]，lags=5）：
  - ACF lag1..5 **0.55503144654088044 / -0.05974842767295601 / -0.56132075471698117 / -0.66666666666666652 / -0.33805031446540873**。
  - PACF lag1..5 **0.55503144654088044 / -0.53156095138395143 / -0.43409697205350251 / -0.21794716741019138 / 0.0096932454921819424**。
- PR 参考（labels [0,1,0,1,1,0,1,1]，scores [.1,.4,.2,.8,.9,.3,.7,.6]）：AP **1.0**；首点 precision **0.625**、recall 1、threshold 0.1；末点 precision 1、recall 0、threshold NaN。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 327/82/21；参考页 327 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 273 passed。
- 边界：ACF 要求 `lags < n` 且序列非常量，默认 `bartlett_confint=True`；PACF 使用 `method="ywm"`，置信区间为正态近似；PR 曲线要求至少 4 个共享样本且两类都存在，`drop_intermediate=False`，末尾补 NaN threshold 点。

## 62. 0.62.0 扩展证据

- 新增 3 个聚类一致性算子：`fowlkes_mallows`（成对 precision/recall 几何均值）、`homogeneity_completeness_v_measure`（熵基同质性、完整性、V-measure）、`pair_confusion_matrix`（同簇/异簇与同标签/异标签的成对计数）。
- `tests/test_extension55.py` 4 项、`tests/test_r_oracles46.py` 1 项，合计 **5 passed**；FMI/HCV/PCM 用 sklearn 固定参考值，PCM 的 Rand 关系另对 R `aricode::RI`。
- 参考值（A=[0,0,0,1,1,1,2,2,2]，B=[0,0,0,1,1,2,2,1,1]，n=9）：
  - Fowlkes-Mallows **0.5270462766947299**。
  - homogeneity **0.5793801642856953**、completeness **0.6000000000000002**、V-measure **0.5895098274473051**（beta=1）。
  - 成对混淆矩阵 `[[44,10],[8,10]]`；Rand index **0.75**。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 330/82/21；参考页 330 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 276 passed。
- 边界：两个分区都必须至少有 2 个簇、至少 2 个共享样本；成对矩阵按 `pair_confusion_matrix` 返回 `[同簇同标签, 同簇异标签; 异簇同标签, 异簇异标签]`；H/C/V 的 beta 必须大于 0。

## 63. 0.63.0 扩展证据

- 新增 3 个时间序列诊断算子：`cross_correlation`（Pearson 滞后互相关）、`bds_test`（BDS 非线性依赖）、`difference_sign`（差分符号随机性）。
- `tests/test_extension56.py` 4 项、`tests/test_r_oracles47.py` 1 项，合计 **5 passed**；CCF/差分符号对照 R `stats::ccf`/`randtests::difference.sign.test`，BDS 对照 statsmodels。
- 参考值：CCF x=[1,2,3,4,5,4,3,2,1]、y=[2,1,2,4,5,6,5,8,7]、lags −3..3 → **0.46271424434198255 / 0.4797494951287023 / 0.43048539150224246 / 0.07044306406400333 / -0.31952605529685163 / -0.47744743421157804 / -0.6312251034754807**；差分符号 z **1.4411533842457842**、p **0.14954135458461512**；BDS（12 点、max_dim=2、eps=0.5）statistic **4.940627273908729**、p **7.787164227744485e-07**。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 333/82/21；参考页 333 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 279 passed。
- 边界：CCF 要求 `lags < n` 且两条序列均非常量；差分符号剔除零差分，要求至少两个非零差分；BDS 要求 `max_dim >= 2`、`n >= max_dim + 2`、非常量，epsilon 缺省为 0.5×标准差。

## 64. 0.64.0 扩展证据

- 新增 3 个 2×2 表效应量算子：`risk_ratio`（暴露/非暴露风险比与 Wald log CI）、`odds_ratio`（比值比与 Woolf log CI）、`cohens_h`（两个独立比例的 Cohen's h 与正态 CI）。
- `tests/test_extension57.py` 4 项、`tests/test_r_oracles48.py` 1 项，合计 **5 passed**；RR/OR 对照 R 公式与 `epitools`，Cohen's h 对照 R `pwr::ES.h`。
- 参考值（表 `[[18,12],[10,20]]`）：RR **1.8**、95% CI **1.0034442222671074..3.2288790229712867**；OR **3.0**、95% CI **1.0461986908532277..8.602572416392574**；Cohen's h **0.5411948302444529**、95% CI **0.035134305491788975..1.0472553549971169**。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 336/82/21；参考页 336 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 282 passed。
- 边界：输入必须是非负 2×2 计数表；RR 以第 1 行为暴露、第 2 行为非暴露，OR 的 `a*d/(b*c)` 与 RR 方向一致；零格默认 Haldane +0.5，可用 `correction="none"` 禁用；Cohen's h 只要求每行有观测，不对零格做校正。

## 65. 0.65.0 扩展证据

- 新增 3 个推断/一致性算子：`variance_ratio`（两独立样本方差比、F 检验与 CI）、`youden_index`（ROC 上最大化 Youden J 的阈值）、`krippendorff_alpha`（nominal/interval 评分者一致性，支持缺失评分）。
- `tests/test_extension58.py` 4 项、`tests/test_r_oracles49.py` 1 项，合计 **5 passed**；方差比对照 R `stats::var.test`，Krippendorff 对照标准公式与 R `irr::kripp.alpha`。
- 参考值：x=1..5 vs y=2,4,6,8,10 方差比 F **0.25**、df **4/4**、p **0.20800000000000005**、95% CI **0.026029384363481924..2.4011324711807167**；Youden 标签/分数 fixture 阈值 **0.4**、sens **1.0**、spec **0.8**、J **0.8**、n_pos/n_neg **5/5**；Krippendorff 完整 4×4 nominal **-0.1052631578947365**、interval **-0.20578778135048226**，含一个缺失值的同一 fixture nominal **-0.08130081300812986**、interval **-0.1192411924119241**。
- R `irr::kripp.alpha` 0.84.1 在无缺失数据时使用错误分母（`mc <- rep(1, dimx[2])`），与标准公式不一致；R oracle 用带一个缺失值的 fixture，完整数据由标准公式手算验证。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 339/82/21；参考页 339 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 285 passed。
- 边界：方差比每组至少 2 个有限值且方差非零；Youden 要求二分类标签与连续分数；Krippendorff 至少 2 个 subject、2 个 rater、2 个类别，缺失值按该 subject 的可用评分数加权，期望不一致为零时拒绝。

## 66. 0.66.0 扩展证据

- 新增 3 个回归影响诊断算子：`leverage`（OLS hat 矩阵对角）、`cooks_distance`（Cook 距离）、`dffits`（DFFITS）。
- `tests/test_extension59.py` 4 项、`tests/test_r_oracles50.py` 1 项，合计 **5 passed**；三项均对照 R `lm` 的 `hatvalues`/`cooks.distance`/`dffits`。
- 参考 fixture：x=1..10、y=2+0.5x+[1,-1,2,-2,0,1,-1,2,-2,0]。leverage **0.34545454545454546, 0.24848484848484845, 0.17575757575757578, 0.12727272727272729, 0.10303030303030304, 0.10303030303030303, 0.12727272727272726, 0.17575757575757578, 0.24848484848484853, 0.34545454545454546**；Cook D **0.074610468585066189, 0.14158186949003726, 0.17485946926332305, 0.15197748864105742, 3.4622183722957693e-05, 0.028121868728972085, 0.027117861937215996, 0.25179763573918529, 0.27406395908846498, 0.017657992565055805**；DFFITS **0.36790202489736512, -0.52675565099872412, 0.62041477016880719, -0.59972093542830984, -0.0077841754527546549, 0.22895812359793719, -0.22309180205911905, 0.7907064769401313, -0.77780081929838962, 0.17652800580145919**。
- 公式：OLS 含截距，`h=diag(X inv(X'X) X')`；Cook `e²/(p*mse)*h/(1-h)²`；DFFITS `e/sqrt(s2_i)*sqrt(h)/(1-h)`，`s2_i=(SSE-e²/(1-h))/(n-p-1)`。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 342/82/21；参考页 342 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 288 passed。
- 边界：输入为含响应列的 OLS 设计表；listwise 删除缺失行；要求 `n > p+1`、满秩、杠杆值不接近 1；p 含截距。

## 67. 0.67.0 扩展证据

- 新增 3 个 OLS 残差诊断算子：`standardized_residuals`（标准化残差）、`studentized_residuals`（学生化/删除残差）、`press`（预测误差平方和与 RMSE）。
- `tests/test_extension60.py` 4 项、`tests/test_r_oracles51.py` 1 项，合计 **5 passed**；三项均对照 R `lm` 的 `rstandard`/`rstudent` 与 PRESS 公式。
- 参考 fixture：x=1..10、y=2+0.5x+[1,-1,2,-2,0,1,-1,2,-2,0]。标准化残差 **0.531727756723047618, -0.925417554187445868, 1.280648753153083019, -1.443697579606987080, -0.024552664144405371, 0.699750928115549509, -0.609837770696054715, 1.536778503783700067, -1.287537466695575450, 0.258678368135536407**；学生化残差 **0.506415078205768143, -0.916068854139824862, 1.343546134340419584, -1.570438047114258939, -0.022967779665450629, 0.675557709012263419, -0.584191468491439103, 1.712323241759369008, -1.352655835647444293, 0.242989811997891242**；PRESS **29.579274620026872**，PRESS RMSE **1.719862628817397**。
- 公式：OLS 含截距；标准化残差 `e/(s*sqrt(1-h))`；学生化残差 `e/(s_i*sqrt(1-h))`，`s_i²=(SSE-e²/(1-h))/(n-p-1)`；PRESS `sum((e/(1-h))²)`，RMSE `sqrt(PRESS/n)`。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 345/82/21；参考页 345 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 291 passed。
- 边界：输入为含响应列的 OLS 设计表；listwise 删除缺失行；要求 `n > p+1`、满秩、杠杆值不接近 1；p 含截距。

## 68. 0.68.0 扩展证据

- 新增 3 个未加权评分者一致性系数：`gwet_ac1`（Gwet AC1）、`brennan_prediger`（Brennan-Prediger）、`conger_kappa`（Conger kappa）。
- 输入为一个 `[subject,rater]` 数值评分矩阵；类别按唯一值排序；每名受试者至少 2 个评分；允许缺失，但 Conger 要求每名评分者至少 2 个评分。
- `tests/test_extension61.py` 4 项、`tests/test_r_oracles52.py` 1 项，合计 **5 passed**；R 对照 `irrCAC::gwet.ac1.raw`、`bp.coeff.raw`、`conger.kappa.raw`。
- 参考 fixture：5×4 `[[1,2,3,3],[2,1,1,2],[2,3,3,2],[1,1,2,3],[3,1,2,2]]`。Gwet AC1 **-0.14427860696517408**（pa 0.2333333333333333，pe 0.32999999999999996）；Brennan-Prediger **-0.15**（pe 0.3333333333333333）；Conger **-0.11650485436893211**（pe 0.31333333333333335）。
- 公式：`pa = mean_subject[sum_c n_ic(n_ic-1)/(r_i(r_i-1))]`；AC1 `pe = sum_c pi_c(1-pi_c)/(q-1)`；Brennan-Prediger `pe=1/q`；Conger `pe = sum_c mean_p_c² - trace(S)/r`；`coeff=(pa-pe)/(1-pe)`。
- 边界：仅实现未加权系数；`irrCAC` 的系数输出只保留约 5 位小数，R oracle 用 `abs=1e-5`，手算测试验证完整精度。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 348/82/21；参考页 348 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 294 passed。

## 69. 0.69.0 扩展证据

- 新增 2 个非线性序列算子：`approx_entropy`（近似熵 ApEn）、`hurst_exponent`（简单 R/S Hurst 指数）。
- `approx_entropy`：一个 `[sample,feature]` 数值表；默认 `embedding_dim=2`、`radius=0.2*sd`；`ApEn=phi(m)-phi(m+1)`，phi 为嵌入向量在 Chebyshev 距离 r 内的平均对数比例（含自身）；要求 5–2000 个有限值且方差非零。
- `hurst_exponent`：一个 `[sample,feature]` 数值表；先按 R `pracma::hurstexp` 约定把奇数长度序列用最后两个值的均值补齐，再计算 `H=log((max(cumsum(x-mean))-min(cumsum(x-mean)))/sd(x))/log(n)`。
- `tests/test_extension62.py` 4 项、`tests/test_r_oracles53.py` 1 项，合计 **5 passed**；R 对照 `pracma::approx_entropy` 与 `hurstexp(..., display=FALSE)$Hs`。
- 参考 fixture：`round(sin(linspace(0,8*pi,100))+0.1*arange(100)/100,1)`。ApEn **0.19343740801454112**；Hurst **0.54431529367338694**，n=100，奇数 99 点补齐为 100。
- 边界：`approx_entropy` 的 `embedding_dim` 限 1–5，序列上限 2000；`hurst_exponent` 只实现简单 R/S 估计，不输出 `hurstexp` 的 Hrs/He/Hal/Ht 四种估计。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 350/82/21；参考页 350 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 296 passed。

## 70. 0.70.0 扩展证据

- 新增 2 个时间序列协整算子：`engle_granger`（Engle-Granger 残差 ADF）和 `johansen`（Johansen 迹/最大特征值秩检验）。
- `engle_granger`：一个 `[sample,feature]` 表，`y_label`/`x_label` 指定二元变量；`trend` 为 `c`/`ct`/`ctt`，`lags` 为手动滞后或 `null` 时 AIC 自动选滞后；输出 `statistic,p,n,critical_1pct,critical_5pct,critical_10pct`。
- `johansen`：一个 `[sample,feature]` 表，每一列是一个变量；`det_order` 为 -1/0/1，`k_ar_diff` 为差分滞后；输出秩×9：trace/max-eig 统计量及 90/95/99% 临界值、特征值。
- `tests/test_extension63.py` 4 项、`tests/test_r_oracles54.py` 1 项，合计 **5 passed**；R 对照 `urca::ur.df` 与 `urca::ca.jo`。
- EG fixture：seed 20261031，`x=cumsum(rnorm(160))`，`y=1.5*x+rnorm(sd=.6)`；`coint(lags=2)` 统计量 **-6.365675416103156**，p **2.536310715415716e-07**，1/5/10% 临界值 **-3.96664605 / -3.37482819 / -3.0712318**，n=160；R `ur.df(resid,type="none",lags=2)` 统计量完全一致。
- Johansen fixture：`det_order=0,k_ar_diff=1` trace **[72.01098429,4.14697157]**，max-eig **[67.86401273,4.14697157]**，eigen **[0.34917798,0.02590521]**；R `ca.jo(type="trace",ecdet="none",K=2)` 的 `@teststat` 逆序为 **[4.146971568,72.01098429]**，`type="eigen"` 为 **[4.146971568,67.86401273]**。
- 边界：EG 仅二元、仅 `aeg` 方法；Johansen 要求完整样本且每个变量方差非零；两算子均直接使用 statsmodels 临界值表，不声称与 R `urca` 临界值逐位相同。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 352/82/21；参考页 352 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 298 passed。

## 71. 0.71.0 扩展证据

- 新增 2 个推断算子：`zivot_andrews`（结构突变单位根检验）和 `poisson_means_test`（精确两样本泊松率检验）。
- `zivot_andrews`：一个 `[sample,feature]`，`regression` 为 `c`/`t`/`ct`，`trim` 默认 0.15，`lags` 为手动滞后或 `null` 时 AIC；输出 `statistic,p,break_index,lag,n,critical_1pct,critical_5pct,critical_10pct`。共享 fixture：seed 20261101，80 点 `cumsum(rnorm(80)) + [0]*40 + [3]*40`；statsmodels `regression="c", maxlag=2` 统计量 **-3.7254940402358883**，p **0.5295691048518368**，`break_index=57`（零基），`lag=2`；R `urca::ur.za(model="intercept",lag=2)` 的 teststat 完全一致，bpoint=58（一基）。
- `poisson_means_test`：一个 `[feature,sample]` 计数表 + `[sample,group]` 分组表；条件二项精确检验，`alternative` 为 two-sided/less/greater，`confidence` 默认 0.95；输出 `count_a,count_b,n_a,n_b,rate_a,rate_b,rate_ratio,p,ci_low,ci_high`。100/4 vs 50/4 fixture：p **5.4475331033925765e-05**，rate ratio **2**，95% CI **1.4105504610094759 / 2.8676286550257819**；R `poisson.test(c(100,50),T=c(4,4))` 一致。总计数为 0 时 p=1，rate ratio/CI 为 NaN。
- `tests/test_extension64.py` 4 项、`tests/test_r_oracles55.py` 1 项，合计 **5 passed**；R 对照 `urca::ur.za` 与 `poisson.test`。
- 边界：Zivot-Andrews 使用 statsmodels 临界值表，测试只比较统计量与断点，不声称与 R `urca` 临界值逐位相同；泊松检验不使用 scipy 的 E-test（`poisson_means_test`），因其 p 值与 R 条件二项结果不同。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 354/82/21；参考页 354 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 300 passed。

## 72. 0.72.0 扩展证据

- 新增 3 个算子：`theil_u`（Theil 不确定系数）、`dfbetas`（标准化 DFBETAS）、`covratio`（COVRATIO 协方差比）。
- `theil_u`：一个 `[row,column]` 列联表，要求至少 2×2、非负计数、行列边际均大于 0；输出 `u_row_given_column`、`u_column_given_row`、`u_symmetric` 及三个熵。2×2 fixture `[[10,20],[30,40]]`：U(row|col) **0.006583693**，U(col|row) **0.005975741**，U(symmetric) **0.006265003**；R `DescTools::UncertCoef` 一致。
- `dfbetas`：一个 `[sample,feature]` OLS 表，`response` 指定响应列，其余列作预测变量；输出 `[sample,coefficient]`，系数顺序为 `intercept` + 预测变量；8×3 fixture（y/x1/x2）首行 **1.685224359 / -1.29852524 / 0.69920590**；R `stats::dfbetas` 一致。
- `covratio`：同一个 OLS 表；输出每样本 COVRATIO；fixture **0.4017102, 1.0186115, 0.2800875, 1.6334704, 2.4723222, 2.4723222, 3.6721322, 3.6721322**，最小值在 s2，最大值在 s6/s7（并列）；R `stats::covratio` 一致。
- `tests/test_extension65.py` 4 项、`tests/test_r_oracles56.py` 1 项，合计 **5 passed**。
- 边界：DFBETAS 使用留一残差方差与 `(X'X)^-1` 标准化；COVRATIO 使用 R `stats::covratio` 同一公式；Theil U 只支持二维列联表，不提供 DescTools 的置信区间。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 357/82/21；参考页 357 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 303 passed。

## 73. 0.73.0 扩展证据

- 新增 3 个时间序列算子：`phillips_perron`（Phillips-Perron Z-tau 单位根）、`dfgls`（DF-GLS 单位根）、`arch_lm`（Engle ARCH LM 条件异方差检验）。
- `phillips_perron`：一个 `[sample,feature]`，`trend` 为 `c`/`ct`，`lags` 为固定滞后或 `null` 时 AIC；输出 `statistic,p,lags,nobs,n,critical_1pct,critical_5pct,critical_10pct`。fixture seed 20261102、120 点 `cumsum(rnorm(120))`，`lags=2, trend=c`：统计量 **-1.9273077985416451**，p **0.31932569624470114**，nobs **119**；R `urca::ur.pp(type="Z-t",model="constant",lags="short",use.lag=2)` 统计量 **-1.9273080452513796**，差异 <1e-6（长程方差带宽实现不同），测试按 1e-6 对齐。
- `dfgls`：同样的单序列输入，`trend` 为 `c`/`ct`，`lags` 为固定滞后或 `null` 时 AIC；输出含 `max_lags`。fixture 同上，`lags=2`：统计量 **-1.74135623062118**，p **0.08039437046328551**，nobs **117**；R `urca::ur.ers(type="DF-GLS",model="constant",lag.max=2)` 统计量 **-1.7413562306211814**，逐值一致。
- `arch_lm`：一个残差序列，`lags` 默认 12；输出 `statistic,p,df,f_statistic,f_p,lags,n`。fixture seed 20261102、200 个 t(5) 残差、`lags=5`：LM **4.186145832492666**，p **0.5229387617060965**，F **0.829270564019495**，F p **0.5303006600082081**；R `FinTS::ArchTest(e,lags=5)` 逐值一致。
- `tests/test_extension66.py` 4 项、`tests/test_r_oracles57.py` 1 项，合计 **5 passed**；R 对照 `urca::ur.pp`、`urca::ur.ers`、`FinTS::ArchTest`。
- 边界：Phillips-Perron 只实现 Z-tau，不实现 Z-alpha；`arch` 与 R `urca` 的 PP 长程方差带宽细节不同，统计量按 1e-6 容差比较，临界值只作参考不逐位断言；DF-GLS 固定滞后时与 R 对齐，`lags=null` 使用 arch 的 AIC 选择；ARCH LM 输入按残差处理，不拟合均值模型。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 360/82/21；参考页 360 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 306 passed。


## 74. 0.74.0 扩展证据

- 新增 2 个统计过程控制算子：`cusum_chart`（双侧 tabular CUSUM 控制图）、`ewma_chart`（EWMA 控制图）。
- `cusum_chart`：一个单序列 `[sample,feature]`，`value_label` 指定列；`decision_interval` 默认 5，`se_shift` 默认 1；用平均移动极差 / 1.128 估计 sigma；输出 `cusum_pos,cusum_neg,center,std_dev,limit,out_of_control`。12 点 fixture `10,12,11,13,12,14,13,15,14,16,15,17`：center 13.5、sigma **1.3700838168923277**；`cusum_pos` 末值 **4.4338823529411755**，`cusum_neg` 首值 **-2.0545882352941174**；R `qcc::cusum(sizes=1,decision.interval=5,se.shift=1)` 逐值一致。
- `ewma_chart`：同样单序列输入；`lambda` 默认 0.2、`nsigmas` 默认 3；sigma 同样由移动极差估计；输出 `ewma,center,lcl,ucl,std_dev,out_of_control`，上下限按随时间变化的 EWMA 方差计算。同一 fixture：首值 **12.8**，末值 **14.688383963136**；首行 LCL/UCL **12.677949709864604 / 14.322050290135396**；R `qcc::ewma(sizes=1,lambda=0.2,nsigmas=3)` 逐值一致。
- `tests/test_extension67.py` 4 项、`tests/test_r_oracles58.py` 1 项，合计 **5 passed**；R 对照 `qcc::cusum`、`qcc::ewma`。
- 边界：只处理单个 `value_label` 序列；CUSUM 的 `limit` 为决策区间 h，`se_shift` 对应 qcc 的 `se.shift`，内部取半位移 k=se_shift/2；EWMA 的限随时间收敛，不是常数限；两个算子只输出表，不直接画图；`out_of_control` 为 0/1 数值列。常数序列因移动极差为 0 被拒绝。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 362/82/21；参考页 362 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 308 passed。


## 75. 0.75.0 扩展证据

- 新增 2 个算子：`correspondence_analysis`（对应分析/CA）与 `tobit`（左删失正态回归）。
- `correspondence_analysis`：一个非负计数表 `[row,column]`，行/列边际必须为正；`n_components` 默认 2，并截断到 `min(n_rows-1,n_cols-1)`；输出主表为 `[point,component]` 的主坐标（行点前缀 `row:`、列点前缀 `column:`），info 给出总惯量、卡方、df、p。4×3 fixture `[[10,20,30],[20,40,20],[30,10,10],[15,25,35]]`：奇异值 **0.34920690627954476 / 0.19981461817371882**，总惯量 **0.16187134502923978**，卡方 **42.89590643274854**，df 6；`n_components=1` 的累计解释率 **0.7533**。R `ca::ca` 对标准坐标/奇异值逐值一致。
- `tobit`：一个 `[sample,feature]` 表，`response_label` 与 `predictors` 必填，`categorical` 可选，默认在 0 处左删失并含隐式截距；输出 `[term,statistic]` 的 `coef,se,z,P,CI_low,CI_high`，info 给出 `sigma,loglik,n_censored`。fixture seed 20261103、n=60、11 个左删失：coef **1.10646400866156114 / 0.91970907755316011 / -0.60664699838834946**，se **0.11553127141226120 / 0.11778270999030564 / 0.12791704775948415**，sigma **0.8373168628959122**，loglik **-67.507455881612927**；R `censReg` 系数/se 对照容差 2e-6，loglik 1e-8。
- `tests/test_extension68.py` 4 项、`tests/test_r_oracles59.py` 1 项，合计 **5 passed**；R 对照 `ca::ca`、`censReg`。
- 边界：CA 只接受非负计数表，行/列边际为 0 会拒绝；只输出坐标/贡献/cos2，不画图；贡献/cos2 在返回分量内计算，cos2 使用全维距离。Tobit 只实现左删失；全删失、设计矩阵秩亏、观测数不足会拒绝；SE 由数值 Hessian 计算，不提供稳健/聚类 SE。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 364/82/21；参考页 364 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 310 passed。


## 76. 0.76.0 扩展证据

- 新增 2 个时间序列算子：`garch`（GARCH 波动率模型）与 `var_model`（向量自回归）。
- `garch`：一个 `[sample,feature]` 单序列，`value_label` 必填；`mean` 支持 Constant/Zero，`p`/`q` 为 1–3，`dist` 支持 normal/t；输出 `[parameter,statistic]` 的 `coef,se,t,p`，info 给出 loglik/aic/bic/nobs/persistence；导出条件波动率、残差和标准化残差。fixture seed 20261104、300 点 GARCH(1,1)：coef **0.12545912769161274 / 0.21557564103295726 / 0.04612526785494381 / 0.7269061346242348**，persistence **0.7730314024791786**，loglik **-417.4502100666318**，nobs 300；`arch` 8.0.0 拟合值逐值对齐。
- `var_model`：一个 `[sample,feature]` 且至少两列，`lags` 默认 1，`trend` 为 c/n/ct；`statsmodels VAR(...).fit(lags, trend=...)`；输出 `[equation,term]` 的 `coef,se,t,p`，info 给出 llf/aic/bic/hqic/nobs/neqs/lags。fixture seed 20261105、120×2 VAR(1)：y1 方程系数 **-0.03397482 / 0.39825042 / 0.12134407**，y2 方程系数 **0.06367029 / 0.17068698 / 0.40692885**，llf **-137.21370301647985**，nobs 120；R `vars::VAR(...)` 系数逐值一致。
- `tests/test_extension69.py` 4 项、`tests/test_r_oracles60.py` 1 项，合计 **5 passed**；R 对照 `vars::VAR`，GARCH 用 `arch` 8.0.0 拟合值。修复 `VarModelStep` 把 `table_frame` 的 `__sample__` 列误当特征、导致所有行被数值化丢弃的问题：先排除 `__sample__`，再检查至少两列并构造数据矩阵；单序列错误消息恢复为 `need at least two series`。
- 边界：GARCH 只实现常均值/零均值 GARCH，不实现 EGARCH/GJR/ARCH-in-mean；VAR 只输出简约式系数，不提供 IRF/FEVD/结构识别；两算子都只输出表，不直接画图。VAR 要求至少两个序列、完整观测足够、每列方差为正；GARCH 只接受单列数值序列。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 366/82/21；参考页 366 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 312 passed。


## 77. 0.77.0 扩展证据

- 新增 3 个功效/样本量计算算子：`power_t_test`（t 检验功效）、`power_prop_test`（两比例检验功效）、`power_anova`（单因素 ANOVA 功效）。三者均为无输入的计算算子，输出一张 `[statistic,value]` 表。
- `power_t_test`：`test` 为 two-sample/paired/one-sample，`effect_size` 为 Cohen d，`nobs1` 为每组/配对样本量，two-sample 可选 `nobs2` 或 `ratio`，`alternative` 为 two-sided/greater/less；输出 `power,effect_size,nobs1,nobs2,alpha,df`。fixture d=0.5、n=64：two-sample power **0.8014595579222542**，paired/one-sample **0.9760555768876558**；R `pwr.t.test` 对应值 **0.80145955792232759 / 0.97605557688772915**，差异 <1e-12。
- `power_prop_test`：`p1,p2` 为两比例，`nobs1,nobs2` 为两组样本量；Cohen h `2asin(sqrt(p1))-2asin(sqrt(p2))`，正态近似双侧检验；输出 `power,effect_size,p1,p2,nobs1,nobs2,alpha`。fixture p1=.6、p2=.4、n=100/100：h **0.40271584158066154**，power **0.8126408236244113**；R `pwr.2p.test(h=ES.h(.6,.4),n=100)` 一致。
- `power_anova`：`effect_size` 为 Cohen f，`n_per_group` 为每组样本量，`k_groups` 为组数；输出 `power,effect_size,n_per_group,n_total,k_groups,alpha,df1,df2`。fixture f=.25、n=40、k=4：power **0.7494045377009664**，df **3/156**；R `pwr.anova.test(k=4,n=40,f=.25)` 为 **0.74940453777624239**，差异 <1e-9。
- `tests/test_extension70.py` 4 项、`tests/test_r_oracles61.py` 1 项，合计 **5 passed**；R 对照 `pwr::pwr.t.test`/`pwr.2p.test`/`pwr.anova.test`。三算子均无输入，适合在路线中先估算样本量，再接入实际数据算子。
- 边界：只计算给定设计下的 achieved power，不反解样本量；t 检验使用 statsmodels 非中心 t 近似，与 R pwr 的差异在 1e-12 量级；两比例使用 Cohen h 正态近似，非精确二项功效；ANOVA 只支持平衡设计。输入参数在 schema 与运行期双重校验，alpha 必须在 (0,1)。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 369/82/21；参考页 369 算子 / 82 Reader；增量门 21 passed；`-W error` 7 passed；Studio 前端 315 passed。

## 78. 0.78.0 扩展证据

- 新增 2 个回归/约束排序算子：`beta_regression`（响应严格在 (0,1) 的 Beta 回归，均值 logit + 精度 identity）与 `redundancy_analysis`（RDA，响应矩阵对解释矩阵的约束排序）。
- `beta_regression`：一个 `[sample,feature]` 表；`response_label` 与 `predictors` 必填，可选 `categorical`；隐式截距；`phi=exp(precision)`，输出 `[row,statistic]` 的 `coef,se,z,P,CI_low,CI_high`，行为均值项和 `phi`；info 给出 logit/identity、llf/aic/bic。fixture seed 20261106、n=80、phi=8：coef **0.45218830829562068 / 0.74962773840681951 / -0.52970059447541096**，phi **8.44338203849741475**，SE **0.079304360738738172 / 0.081498782085493882 / 0.082805985258789488**，phi SE **1.2829694348069349**，loglik **44.157923586039978**；R `betareg` 一致，statsmodels Newton + `cov_type="eim"`，系数容差 2e-5、loglik 1e-7。
- `redundancy_analysis`：两个 `[sample,feature]` 输入（响应/解释）；按样本标签对齐、去非有限行、检查秩；中心化后 `B=lstsq(Xc,Yc)`，`fitted=Xc@B`，总/约束惯量除以 n−1；SVD 得特征值，输出 `[component,statistic]` 的 `eigenvalue,explained,cumulative`，explained 相对总惯量；导出 site/response/predictor scores。fixture seed 20261107、n=40、4 响应、2 解释变量：总惯量 **5.5116445710705815**，约束 **2.566316831991446**，非约束 **2.945327739079135**，特征值 **2.38249053751312445 / 0.18382629447832174**；R `vegan::rda` 一致（n−1 惯量，容差 1e-12）。
- `tests/test_extension71.py` 5 项、`tests/test_r_oracles62.py` 2 项，合计 **7 passed**；R 对照 `betareg`、`vegan`。参考页 371/82；增量门 23 passed；`-W error` 11 passed；Studio 前端 317 passed。
- 边界：Beta 回归不处理 0/1 膨胀，响应必须在开区间；RDA 不提供置换显著性，只做线性约束排序；两算子都不画图。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。

## 79. 0.79.0 扩展证据

- 新增 1 个证据综合算子：`meta_regression`（研究级效应量的逆方差 Meta 回归）。输入一个 `[study,feature]` 表，必填 `effect_label`、`variance_label`、`moderators`；隐式截距，可选分类 moderator；`method` 为 fixed 或 random（DL）。
- 输出 `[term,statistic]` 的 `coef,se,z,P,CI_low,CI_high`；info 给出 method、n_studies、n_parameters、tau2、Q、Q_p、I2。fixed 用 `1/vi` 权重；random 用 `1/(vi+tau2)`，tau2 分母为 `tr(P)=sum(w)-trace((X'WX)^-1 X'W^2X)`，不是单截距简化式。
- R `metafor 5.2-1` fixture seed 20261109、n=24、moderators x1/x2：fixed coef **0.5582954 / 0.3417866 / -0.2302585**，SE **0.06041857 / 0.05883369 / 0.05093128**，tau2 0，Q **109.27136626848096**，I2 **80.78179058509915**；random (DL) coef **0.5431708 / 0.3468496 / -0.2191853**，SE **0.1404448 / 0.1427122 / 0.1167862**，tau2 **0.34606677368814776**。
- `tests/test_extension72.py` 4 项、`tests/test_r_oracles63.py` 1 项，合计 **5 passed**；R 对照 `metafor::rma(..., method="FE"/"DL")`。参考页 372/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 318 passed。
- 边界：只做逆方差加权线性 moderator 回归，不做置换检验、发表偏倚或网状 Meta；random 仅 DerSimonian-Laird；方差必须为正；设计矩阵秩亏或有效研究数不足会拒绝。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。

## 80. 0.80.0 扩展证据

- 新增 3 个 GSEA 标准格式 Reader：`RnkReader`（`.rnk` 排名列表）、`ClsReader`（`.cls` 表型）、`GrpReader`（`.grp` 表型分组）。三者都是只读格式适配，不做富集统计或分组检验。
- `RnkReader`：输出 `[gene, feature]`，单列 `score`，严格保留文件顺序（preranked GSEA 依赖排名）；参数 `header`（默认 false）、`comment`（默认 `#`）、`gene_column`（默认 0）、`score_column`（默认 1）、`feature_label`（默认 `score`）。支持制表符或空白分隔；重复基因、非数值分数、非有限分数、空文件均拒绝；三列文件示例 `gene<TAB>description<TAB>score` 用 `score_column=2`。
- `ClsReader` / `GrpReader`：输出 `[sample, feature]`，单列类别编码；解析 `<n_samples> <n_classes> [1]`、`# class0 class1 ...`、逐样本类索引；样本名为 `S1..Sn`；类别名写入 `info["encoders"]["feature"]["class"]`，`group_values` 可还原为原始类别；计数/索引越界/重复类名/缺少 `#` 均拒绝。`.grp` 与 `.cls` 共用严格解析器，但保留独立扩展名与 Reader 选择。
- `tests/test_extension73.py` 覆盖 7 项：RNK 顺序与编码、RNK 表头/三列、重复与非数值、CLS 类别编码、GRP 编码与 dispatch、坏计数/越界/缺 `#`、自定义 `feature_label` 与 encoder 覆盖；合计 **7 passed**。格式类 Reader 无 R oracle，使用黄金文件与严格负例；不新增前端交互。
- 边界：RNK 只读取排名分数，不解析 GSEA 的 `.gct` 表达矩阵（已有 `GctReader`）；CLS/GRP 只支持标准空格/换行分隔，不支持每样本多列注释；类别名含空格会被 split 拆开，需先用标准 GSEA 命名。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 372/85/21；参考页 372 算子 / 85 Reader；增量门 23 passed；Studio 前端 318 passed（无新增算子图标）。


## 81. 0.81.0 扩展证据

- 新增 3 个回归/多元算子：`inverse_gaussian_regression`（逆高斯 GLM，log link）、`betadisper`（PCoA 质心距离的组间离散度检验）、`zero_inflated_negative_binomial`（NB2 零膨胀回归）。
- 逆高斯：一个 `[sample,feature]` 表，`response_label` 与 `predictors` 必填，隐式截距；输出 `[term,statistic]` 的 `coef,se,z,P,CI_low,CI_high,exp_coef`；info 含 deviance/null_deviance/aic/n。fixture seed 20261110 n=60：coef **0.29112628016820374 / 0.31847495391789 / -0.22659950198706433**，SE **0.1160139475750473 / 0.08959275775038143 / 0.1159005421324707**；R `glm(family=inverse.gaussian(link="log"))` 对齐 coef 3e-5、SE 3e-6；AIC 的 likelihood 常数不同，不比较。
- betadisper：输入距离 `[sample,sample_b]` + 元数据 `[sample,group]`；PCoA 双中心、保留正特征值、组质心、ANOVA；输出每样本距离与组编码；fixture 12 样本两组，group means **0.5432907785733675 / 1.5080518970308538**，F **12.27190000879564**，p **0.0056966678673121976**，特征值 **70.0768332020954 / 5.309000131237974**；与 R `vegan::betadisper(type="centroid")` 对齐 1e-12。
- ZINB：一个 `[sample,feature]` 表，count/zero 预测变量均必填；statsmodels `params` 顺序是 **zero, count, alpha**，实现按此切片后再按 count→zero 输出；输出 `[term,statistic]` 的 coef/se/z/P/CI；fixture seed 20261111 n=220、125 zeros：count coef **0.504542522196694 / 0.35446674816788964 / -0.24305519652093036**，zero coef **-0.5862120388429567 / 0.537950517169738**，alpha **0.7224400229926667**，theta **1.38419795162726**，loglik **-312.2941749228622**；与 R `pscl::zeroinfl(dist="negbin")` 对齐。
- `tests/test_extension74.py` 6 项、`tests/test_r_oracles64.py` 3 项，合计 **9 passed**；R 对照 `stats::glm`、`vegan::betadisper`、`pscl::zeroinfl`。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 375/85/21；参考页 375 算子 / 85 Reader；增量门 25 passed；`-W error` 11 passed；Studio 前端 321 passed。


## 82. 0.82.0 扩展证据

- 新增 2 个排序算子：`pcoa`（经典主坐标分析）与 `cca`（典范对应分析）。
- `pcoa`：一个 `[sample,sample_b]` 距离矩阵；校验方阵、对称、零对角、非负；`G=-.5D²` 双中心、`eigh`、仅保留正特征值，坐标 `V*sqrt(lambda)`；输出 `[sample,component]`，`n_components` 不超过正特征值数；info 含正/负/零特征值数量、explained、cumulative。fixture 7×7：正特征值 **5.542135906022611 / 5.317599140996917 / 3.0999555198047037 / 1.348490145693564**；R `cmdscale(D,k=4,eig=TRUE)` 特征值与前 3 维坐标（绝对符号）一致。
- `cca`：响应 `[sample,feature]` 计数表 + 解释变量 `[sample,predictor]`；按样本标签对齐；行/列权重 `r,c`，`Q=(Y/total-r c^T)/sqrt(r c^T)`；总惯量 `sum(Q²)`；加权设计 `Xw=sqrt(r)*center_weighted(X)`，对 **未加权 Q** 做 `lstsq(Xw,Q)` 后 SVD `Xw@B=U S Vt`；约束惯量 `sum(S²)`，特征值 `S²`；输出 `[component,statistic]` 的 `eigenvalue,explained,cumulative`，导出 site/species scores、权重与未约束惯量。
- CCA fixture 8×3、2 个解释变量：总惯量 **0.15765814626171162**，约束 **0.0760530413394101**，未约束 **0.08160510492230152**，特征值 **0.07592386857218954 / 0.00012917276722056823**；R `vegan::cca(Y~x1+x2)` 逐值一致（约束/未约束惯量容差 1e-10）。R `$CCA$u` 的缩放与实现导出的 LC site scores 不同，oracle 只比较特征值与惯量；实现导出的 site/species scores 为单位范数。
- `tests/test_extension75.py` 5 项、`tests/test_r_oracles65.py` 2 项，合计 **7 passed**；R 对照 `vegan::cmdscale`、`vegan::cca`。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 377/85/21；参考页 377 算子 / 85 Reader；增量门 22 passed（另 1 skipped）；`-W error` 11 passed；Studio 前端 323 passed。


## 83. 0.83.0 扩展证据

- 新增 2 个算子：`dbrda`（距离基冗余分析）与 `leave_one_out`（留一研究 Meta 分析）。
- `dbrda`：响应 `[sample,feature]` 计数/丰度表 + 解释变量 `[sample,predictor]`；Bray-Curtis 或欧氏距离；`G=-.5D²` 双中心；总惯量 `sum(eigvalsh(G))`；解释变量中心化后 QR，`fitted=Q Q' G Q Q'`；约束特征值为 `fitted` 的正特征值，约束惯量 sum，未约束=总-约束。fixture 8×3、2 个解释变量：总惯量 **0.29766435057928425**，约束 **0.14785322587790678**，未约束 **0.14981112470137747**，特征值 **0.14271793573379188 / 0.0051352901441149134**；R `vegan::dbrda(vegdist(Y,method="bray")~x1+x2)` 逐值对齐 1e-10。初版把零截距列纳入 QR，约束惯量偏大 0.15494；改为仅中心化解释变量后修正。
- `leave_one_out`：一个 `[study,feature]` 表，`effect_label`/`variance_label` 必填；对每个研究，删除后重拟合固定效应或 DL 随机效应截距模型；输出 `[study,statistic]` 的 `estimate,se,z,p,ci_low,ci_high,tau2,I2,Q,Qp,k`。fixture 8 研究：R `metafor::leave1out(rma(...))`；FE 第一项 estimate **0.23303691756346831**、se **0.13543160584780461**；DL 第一项 estimate **0.24783622694697988**、se **0.22256015182479655**、tau2 **0.20666323998000977**，逐值对齐 1e-10。
- `tests/test_extension76.py` 7 项、`tests/test_r_oracles66.py` 2 项，合计 **9 passed**；R 对照 `vegan::dbrda`、`metafor::leave1out`。
- 按用户要求未重跑全量；0.18 全量基线仍为 606 passed / 1 skipped。registry 379/85/21；参考页 379 算子 / 85 Reader；增量门 25 passed；`-W error` 11 passed；Studio 前端 325 passed。


## 84. 0.84.0 分类、预览与自动检查

- 分类：18 种原始写法收敛为 6 类；`build_catalog` 在 `describe_operator` 之后归一，避免被 `Step.category` 覆盖。
- 元数据：379 个算子 description 全非空（缺省用 title/输入数/输出类型生成）；85 个 Reader 均有 title/category/description/extensions/platforms。
- 平台：`BamReader`、`CramReader`、`BcfReader`、`BigWigReader` 标记 `platforms=["linux","darwin"]`；前端显示“Windows 不可用”。
- 前端：算子库 + Reader 库；搜索同时覆盖两者；Inspector 显示功能预览与源 Reader 信息。
- 自动检查：`tests/test_catalog_integrity.py` 对比 manifest 与源码发现；前端测试强制 6 类、非空描述、Reader 平台标记。
- 修复：Reader 发现去重（tenx 导入的 CsvReader 误计数）、`youden_index.py` BOM。
- 证据：registry **379/85/21/6**；定向 **20 passed**；前端 **39 passed / 9 files**；全量 **974 passed, 1 skipped**。

## 85. 0.85.0 Weibull AFT 与 Hardy-Weinberg

- 新增 `aft`：右删失 Weibull 加速失效时间回归；一个 `[sample,feature]` 表，`time_label`/`event_label`/`covariates` 必填，隐式截距；输出系数、SE、z/p、95% CI 与 `time_ratio`，info 含 shape/scale/loglik。
- 新增 `hardy_weinberg`：双等位精确 HWE 检验；输入 `[variant,feature]` 的 AA/AB/BB 计数；输出 n、alt_freq、obs_het、exp_het、fis、exact_p。
- AFT：R `survival::survreg(Surv(time,event)~x1+x2,dist="weibull")` 对照；seed 20261112、n=90、58 events：coef **1.24865535626414 / 0.918466782844872 / -0.434929192384358**，scale **0.913473103084374**，loglik **-120.493434256986**。
- HWE：R `HardyWeinberg::HWExact(..., pvaluetype="selome")` 对照；fixture (30,20,10)/(40,5,35)/(35,30,35)/(10,10,80)/(0,20,0)/(50,0,50) 的 p 分别为 **0.07767465115912098 / 4.713334922023663e-17 / 5.882470534401839e-05 / 2.538559375620213e-07 / 8.94713860811457e-06 / 1.1142241805814507e-30**。极端 p 不能加绝对 epsilon，否则会误把大量表计入尾概率。
- 证据：`tests/test_extension77.py` 4 项 + `tests/test_r_oracles67.py` 2 项 = **6 passed**；增量门 **100 passed**；`-W error` **8 passed**；frontend **39 passed / 9 files**；registry **381/85/21/6**；参考页 381/85。

## 86. 0.86.0 Chao1 与 rarefaction

- 新增 `chao1`：一个 `[sample,feature]` 计数表，非负整数、逐样本计算；输出 `chao1,observed,singletons,doubletons,n`。`f2>0` 时 `chao1=observed+f1²/(2f2)`，`f2=0` 时 `observed+f1(f1-1)/2`；空样本为 0。
- 新增 `rarefaction`：一个 `[sample,feature]` 计数表，`depth` 必填且不得超过样本总量；输出 `[sample,feature]` 的 `rarefied`。公式 `sum(1-C(N-n_i,depth)/C(N,depth))`；`N-n_i<depth` 时该物种必然保留，补 1。
- R 对照：`vegan::estimateR` 与 `vegan::rarefy`。Chao1 fixture `[[10,20,30,0],[5,0,15,30],[0,0,0,0],[1,1,1,1]]` 得 `[3,3,0,10]`；rarefaction 深度 10 得 `[2.852110517597176, 2.671547890140520, 3.0]`。
- 修复：rarefaction 初版在 `depth==N` 时跳过全部物种，补“必然保留”分支；Chao1/rarefaction 均拒绝负数和浮点计数。
- 证据：`tests/test_extension78.py` 4 项 + `tests/test_r_oracles68.py` 2 项 = **6 passed**；增量门 **22 passed**；`-W error` **8 passed**；frontend **39 passed / 9 files**；registry **383/85/21/6**；参考页 383/85。

## 87. 0.87.0 ARIMA 与保序回归

- 新增 `arima`：非季节 ARIMA(p,d,q) 最大似然拟合；一个 `[sample,feature]` 表，`value_label` 必填；`p/q` 0–4、`d` 0–2、`trend` c/n；输出 `[term,statistic]` 的 `coef/se/z/P/CI_low/CI_high`，info 含 sigma2、loglik、AIC/BIC、order、n。拒绝 `p+q=0`、`d>0` 且带常数趋势、样本不足与零方差序列。
- 新增 `isotonic`：单调最小二乘回归；一个 `[sample,feature]` 表，`x_label`/`y_label` 必填；`increasing` 控制方向，`out_of_bounds` 为 clip/nan/raise；按 x 排序后输出 `x/y/fitted/residual`。拒绝重复 x、少于 3 个有限点、x 零范围。
- ARIMA：R `stats::arima(order=c(1,0,0), method="ML", include.mean=TRUE)` 对照；seed 20261113、n=100 的 AR(1) 序列，statsmodels `coef const/ar.L1 = 1.316433508/0.639953805`、`sigma2=0.613084023`、`loglik=-117.695618`、`AIC=241.391236`；R `coef intercept/ar1 = 1.316459716/0.639954023`、`sigma2=0.6130963`、`loglik=-117.6956`、`AIC=241.3912`。
- ARIMA 标准误：statsmodels 默认 `cov_type="opg"` 的 const SE 为 **0.225358686**，R Hessian 为 **0.213974945**；改用 `cov_type="approx"` 得 **0.213972**，因此本实现显式使用 `approx`，R oracle 对 coef/se 容差 1e-4、sigma2 2e-5、loglik/AIC 1e-3。
- isotonic：R `isoreg` 对照；x 1..8、y `[1,2.2,1.8,2.7,3.1,2.9,4.2,4]` 的递增拟合为 `[1,2,2,2.7,3,3,4.1,4.1]`；递减拟合全部 **2.7375**；逐值容差 1e-12。
- 证据：`tests/test_extension79.py` 5 项 + `tests/test_r_oracles69.py` 2 项 = **7 passed**；增量门 **28 passed**；`-W error` **9 passed**；frontend **39 passed / 9 files** 且构建通过；registry **385/85/21/6**；参考页 385/85。

## 88. 0.88.0 决策曲线分析与 LOWESS

- 新增 `dca`：一个 `[sample,feature]` 表，`outcome_label` 与 `probability_label` 必填；阈值可用 `thresholds` 数组或 `threshold_start/.stop/.step` 生成（0–1、最多 1000 个）；输出 `[threshold,metric]` 的 `net_benefit,treat_all,treat_none,true_positive,false_positive,n`。净获益 `TP/n - FP/n*pt/(1-pt)`，全治疗 `prevalence-(1-prevalence)*pt/(1-pt)`；结局必须为 0/1，概率必须有限且在 [0,1]。
- 新增 `lowess`：一个 `[sample,feature]` 表，`x_label`/`y_label` 必填；`frac=2/3`、`iterations=3`（0–10）；按 x 排序后用 statsmodels lowess（`return_sorted=False`）计算，输出 `[sample,statistic]` 的 `x/y/fitted/residual`；拒绝少于 3 个有限点、常数 x。
- R 对照：`dcurves::dca` 在阈值 .1/.2/.5/.8 的净获益 **0.4583333/0.4375/0.5/0.25**、全治疗 **0.4444444/0.375/0/-1.5**；`stats::lowess(f=2/3, iter=3)` 对 x=1..20、y=sin(x/3)+0.1x 的前三个拟合 **0.92245094669743/0.99832873724478355/1.06239694318101585**、末两个 **1.78404484715937817/2.03812569619603856**，statsmodels 与 R 逐值约 1e-15。
- 重复检查：`chow_test` 已在 0.25 引入，本轮发现后恢复原文件，未重复新增；最终 0.88 只新增 `dca`/`lowess`。
- 许可证：根目录新增 Apache-2.0 `LICENSE`/`NOTICE`，README、`pyproject.toml`、`frontend/package.json` 与 lockfile 同步；移除旧专有许可/商业授权表述。
- 证据：`tests/test_extension80.py` 5 项 + `tests/test_r_oracles70.py` 2 项 = **7 passed**；增量门 **25 passed**；`-W error` **9 passed**；frontend **39 passed / 9 files** 且构建通过；registry **387/85/21/6**；参考页 387/85。

## 89. 0.89.0 Bai-Perron 多结构突变回归

- 新增 `bai_perron`：一个 `[sample,feature]` 表，`response_label` 与 `predictors` 必填；`n_breaks` 1–5（默认 2）、`min_segment` 0.05–0.5（默认 0.15）；丢弃非有限行，`design_matrix` 隐式截距。
- 算法：对每个候选分段用 OLS 求残差平方和，动态规划在固定断点数下最小化总 RSS；最小段长 `max(k+1, ceil(n*min_segment))`。输出 `[segment,term]` 的分段系数矩阵（Intercept + predictors），info 含 1-based 断点、分段起止、RSS、BIC、n/k。
- R 对照：`strucchange::breakpoints(y ~ x1 + x2, h=0.15, breaks=2)`；确定性 n=120 fixture 得到断点 **40/80**、总 RSS **0.5989**、三段系数 **(1.001658477, 0.4907472, -0.2923898) / (3.001149770, 0.5043395, -0.2967135) / (0.001173379, 0.4974717, -0.3007148)**，与 R 逐值 1e-6。
- BIC：本实现输出 `n*log(RSS/n) + ((n_breaks+1)*k + n_breaks)*log(n)`；R `breakpoints` 的 BIC 表采用不同尺度，只声明本实现公式，不做逐值对齐。
- 证据：`tests/test_extension81.py` 3 项 + `tests/test_r_oracles71.py` 1 项 = **4 passed**；增量门 **20 passed**；`-W error` **6 passed**；frontend **39 passed / 9 files** 且构建通过；registry **388/85/21/6**；参考页 388/85。
