# R oracle setup and tests

BioPipe 的核心运行时只依赖 Python。R 仅用于测试 limma、fgsea、metafor 等外部实现，以及为将来可选的 R 后端提供环境。

## 1. 本机已验证环境

- R **4.3.3** (`/usr/bin/R`, `/usr/bin/Rscript`)，Bioconductor **3.18**。
- 包安装到用户库 `~/R/x86_64-pc-linux-gnu-library/4.3`，不需要 sudo。
- CRAN：`https://mirrors.ustc.edu.cn/CRAN/`。
- Bioconductor：Tsinghua/USTC/Aliyun 在 3.18 上返回 403/404，安装脚本回退到官方 `https://bioconductor.org`；这是镜像不可用时的 fallback，不是默认首选。

## 2. 安装

```bash
Rscript scripts/install_r_deps.R
```

脚本安装到用户库，并在 `Rscript` 里使用 `CXX_STD = CXX17` 重编译 `fgsea`：`fgsea` 1.28.0 的 Makevars 默认 C++11，而当前 `BH` 头文件要求 C++14/17。

| 包 | 必需性 | 用途 |
|---|---|---|
| `limma` | 必需 | `limma_de` 的普通线性模型对拍 |
| `fgsea` | 必需 | `gsea` 的 enrichment score 对拍 |
| `metafor` | 必需 | `meta_analysis` 的 fixed/random-effect 对拍 |
| `GSVA` | 必需 | `ssgsea` 的 rank-sum 对拍 |
| `sva` | 可选 | ComBat 的 R 参考；用于差异表达/批次校正研究 |
| `Kendall` | 可选 | `mann_kendall` 与 R `Kendall::MannKendall` 对拍 |
| `edgeR` | 可选 | RNA-seq 计数模型参考 |
| `DESeq2` | 可选 | RNA-seq 差异分析参考 |
| `clusterProfiler` | 可选 | ORA/富集分析参考 |
| `ANCOMBC` | 可选 | 微生物差异丰度参考 |
| `ALDEx2` | 可选 | 成分数据差异丰度参考 |
| `BiocManager` | 必需 | Bioconductor 安装器 |

可选包依赖系统库（libcurl、OpenSSL、fontconfig、GSL、HiGHS 等）；缺失时脚本会报告并继续，不会让四个必需 oracle 失败。当前 WSL 主机上 `limma` 3.58.1、`fgsea` 1.28.0、`metafor` 5.2.1、`GSVA` 1.50.5、`sva`、`Kendall`、`edgeR`、`DESeq2`、`ALDEx2` 已安装；`clusterProfiler`、`ANCOMBC` 仍受 `treeio`/`TreeSummarizedExperiment` 依赖链影响，`gsl` 的 CRAN 版本要求 R >= 4.5，R 4.3 下不可用。

## 3. 测试

```bash
python -m pytest -q tests/test_r_oracles.py tests/test_r_oracles2.py tests/test_r_oracles3.py
```

覆盖 13 个测试：

- `limma_de`：平衡两组、`prior_df=0` 时与 R `limma::lmFit` 的 logFC/t/p 逐值对拍。
- `ora`：与 R base `phyper` 的超几何尾概率逐值对拍。
- `gsea`：与 `fgsea::calcGseaStat` 的 weighted enrichment score 对拍（p 值仍由 Python 的 gene-set permutation 产生）。
- `meta_analysis`：与 `metafor::rma(method="FE"/"DL")` 的 beta/se/z/p/Q/I² 对拍；`I2` 输出为百分比（0–100）。
- `ssgsea`：与 `GSVA::gsva(ssgseaParam(...))` 的 rank-sum 分数对拍；Python 沿用 GSVA 的 global-range 归一化。
- `ancom_bc` / `aldex2`：与独立 R base log-ratio + Welch t 公式对拍；Monte Carlo 分支不逐随机数对拍。
- `wilcoxon`：与 R `wilcox.test(..., paired=TRUE, exact=TRUE)` 的 W/P 对拍。
- `friedman` / `bartlett` / `ks_2samp`：分别与 R `friedman.test`、`bartlett.test`、`ks.test(exact=TRUE)` 对拍。
- `mann_kendall`：与 R `Kendall::MannKendall` 的 S/tau/P 对拍。

R 或某个必需包不存在时，对应测试自动 skip，不会阻止纯 Python 环境运行全量测试。

## 4. 边界

- `limma_de` 的默认 empirical-Bayes 先验没有与 R `eBayes` 做逐值对拍；R oracle 覆盖的是 `prior_df=0` 的普通 t 分支。
- `ancom_bc` / `aldex2` 仍是独立近似实现，不是 R ANCOMBC/ALDEx2 的完整复刻；上面的 R 对拍验证的是 log-ratio + Welch 核心，不是完整包行为。
- `gsea` 只对拍 ES；fgsea 的 adaptive multilevel p 值与 Python 的 gene-set permutation p 值不是同一个零分布，不能直接逐值比较。
- Windows D 副本未安装 R；R oracle 只在 WSL/Linux 测试环境运行。
