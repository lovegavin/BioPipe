# RefSeq CDS sequence features: six cancer-related genes

## 数据与问题

本示例用 NCBI RefSeq 的 6 条人类编码序列（CDS），通过 BioPipe 的 `FastaReader` 读入，回答三个描述性问题：

1. 六条 CDS 的长度和 GC 含量分别是多少？
2. 按标准遗传密码翻译后，六种蛋白的理化性质（长度、分子量、等电点、GRAVY、芳香族比例）如何？
3. 把六条 CDS 合在一起看，密码子使用有什么总体特征？

数据来自 NCBI RefSeq，检索日期 2026-10-31：

| gene | CDS accession | protein accession | CDS length (nt) | protein length (aa) |
|---|---|---|---|---|
| TP53 | NM_000546.6 | NP_000537.3 | 1182 | 393 |
| BRCA1 | NM_007294.4 | NP_009225.1 | 5592 | 1863 |
| BRCA2 | NM_000059.4 | NP_000050.3 | 10257 | 3418 |
| EGFR | NM_005228.5 | NP_005219.2 | 3633 | 1210 |
| KRAS | NM_004985.5 | NP_004976.2 | 567 | 188 |
| PTEN | NM_000314.8 | NP_000305.3 | 1212 | 403 |

FASTA 的 header 已改写为基因名作为第一个 token，便于 `FastaReader` 生成 `sequence` 轴标签；原始 accession 与蛋白长度保存在 `input/refseq_cds_sources.tsv`。这不改变碱基序列。

RefSeq 参考：O'Leary, N.A. et al. (2016). Reference sequence (RefSeq) database at NCBI. *Nucleic Acids Research*, 44(D1), D733–D745. <https://doi.org/10.1093/nar/gkv1189>。序列通过 NCBI E-utilities `efetch`（`db=nuccore`, `rettype=fasta_cds_na`）取得。

## 路线

`task.yaml` 是 11 步的扁平 DAG：

1. `FastaReader` 读 `input/refseq_cds.fasta`，得到 `[sequence, position]`、DNA 编码的序列矩阵。
2. `sequence_stats` 计算每条序列的 length、GC、N 比例、valid_ratio；`drop` 去掉后两项，只保留 length/GC，`describe` 输出检查表。
3. `translate`（frame 0，`to_stop=true`）把 CDS 翻译成蛋白编码矩阵。
4. `protein_properties` 计算每条蛋白的 length、molecular_weight、isoelectric_point、gravy、aromaticity。
5. `heatmap` 以 `sequence` 为行、`statistic` 为列，按列 z-score 后展示六种蛋白的性质谱。
6. `correlation`（Pearson）计算 5 个蛋白性质之间的相关矩阵，`heatmap` 展示。
7. `codon_usage` 汇总六条 CDS 的 64 个密码子计数/频率，`describe` 输出总体检查。

## 结果

### CDS 长度与 GC

| gene | length (nt) | GC |
|---|---:|---:|
| TP53 | 1182 | 0.5685 |
| BRCA1 | 5592 | 0.4122 |
| BRCA2 | 10257 | 0.3573 |
| EGFR | 3633 | 0.5395 |
| KRAS | 567 | 0.3757 |
| PTEN | 1212 | 0.3845 |

六条 CDS 合计 22,443 nt，平均 GC 0.4396。长度差异很大（KRAS 567 nt 到 BRCA2 10,257 nt），因此后续蛋白性质的比较必须先按长度/分子量理解，不能把绝对差异直接当作“性质强弱”。

`valid_ratio` 被 `drop` 去掉：`FastaReader` 会把所有序列补齐到最长序列长度，`valid_ratio` 只反映补齐后的有效比例，不是生物学指标。`n_ratio` 也去掉，因为六条 CDS 都没有 N。

### 蛋白理化性质

| gene | length (aa) | molecular_weight | isoelectric_point | gravy | aromaticity |
|---|---:|---:|---:|---:|---:|
| TP53 | 393 | 50,732.785 | 6.326 | -0.7562 | 0.0611 |
| BRCA1 | 1863 | 241,281.61 | 5.114 | -0.7849 | 0.0483 |
| BRCA2 | 3418 | 445,803.0 | 6.255 | -0.6423 | 0.0688 |
| EGFR | 1210 | 156,074.94 | 6.219 | -0.3160 | 0.0702 |
| KRAS | 188 | 24,811.266 | 8.111 | -0.5745 | 0.0745 |
| PTEN | 403 | 54,426.066 | 5.901 | -0.6896 | 0.1241 |

六种蛋白的翻译长度与 RefSeq 对应的 NP 长度逐一吻合（393/1863/3418/1210/188/403），说明 FASTA 读取、密码子分帧和翻译在标准遗传密码下是一致的。蛋白长度合计 7,475 aa；六条 CDS 共 7,481 个密码子，其中 6 个是终止密码子，`to_stop=true` 把它们去掉，正好得到 7,475 aa。

BRCA2 是六者中最大的蛋白（3,418 aa，约 445.8 kDa），KRAS 最小（188 aa，约 24.8 kDa）。六种蛋白的 GRAVY 均为负值（-0.7849 到 -0.3160），整体偏亲水；EGFR 的 GRAVY 最接近 0，BRCA1 最亲水。等电点范围 5.114–8.111；KRAS 是唯一 pI 明显偏碱性的蛋白（8.111），其余在 5.1–6.3。PTEN 的芳香族比例最高（0.1241），BRCA1 最低（0.0483）。

![protein properties by gene](output/figures/protein_properties_by_gene.png)

热图按列 z-score，行是基因，列是五个性质。颜色只表示六条序列内部的相对高低，不表示绝对量级；长度和分子量两列高度一致，这是它们的数学关系，不是独立发现。

### 蛋白性质相关

|  | length | molecular_weight | isoelectric_point | gravy | aromaticity |
|---|---:|---:|---:|---:|---:|
| length | 1.0000 | 0.99997 | -0.3982 | -0.0326 | -0.3657 |
| molecular_weight | 0.99997 | 1.0000 | -0.3967 | -0.0349 | -0.3593 |
| isoelectric_point | -0.3982 | -0.3967 | 1.0000 | 0.3330 | 0.0899 |
| gravy | -0.0326 | -0.0349 | 0.3330 | 1.0000 | 0.0693 |
| aromaticity | -0.3657 | -0.3593 | 0.0899 | 0.0693 | 1.0000 |

![protein property correlation](output/figures/protein_property_correlation.png)

最显著的相关是 length 与 molecular_weight（r = 0.99997），这几乎是定义性的：蛋白越长，残基质量总和越大。除此之外，length/MW 与 pI、aromaticity 呈弱负相关（约 -0.36 到 -0.40），与 GRAVY 几乎不相关（约 -0.03）。pI 与 GRAVY 有弱正相关（0.333）。这些系数只基于 6 个蛋白，不能作为总体推断，也不能说明因果方向。

### 密码子使用

`codon_usage` 在六条 CDS 上共统计 7,481 个密码子（64 种）。计数最高的几个密码子：

| codon | count | frequency |
|---|---:|---:|
| GAA | 440 | 0.0588 |
| AAA | 373 | 0.0499 |
| AAT | 296 | 0.0396 |
| GAT | 241 | 0.0322 |
| AAG | 227 | 0.0303 |
| TCT | 206 | 0.0275 |
| GAG | 200 | 0.0267 |
| CAG | 195 | 0.0261 |

这些是六条 CDS 合并后的总体频率；`codon_usage` 当前只输出 `[codon, statistic]`，不保留基因维度，因此不能据此比较单个基因的密码子偏好，也不能推断翻译效率。要做基因间比较，需要先新增按序列分组的密码子统计算子，或在路线中逐条处理。

## 解释与限制

- 这是六条经典癌症相关基因的描述性序列特征分析，不是临床、诊断或功能实验结论。
- 六条 CDS 的 GC 含量差异（0.3573–0.5685）只描述编码序列本身；不能外推到基因组 GC、密码子适应度或表达水平。
- `protein_properties` 使用标准氨基酸残基质量、简单 pKa 模型和 GRAVY 表；没有考虑信号肽切除、跨膜区、翻译后修饰、二硫键或复合体状态。EGFR 的 RefSeq 蛋白是前体，热图中的分子量是前体序列的计算值。
- `translate` 使用标准遗传密码、frame 0、`to_stop=true`；线粒体遗传密码、可变剪接或非标准起始密码子不在本示例范围。
- 相关性基于 6 个蛋白，且 length 与 molecular_weight 并非独立变量；相关矩阵只用于检查实现一致性和描述性结构，不做显著性检验或因果解释。
- `codon_usage` 是合并统计，不能回答“哪个基因的密码子偏好更强”；这是当前算子输出粒度的限制。
- `describe` 的全局统计把不同性质的量纲混在一起（length 到 10,257，GC 到 0.57），只适合检查缺失和范围，不适合作为跨性质比较。

## 复现

```bash
python scripts/run.py examples/route_combinations/refseq_cds_sequence_features
python scripts/run.py examples/route_combinations/refseq_cds_sequence_features --check
```

输出写入 `output/`：两张图和逐步 JSON。`input/refseq_cds.fasta` 是任务实际读取的文件；`input/refseq_cds_sources.tsv` 只记录 accession、长度和蛋白描述，不参与计算。
