# 权威实现对照矩阵

本页记录扩展算子与外部权威实现的对标方式。原则：优先使用同语义的成熟实现；数值差异必须能由算法差异、参数或浮点精度解释；不能对标的项要明确写出原因。

## 0.20.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `cohens_kappa` | Python `statsmodels.stats.inter_rater.cohens_kappa` | `tests/test_extension13.py` | 无权重/线性/二次权重；统计量与 p 值同源 |
| `fleiss_kappa` | Python `statsmodels.stats.inter_rater.fleiss_kappa` | `tests/test_extension13.py` | `fleiss`/`randolph` 两种方法 |
| `breusch_pagan` | Python `statsmodels.stats.diagnostic.het_breuschpagan` | `tests/test_extension13.py` | 对 float32 输入允许 `rel=1e-5` 的浮点误差 |
| `durbin_watson` | Python `statsmodels.stats.stattools.durbin_watson` | `tests/test_extension13.py` | 残差顺序按输入行顺序 |
| `egger_test` | R `lm(effect/se ~ 1/se)` | `tests/test_r_oracles5.py` | 未加权 OLS；截距、斜率、t、p 对齐 |
| `anosim` | R `vegan::anosim` | `tests/test_r_oracles5.py` | 秩和置换；`R` 与 R 一致 |
| `procrustes` | R `vegan::procrustes(scale=TRUE, symmetric=FALSE)` | `tests/test_r_oracles5.py` | 对齐 `ss`、`scale` 和由 `ss` 推出的 `r`；不做反射 |
| `partial_mantel` | R `vegan::mantel.partial` | `tests/test_r_oracles5.py` | 对距离下三角残差化；`r=0.923474` 对齐 |

关键数值（测试 fixture）：

- Egger：截距 `1.883214`，斜率 `0.0166146`，截距 p `0.487185`。
- ANOSIM：`R=1`。
- Procrustes：`ss=7.105427e-15`，`scale=1`，由 R `ss` 推出 `r≈1`。
- Partial Mantel：`r=0.923474`。

## 0.21.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `storey_qvalue` | R `p.adjust(BH)` + 固定 lambda pi0 公式 | `tests/test_r_oracles6.py` | qvalue 包当前版本不接受 `pi0.method="fixed"`，用等价固定 pi0/BH 公式；pi0 与 q 值对齐 |
| `delong_auc` | R `pROC::roc` + `ci.auc(method="delong")` | `tests/test_r_oracles6.py` | AUC、DeLong CI 对齐 |
| `dunn_test` | R `dunn.test::dunn.test` | `tests/test_r_oracles6.py` | 原始 z/P 对齐；算子用标准 Holm，R 的 P.adjust 非单调，差异已记录 |
| `decision_curve` | R `dcurves::dca` | `tests/test_r_oracles6.py` | 阈值 0.2/0.4/0.6 的 net benefit 对齐 |
| `ordinal_logistic` | R `MASS::polr` | `tests/test_r_oracles6.py` | 去掉 intercept 后系数、阈值、logLik 对齐 |
| `linear_mixed_model` | R `lme4::lmer` + `VarCorr` | `tests/test_r_oracles6.py` | 固定效应、组间/残差方差对齐 |
| `hosmer_lemeshow` | R `ResourceSelection::hoslem.test` | `tests/test_r_oracles6.py` | 唯一分位数切点；统计量/df/p 对齐 |
| `stuart_maxwell` | R `DescTools::StuartMaxwellTest` | `tests/test_r_oracles6.py` | 2 个 rater、4 类；统计量/df/p 对齐 |

- 本轮新增 R 包：`pROC`、`dunn.test`、`dcurves`、`ResourceSelection`、`DescTools`；已有 `MASS`、`lme4`。
- 尝试的 Reader 依赖：`flowCore` 因 `cytolib` 编译失败；`sangerseqR` 未安装。因此 0.21 不新增 Reader，FCS/AB1 延后。
- Python 侧仍使用 `statsmodels 0.14.6`、`scipy 1.17.1`；未依赖未安装的 PyPI 包。
- 复现：`python -m pytest -q tests/test_extension14.py tests/test_r_oracles6.py`。

## 环境与缺口

- R 4.3.3；已装 `vegan`、`survival`、`metafor`、`edgeR`、`limma`、`DESeq2`、`fgsea`、`GSVA`、`sva`、`Kendall`、`ALDEx2` 等。
- 未装 `clusterProfiler`、`ANCOMBC`、`glmnet`、`preprocessCore`、`msigdbr`、`org.Hs.eg.db`、`biomaRt`、`rtracklayer`、`Rsamtools`、`ShortRead`、`phangorn`、`survminer`、`timeROC`、`pec`、`rms` 等。它们只影响对应领域；0.20 的 8 个算子不需要这些包。
- Python 侧使用 `statsmodels 0.14.6`、`scipy 1.17.1`；未安装 `pyteomics`/`pingouin` 等。质谱 Reader 用标准库 XML 解析，不依赖 `pyteomics`。
- 后续全量权威对标时，按算子领域选择 R/Python/命令行工具；不能直接对齐的项（如不同 NMDS 应力定义、不同 PH 假设检验实现）必须记录算法差异，不能强行调参拟合。

## 复现命令

```bash
# 纯 Python 与 R 对照（R 缺失时自动 skip）
python -m pytest -q tests/test_extension13.py tests/test_extension13_readers.py tests/test_r_oracles5.py
```

本矩阵只覆盖当前批次；历史批次见 `docs/sop_matrix.md` 的 §18/§19 与对应 R oracle 文件。
