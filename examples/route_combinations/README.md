# 路线组合示例

本目录保留 **五条强代表性、高端的可运行分析任务**。它们分别覆盖 FASTA、VCF、GCT、H5AD、BIOM 五类专用 Reader，并组合 BioPipe 已有的序列、群体遗传、表达、单细胞与微生物组算子；不新增注册项，registry 仍为 **402 个算子、85 个 Reader、21 条 route**。

早期用于验证 CSV/表格算子的多条示例已收敛删除，历史记录保留在 `docs/changelog.md` 与 `docs/sop_matrix.md`；当前只保留下面五条，避免示例膨胀和维护成本。

## 示例

| 目录 | 组合的路线 | 数据与目的 |
|---|---|---|
| `refseq_cds_sequence_features/` | FASTA 读取 + 序列统计 + 翻译/蛋白性质 + 密码子使用 | NCBI RefSeq 六个人类癌症相关基因 CDS；用 FastaReader 读入，检查长度/GC，翻译后比较蛋白理化性质，并汇总密码子使用 |
| `thousand_genomes_chr22_population/` | VCF 读取 + 群体质控 + PCA + FST + 亲缘关系 | 1000 Genomes Phase 3 chr22 的 200 kb 区间；用 VcfReader 读入 100 个样本，做 MAF/缺失/HWE 过滤、PCA、AFR-EUR Hudson FST 与 GRM 热图 |
| `leukemia_all_aml_expression/` | GCT 读取 + PCA + 差异分析 + FDR 热图 + 随机森林 | GSEA Leukemia 表达谱；用 GctReader 读取 48 个 ALL/AML 样本，做 Mann-Whitney + BH、显著基因热图与分类 |
| `pbmc3k_single_cell_atlas/` | H5AD 读取 + 单细胞 PCA/UMAP + 细胞类型聚合/热图 + 随机森林 | 10x Genomics PBMC3k 处理数据；用 H5adReader 读取 2,638 个细胞 × 1,838 个基因，按 8 个注释细胞类型做结构、marker 与分类分析 |
| `qiime_moving_pictures_microbiome/` | BIOM 读取 + alpha/beta 多样性 + PCoA + PERMANOVA + 聚类热图 | QIIME 2 moving-pictures 微生物组表；用 BiomReader 读取 34 个样本 × 770 个 taxa，过滤后比较 subject 间 Shannon、Bray-Curtis PCoA 与群落结构 |

五条示例都使用公开、可引用的数据集，而不是临时合成数据。数据已放在各自的 `input/` 下，便于离线复现；每条示例的逐步理由、结果和限制见该目录的 `ANALYSIS.md`。

## 运行

在项目根目录执行：

    python scripts/run.py examples/route_combinations/refseq_cds_sequence_features
    python scripts/run.py examples/route_combinations/thousand_genomes_chr22_population
    python scripts/run.py examples/route_combinations/leukemia_all_aml_expression
    python scripts/run.py examples/route_combinations/pbmc3k_single_cell_atlas
    python scripts/run.py examples/route_combinations/qiime_moving_pictures_microbiome

只做静态校验：

    python scripts/run.py examples/route_combinations/refseq_cds_sequence_features --check
    python scripts/run.py examples/route_combinations/thousand_genomes_chr22_population --check
    python scripts/run.py examples/route_combinations/leukemia_all_aml_expression --check
    python scripts/run.py examples/route_combinations/pbmc3k_single_cell_atlas --check
    python scripts/run.py examples/route_combinations/qiime_moving_pictures_microbiome --check

每个示例的输出写入各自 `output/`：`figures/` 为图片，`steps/` 为每步 JSON 摘要，`run_summary.txt/json` 为运行摘要。`input/` 中的文件来自公开数据集，字段经过最小化整理；示例用于演示组合方式，不构成临床或生物学结论。

## 数据来源与限制

### NCBI RefSeq CDS（6 个基因）

- 来源：NCBI RefSeq CDS，经 E-utilities `efetch(db=nuccore, rettype=fasta_cds_na)` 获取；访问号与基因见 `input/refseq_cds_sources.tsv`。
- 6 条 CDS：TP53 NM_000546.6、BRCA1 NM_007294.4、BRCA2 NM_000059.4、EGFR NM_005228.5、KRAS NM_004985.5、PTEN NM_000314.8；翻译后的蛋白长度分别为 393/1863/3418/1210/188/403，与对应 NP_ 记录一致。
- 仅使用标准遗传密码与 frame 0；不建模信号肽、跨膜区、PTM、蛋白复合物或临床意义。

### 1000 Genomes Phase 3 chr22（100 个样本，200 kb）

- 来源：1000 Genomes Phase 3 chr22 单倍型参考，GRCh37 `16,000,000–16,200,000`；原始 VCF 与 panel 说明见 <https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/>。
- 100 个样本按 super-population 各取 20 个（AFR/AMR/EAS/EUR/SAS）；`input/kg_chr22_region.vcf` 为区间子集，`input/kg_samples.csv` 提供样本与 super-population。
- 1,663 个 VCF 行经 MAF ≥0.05、缺失 ≤0.10、HWE P≥1e-6 后保留 97 个变异；单个 200 kb 区间不能代表全基因组，FST/GRM 只作区间内描述。

### GSEA Leukemia（48 个样本，10,056 个基因）

- 来源：GSEA 官方 Leukemia 示例数据，<https://www.gsea-msigdb.org/gsea/datasets.jsp>；GitHub 镜像只用于传输，不作为科学来源。
- 48 个样本：24 ALL、24 AML；表达值有符号，不是原始 counts；数据没有缺失表达单元格。176 个 `NA` 是基因名/描述子串，不是缺失值。
- 引用：Armstrong, S.A. et al. (2002). MLL translocations specify a distinct gene expression profile that distinguishes a unique leukemia. *Nature Genetics*, 30, 41–47. <https://doi.org/10.1038/ng809>。
- 48 个样本、无独立验证；ALL/AML 是强分离教学数据，不作临床结论。

### 10x Genomics PBMC3k（2,638 个细胞，1,838 个 HVG）

- 来源：10x Genomics PBMC3k 数据集的 Scanpy 处理版本 `scanpy.datasets.pbmc3k_processed()`；原始数据由 10x Genomics 生成，处理流程见 Scanpy 教程。
- `X` 为 log1p 归一化表达（范围约 −2.849 到 10.0），本示例**没有再次归一化**；h5ad 只保留表达矩阵、`obs` 注释和 `var` 的 `n_cells`，不携带上游 `uns`/`obsm`/`varm`/`layers`。
- `input/pbmc3k_cells.csv` 的 `sample` 与 h5ad 细胞 barcode 对齐；`cell_type` 是短标签，`cell_type_full` 保留完整注释名。
- 引用：Wolf, F.A., Angerer, P. & Theis, F.J. (2018). SCANPY: large-scale single-cell gene expression data analysis. *Genome Biology*, 19, 15. <https://doi.org/10.1186/s13059-017-1382-0>；原始数据：<https://www.10xgenomics.com/datasets/3-k-pbm-cs-from-a-healthy-donor-1-standard-1-1-0>。
- 细胞类型是上游 Louvain 注释，不是独立病理真值；不能据此推断供者、疾病或临床差异。

### QIIME 2 moving pictures（34 个样本，770 个 taxa）

- 来源：QIIME 2 官方 moving-pictures 教程的 `table.qza` 与 `taxonomy.qza`，<https://docs.qiime2.org/2024.10/data/tutorials/moving-pictures/>；BIOM 为 QIIME 2 2024.10 教程文件。
- 原始表为 34 个样本 × 770 个 taxa、2,327 个非零值；样本 ID 形如 `L1S105`。`input/feature-table.biom` 保留原矩阵，并把 taxonomy 的最深分类名 + 6 位 feature hash 写入 `observation/metadata`；`input/sample_metadata.csv` 的 `subject` 由 `L*` 前缀派生（L1–L6）。
- **限制**：教程的 sample metadata（含 body site）在本次运行中无法稳定下载；本示例没有 body-site 标签。`subject` 只是受试者前缀，不是 body site，也不是独立提供的临床分组。
- 过滤：taxa 需在至少 10 个样本中计数 ≥10（770 → 29）；alpha 多样性、Bray-Curtis 和热图都基于这个过滤 panel。
- 引用：Bolyen, E. et al. (2019). Reproducible, interactive, scalable and extensible microbiome data science using QIIME 2. *Nature Biotechnology*, 37, 852–857. <https://doi.org/10.1038/s41587-019-0209-9>；Caporaso, J.G. et al. (2011). Moving pictures of the human microbiome. *Genome Biology*, 12, R50. <https://doi.org/10.1186/gb-2011-12-5-r50>。
- 该示例用于验证 BiomReader 与微生物组算子的组合，不构成生态学或医学结论。

## 组合方式

任务 YAML 是扁平的算子 DAG。示例把 route 中的算子直接展开为多个分支，而不是在 YAML 里引用 route ID：

- `refseq_cds_sequence_features`：FastaReader 读入 6 条 RefSeq CDS；sequence_stats 检查长度/GC；translate + protein_properties 得到蛋白性质；heatmap 展示基因×性质谱；correlation + heatmap 检查性质相关；codon_usage 汇总密码子使用。
- `thousand_genomes_chr22_population`：VcfReader 读入 100 个样本的 chr22 区间；maf/missing/hwe 做变异质控；pca 压缩变异维，boxplot 按 super_pop 展示 PC1/PC2；fst 计算 AFR-EUR Hudson FST 并用 histogram 展示分布；relatedness 计算 GRM，rename_dim 后聚类热图展示个体间结构。
- `leukemia_all_aml_expression`：GctReader 读取 48 个样本 × 10,056 个基因；impute → pca → 两个 boxplot；compare_groups(Mann-Whitney) → select(P) → bh_adjust → filter_by(q<0.05) → heatmap（显著基因中 top-variance 40）；random_forest_classifier 在全部基因上训练，最后 describe。
- `pbmc3k_single_cell_atlas`：H5adReader 读取 2,638 × 1,838 的 log-normalized 矩阵；pca 后按细胞类型画 PC1/PC2 箱线图；umap 后画 UMAP1/UMAP2 箱线图；aggregate 按细胞类型求均值，rename_dim 后画 16 个 marker 的聚类热图；random_forest_classifier 在全部基因上预测注释细胞类型。
- `qiime_moving_pictures_microbiome`：BiomReader 读取 34 × 770 的 BIOM 表；filter_min 过滤低丰度 taxa；diversity 计算 Shannon/richness/evenness；distance_matrix(Bray-Curtis) → pcoa → 两个 boxplot；permanova 检验 subject；aggregate 按 subject 求均值，rename_dim 后 hvg + filter_by 选 20 个高变 taxa，最后聚类热图。

Studio 中可以把这些任务作为图导入，再拆分、合并或替换分支。逐步解释、指标和限制见各目录的 `ANALYSIS.md`。

## 测试

`tests/test_route_combinations.py` 对五条示例执行：

1. `--check` 静态校验；
2. 复制到临时目录后实际运行，检查 `output/run_summary.json` 的状态与步骤数。

测试不会写入仓库内的 `output/`，避免把运行产物或绝对路径带进可移植性审计。
