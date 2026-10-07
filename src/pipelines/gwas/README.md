# GWAS 模块

全基因组关联分析（Genome-Wide Association Study）流水线。输入 VCF 或 PLINK 基因型 + 表型表，一条命令完成质控、群体结构校正、关联分析、多重校正、可视化的完整流程。

## 一、功能范围

| 步骤 | 功能 | 状态 |
|---|---|---|
| 数据读取 | VCF（任意倍性）、PLINK（二倍体） | ✅ |
| 样本对齐 | 基因型 / 表型 / 协变量取交集 | ✅ |
| 样本 QC | 缺失率过滤 | ✅ |
| LD pruning | 滑窗 r² 剪枝（仅用于 PCA） | ✅ |
| PCA | 主成分计算 + 拼入协变量 | ✅ |
| SNP QC | 缺失率 + MAF + HWE | ✅ |
| 关联分析 | OLS（连续）/ Firth（二分类） | ✅ |
| 多重校正 | Bonferroni / FDR | ✅ |
| LD clumping | 显著 SNP 去冗余 | ✅ |
| 可视化 | 10 张论文级图 | ✅ |

## 二、输入

### 2.1 基因型

| 格式 | 扩展名 | 倍性 | 说明 |
|---|---|---|---|
| VCF | `.vcf` / `.vcf.gz` | 任意（2/4/6...） | 推荐。需 GT 字段，无需索引 |
| PLINK | `.bed + .bim + .fam` | 仅 2 | 三件套同名同目录 |

格式自动探测：扩展名优先，文件头兜底（VCF `##fileformat` / PLINK 魔数 `6c1b01`）。

倍性自动探测：

- VCF：从 GT 字段的等位基因个数推断（0/1 → 2，0/0/1/1 → 4）
- PLINK：固定 2

VCF 缺失编码：`./.`（二倍体）或 `./././.`（四倍体）

PLINK A1/A2 语义：

- `.bim` 第 5 列 A1 = 效应等位基因 → 映射到 ALT
- `.bim` 第 6 列 A2 = 其他等位基因 → 映射到 REF
- 遵循 PLINK `--recode vcf` 的官方约定

### 2.2 表型

CSV / TSV / Excel。第一列样本 ID，第二列表型值。

表型类型自动判断：

- 唯一值 == 2 → 二分类 → Firth 惩罚逻辑回归
- 唯一值 > 2 → 连续 → OLS

### 2.3 协变量（可选）

格式同表型。第一列样本 ID，其余列全作协变量。

无协变量时：

- 开启 PCA → PC1~PC10 自动作为协变量
- 关闭 PCA → 仅用截距 + 剂量回归

### 2.4 命名约定

```text
input/
├── genotype.vcf.gz        # 或 genotype.vcf / genotype.bed
├── phenotype.csv
└── covariates.csv         # 可选
```

名字不同时手改 `config.yaml` 即可，`run.py` 只读 config，不再扫描 `input/`。

## 三、处理流程

### 步骤 1：读取

模块：`datapipe/detect.py + datapipe/io.py`

- VCF：pysam 逐记录读 GT，`sum(GT)` 转剂量，缺失 = -1
- PLINK：bed_reader 读 `.bed`，转置成 `(n_snps, n_samples)`，NaN → -1

统一内存表示：

```text
dosage:       (n_snps, n_samples) float32, 缺失 = -1
variant_info: DataFrame [CHROM, POS, ID, REF, ALT]
sample_ids:   list[str]
ploidy:       int
```

### 步骤 2：样本对齐

模块：`datapipe/align.py`

以表型样本顺序为基准，取基因型 ∩ 表型 ∩ 协变量（若存在）的交集，三者按交集重排，保证样本一一对应。

无交集时报错退出。

### 步骤 3：样本级 QC

模块：`sample_qc.py`

| 参数 | 默认 | 说明 |
|---|---|---|
| `qc.sample_missing` | 0.10 | 样本缺失率 > 阈值则剔除 |
| `null` | — | 关闭样本 QC |

样本缺失率 = 该样本在所有 SNP 上的缺失比例。三份数据同步过滤。

### 步骤 4：LD Pruning（可选）

模块：`ld.py`

| 参数 | 默认 | 说明 |
|---|---|---|
| `ld.prune` | true | 是否启用 |
| `ld.r2` | 0.2 | 剪枝 r² 阈值 |
| `ld.window` | 100 | 滑窗大小（SNP 数） |

算法：滑窗内两两计算 r²，超过阈值的后一个 SNP 被剪掉。

关键：剪枝仅用于 PCA 输入，不影响回归的 SNP 集。这是行业标准做法（PLINK / REGENIE / SAIGE 一致），避免 PCA 被 LD 结构主导。

输出：`processed/ld_pruned_snps.txt`

### 步骤 5：PCA（可选）

模块：`pca.py`

| 参数 | 默认 | 说明 |
|---|---|---|
| `pca.enabled` | true | 是否启用 |
| `pca.n_components` | 10 | 保留的主成分数量 |
| `pca.as_covariates` | true | PCs 是否拼到协变量矩阵 |

算法：剪枝后矩阵 → 转置 → 均值填充 → 标准化 → SVD → 前 N 个左奇异向量 × 奇异值。

作用：校正群体分层，防止因祖先结构导致的假阳性。

无群体分层的数据：PCA 会过度校正，λGC 可能降到 1.0 以下。此时可关闭 PCA。

输出：

- `processed/pca_result.tsv`：样本 × PCs 矩阵
- `processed/pca_variance.tsv`：各 PC 解释方差比例

### 步骤 6：SNP 级 QC

模块：`qc.py`

| 参数 | 默认 | 说明 |
|---|---|---|
| `qc.missing` | 0.10 | SNP 缺失率 > 阈值则剔除 |
| `qc.maf` | 0.01 | MAF < 阈值则剔除 |
| `qc.hwe` | 1e-6 | HWE p < 阈值则剔除；null = 跳过 |

MAF 计算：

```python
alt_freq = nanmean(dosage_valid) / ploidy
maf = min(alt_freq, 1 - alt_freq)
```

HWE 规则：

| 场景 | 行为 |
|---|---|
| 二倍体 + 连续表型 | 全样本 Wigginton 精确检验 |
| 二倍体 + 二分类表型 | 只在对照组 Wigginton 精确检验 |
| 对照组样本 < 10 | 回退到全样本，警告 |
| 多倍体 | 跳过，记录 `skipped_reason: "polyploid"` |
| `hwe: null` | 跳过 |

为什么二分类只在对照组做：疾病本身会导致病例组偏离 HWE（真实关联），若在病例组做会把真实信号误删。

为什么多倍体跳过：多倍体 HWE 需要专门模型（考虑双还原），纯 Python 实现成本高。用户可用 R 包 `hwep` 单独处理。

输出：`processed/qc_report.json`

### 步骤 7：关联分析

模块：`association.py + firth.py`

逐 SNP 拟合回归，提取基因型系数的 β、SE、P。

| 表型类型 | 默认模型 | 可选 |
|---|---|---|
| 连续 | OLS（普通最小二乘） | — |
| 二分类 | Firth 惩罚逻辑回归 | 标准 Logit（`binary_model: "logit"`） |

设计矩阵：`[截距, 剂量, 协变量...]`。`params[1]` 是剂量系数。

缺失处理：每个 SNP 独立剔除缺失样本，不插补。

为什么二分类默认用 Firth：

- 病例对照不平衡时标准 Logit 有偏，Firth 无偏
- 完美分离（Perfect Separation）时 Firth 仍能收敛
- 小样本时更稳

代价：比 Logit 慢 5~10 倍

### 步骤 8：多重校正

模块：`correction.py`

| 参数 | 默认 | 说明 |
|---|---|---|
| `correction.method` | bonferroni | bonferroni / fdr / null |
| `correction.fdr_threshold` | 0.05 | FDR 阈值 |

| 方法 | 阈值 | 输出列 |
|---|---|---|
| Bonferroni | 0.05 / n_tests | SIGNIFICANT |
| FDR | BH 方法 | Q_VALUE + SIGNIFICANT |
| null | — | SIGNIFICANT（全 false） |

λGC 计算：`median(chi²) / 0.4549364`。< 1.05 为可接受。

输出：

- `processed/correction_meta.json`：λGC、阈值、显著数
- `processed/significant_snps.tsv`：显著 SNP 子集

### 步骤 9：LD Clumping（可选）

模块：`clump.py`

| 参数 | 默认 | 说明 |
|---|---|---|
| `ld.clump` | true | 是否启用 |
| `ld.clump_r2` | 0.5 | 去冗余 r² 阈值 |
| `ld.clump_window` | 500 | 窗口大小（kb） |

算法：显著 SNP 按 P 值升序，逐个作 index SNP，剔除与它 r² > 阈值且距离在窗口内的其他 SNP。

用途：一个真信号周围几十个 SNP 都会显著，clumping 挑出独立的代表信号。

输出：`processed/independent_significant_snps.tsv`

### 步骤 10：绘图

模块：`plot.py`

10 张论文级图，独立生成，一张失败不影响其他。

## 四、输出结果

```text
tasks/<task>/
├── output/
│   ├── gwas_result.tsv                          # 主结果
│   └── figures/
│       ├── manhattan.png
│       ├── qq.png
│       ├── volcano.png
│       ├── forest.png
│       ├── maf_distribution.png
│       ├── pvalue_histogram.png
│       ├── chromosome_density.png
│       ├── effect_vs_maf.png
│       ├── pca_scatter.png
│       └── pca_scree.png
└── processed/
    ├── dataset_profile.json                     # 数据特征快照
    ├── qc_report.json                           # QC 统计
    ├── ld_pruned_snps.txt                       # 剪枝 SNP 列表
    ├── pca_result.tsv                           # 样本 × PCs
    ├── pca_variance.tsv                         # 各 PC 解释方差
    ├── correction_meta.json                     # λGC + 阈值 + 显著数
    ├── significant_snps.tsv                     # 显著 SNP
    ├── independent_significant_snps.tsv         # 独立信号（clump 后）
    └── top_snps.tsv                             # Top 20
```

主结果 `gwas_result.tsv`

| 列 | 类型 | 说明 |
|---|---|---|
| CHROM | str | 染色体 |
| POS | int | 位置（1-based） |
| ID | str | SNP ID |
| REF | str | 参考等位基因 |
| ALT | str | 效应等位基因 |
| BETA | float | 效应量（ALT 拷贝数增加对表型的影响） |
| SE | float | 标准误 |
| P | float | P 值 |
| MAF | float | 次等位基因频率 |
| N | int | 该 SNP 有效样本数 |
| Q_VALUE | float | FDR Q 值（仅 FDR 方法时出现） |
| SIGNIFICANT | bool | 是否显著 |

关键中间文件

`dataset_profile.json`：数据特征快照。含输入路径、倍性来源、样本数、SNP 数、染色体、缺失率、MAF 分位数、表型统计、对齐统计。

`qc_report.json`：QC 统计。含样本 QC（前后数量、剔除数）、SNP QC（缺失/MAF/HWE 各剔除多少）、HWE 的作用范围和跳过原因。

`correction_meta.json`：多重校正元数据。含 λGC、阈值、检验数、显著 SNP 数。

## 五、图片说明

| 图 | 用途 | 坐标轴 | 关键判断 |
|---|---|---|---|
| `manhattan.png` | 全基因组信号概览 | X=染色体累计位置，Y=-log10(P) | 孤立尖峰 = 显著信号 |
| `qq.png` | P 值分布检验 | X=期望 -log10(P)，Y=观测 -log10(P) | λGC ≈ 1.0 理想；> 1.1 需 PCA 校正 |
| `volcano.png` | 效应量 vs 显著性 | X=β，Y=-log10(P) | 左上/右上 = 大效应 + 高显著 |
| `forest.png` | Top N SNP 的 β + 95% CI | X=β，Y=SNP ID | 横线穿过 0 = 不显著 |
| `maf_distribution.png` | 频率分布 | X=MAF，Y=SNP 数 | U 型正常 |
| `pvalue_histogram.png` | 整体 P 值分布 | X=P 值，Y=密度 | 无信号 = 水平线 y=1 |
| `chromosome_density.png` | 各染色体 SNP 数 | X=染色体，Y=SNP 数 | 应对应染色体长度 |
| `effect_vs_maf.png` | 效应 vs 频率 | X=MAF，Y=β | 随机散布正常 |
| `pca_scatter.png` | 样本 PC1/PC2 分布 | X=PC1，Y=PC2 | 云团 = 无分层；分簇 = 有分层 |
| `pca_scree.png` | 各 PC 解释方差 | X=PC 编号，Y=解释方差% | 肘部 = 应保留的 PC 数 |

绘图规范：

- 字体：Arial → Helvetica → DejaVu Sans
- DPI：300
- 配色：Okabe-Ito 色盲友好
- 去 top/right 边框
- 全英文标签

## 六、配置

`config.py` 的 `default_config()` 返回：

```python
{
    "pipeline": "gwas",
    "input": {
        "genotype": None,
        "phenotype": None,
        "covariates": None,
    },
    "qc": {
        "maf": 0.01,
        "missing": 0.10,
        "sample_missing": 0.10,
        "hwe": 1e-6,
    },
    "ld": {
        "prune": True,
        "r2": 0.2,
        "window": 100,
        "clump": True,
        "clump_r2": 0.5,
        "clump_window": 500,
    },
    "pca": {
        "enabled": True,
        "n_components": 10,
        "as_covariates": True,
    },
    "association": {
        "binary_model": "firth",
    },
    "correction": {
        "method": "bonferroni",
        "fdr_threshold": 0.05,
    },
    "plots": {
        "manhattan": True,
        "qq": True,
        "volcano": True,
        "forest": True,
        "maf_distribution": True,
        "pvalue_histogram": True,
        "chromosome_density": True,
        "effect_vs_maf": True,
        "pca_scatter": True,
        "pca_scree": True,
        "top_n_forest": 20,
    },
}
```

默认全开：LD pruning、PCA、LD clumping。若数据无群体分层或对速度敏感，可在 `config.yaml` 里单独关闭。

## 七、使用示例

### 示例 1：基础用法

```bash
cd ~/biopipe

# 1. 放数据到 tasks/task_010_myrun_GWAS/input/
#    genotype.vcf.gz
#    phenotype.csv

# 2. 生成配置
python scripts/init_task.py --task tasks/task_010_myrun_GWAS/

# 3. 跑
python scripts/run.py --task tasks/task_010_myrun_GWAS/
```

日志：

```text
基因型格式: vcf
读取 VCF: 5000 SNP × 150 样本, 倍性=2
对齐后: 150 样本
样本 QC: 150 → 150 样本
LD pruning: 5000 → 1761 SNP (r²>0.2, 窗口=100)
LD 保留 SNP (仅用于 PCA): .../ld_pruned_snps.txt
PCA: 10 PCs, PC1=5.32%, PC2=3.11%
SNP QC: 5000 → 4998 SNP
  HWE: 移除 2 SNP (scope=all_samples)
表型类型: continuous
完成: 4998 / 4998 SNP
校正 (bonferroni): λGC=1.010, 显著 SNP=18
Clumping: 18 显著 SNP → 3 独立信号 (r²>0.5, 窗口=500kb)
```

### 示例 2：关闭 PCA

修改 `config.yaml`：

```yaml
pca:
  enabled: false
```

日志变化：不再有 `PCA: 10 PCs`，PCA 相关图不生成。

### 示例 3：二分类表型

无需额外配置，`binary_model: firth` 是默认。

日志：

```text
表型类型: binary
  二分类模型: firth
  HWE: 移除 N SNP (scope=controls_only)
```

### 示例 4：PLINK 输入

```bash
# input/ 放 genotype.bed / .bim / .fam
python scripts/init_task.py --task tasks/task_011_plink_GWAS/
python scripts/run.py --task tasks/task_011_plink_GWAS/
```

日志：

```text
基因型格式: plink
读取 PLINK: 1000 SNP × 80 样本, 倍性=2 (PLINK 固定二倍体)
```

### 示例 5：四倍体 VCF

无需额外配置。

日志：

```text
读取 VCF: 2000 SNP × 120 样本, 倍性=4
SNP QC: ...
  HWE: 跳过 (polyploid)
```

### 示例 6：Python 调用

```python
from pathlib import Path
from src.pipelines.gwas.pipeline import run

run(Path("tasks/task_001_userA_GWAS"))
```

## 八、代码结构

```text
src/pipelines/gwas/
├── __init__.py
├── config.py            # 默认配置 + 校验
├── init.py              # 从 input/ 识别文件角色
├── pipeline.py          # 主流程编排 (run 是唯一入口)
├── sample_qc.py         # 样本级 QC
├── qc.py                # SNP 级 QC
├── association.py       # 逐 SNP 回归
├── firth.py             # Firth 惩罚逻辑回归
├── ld.py                # LD pruning
├── clump.py             # LD clumping
├── pca.py               # PCA
├── correction.py        # 多重校正 + λGC
├── plot.py              # 10 张论文级图
└── profile.py           # 数据特征快照

src/datapipe/
├── memory.py            # GenotypeMatrix / Table（dataclass）
├── detect.py            # 文件格式探测
├── genotype.py          # 读 VCF / PLINK → GenotypeMatrix
├── table.py             # 读 CSV / TSV / Excel → Table
└── align.py             # 样本对齐
```

## 九、常见问题

Q：Q_VALUE 全是 NaN？

A：`correction.method` 是 bonferroni。Bonferroni 不产生 Q 值。改成 fdr 才有。

Q：SIGNIFICANT 全是 False？

A：样本量小、效应弱，或 PCA 过度校正。检查 QQ 图 λGC，若明显偏离 1.0，调整 PCA。

Q：PCA 开启后 λGC < 1.0？

A：数据无群体分层，PCA 过度校正。无分层数据建议关闭 PCA。

Q：HWE 剔除 0 个 SNP？

A：数据质量高。真实数据通常剔除 1~5%。

Q：四倍体跳过 HWE？

A：当前流水线不做多倍体 HWE。需要时用 R 包 `hwep` 单独处理。

Q：PLINK 报错"仅支持二倍体"？

A：PLINK 格式本身只支持二倍体。四倍体请用 VCF。

Q：`init_task.py` 找不到我的文件？

A：命名约定是 `genotype.vcf.gz` / `phenotype.csv` / `covariates.csv`。名字不同时它会打印候选列表，手改 `config.yaml` 即可。

Q：LD pruning 后回归为什么还是用全部 SNP？

A：这是行业标准做法。LD pruning 只用于 PCA 输入，避免 PCA 被 LD 结构主导。回归必须在全部 QC 通过的 SNP 上做，避免遗漏信号。

Q：为什么 Firth 比 Logit 慢？

A：Firth 需要迭代求解修正得分方程，比标准 Logit 的 IRLS 慢。但二分类不平衡或小样本时结果更可靠。

## 十、依赖

| 包 | 用途 |
|---|---|
| numpy | 矩阵运算 |
| pandas | 表型/协变量/结果 |
| scipy | 统计检验、优化 |
| statsmodels | OLS / Logit |
| pysam | 读 VCF |
| bed-reader | 读 PLINK |
| matplotlib | 绘图 |
| pyyaml | 配置文件 |

## 十一、示例数据

仓库含 7 个演示任务，覆盖不同分支：

| 任务 | 倍性 | 表型 | 协变量 | 输入格式 | 覆盖特性 |
|---|---|---|---|---|---|
| task_001_userA_GWAS | 2 | 连续 | 有 | VCF.gz | 基线客户 |
| task_002_userB_GWAS | 2 | 连续 | 无 | VCF | 未压缩 VCF + 无协变量 |
| task_003_userC_GWAS | 2 | 二分类（1:1） | 有 | VCF.gz | 平衡病例对照 |
| task_004_userD_GWAS | 2 | 二分类（7:3） | 无 | VCF.gz | 不平衡病例对照 |
| task_005_userE_GWAS | 4 | 连续 | 有 | VCF.gz | 四倍体 |
| task_006_userF_GWAS | 4 | 二分类 | 无 | VCF | 四倍体 + 二分类 |
| task_007_userG_GWAS | 2 | 连续 | 无 | PLINK | PLINK 格式 |

一键生成全部数据：

```bash
python scripts/gen_all_data.py
```