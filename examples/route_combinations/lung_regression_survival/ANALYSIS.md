# NCCTG 肺癌：年龄回归 + 生存分析

## 数据

- 临床表：`input/lung_clinical.csv`，168 个完整病例 × 9 个字段。
- 特征表：`input/lung_ridge_features.csv`，168 个样本 × 6 个数值特征。
- 字段：`time`（生存时间，天）、`event`（1=死亡，0=删失）、`age`、`sex`（1=男，2=女）、`ph.ecog`、`ph.karno`、`pat.karno`、`meal.cal`、`wt.loss`。
- 来源：R 包 `survival` 的 `cancer` 数据集（North Central Cancer Treatment Group, NCCTG）。原始 228 行；本示例保留 168 个完整病例。男性 104、女性 64；事件 121。
- 引用：Loprinzi, C.L. et al. (1994). Prospective evaluation of prognostic variables from patient-completed questionnaires. *Journal of Clinical Oncology*, 12(3), 601–607. <https://doi.org/10.1200/JCO.1994.12.3.601>
- 数据页面：<https://cran.r-project.org/package=survival>

`lung_ridge_features.csv` 只保留 6 个生理/行为特征（`meal.cal`、`ph.karno`、`sex`、`pat.karno`、`wt.loss`、`ph.ecog`），刻意排除 `age`、`time`、`event`，避免把目标或生存结局泄漏进回归特征。

## 分析步骤

1. **ridge_regression**：用 6 个特征回归 `age`；75% 训练、25% 测试，3 折交叉验证，`random_state=11`，`alpha=1.0`。目的是给出一个“生理指标能否解释年龄”的弱预测基线，而不是做精确年龄预测。
2. **kaplan_meier**：按 `sex` 分层估计总生存曲线，给出中位生存期和风险人数。`sex` 在 CSV 中是数值 1/2，KM 按字符串分组，因此 YAML 用 `groups: ["1", "2"]`。
3. **logrank_test**：检验两条性别生存曲线是否相同；这里只做整体检验，不做两两比较。
4. **cox_regression**：`time + event ~ age + sex + ph.ecog`；`sex` 作为分类协变量。输出 HR、95% CI、Wald P 和 C-index。
5. **forest_plot**：把 Cox 的 HR 与 95% CI 画成森林图。
6. **describe**：汇总 Cox 结果表。

## 主要结果

- 年龄回归：训练 126、测试 42；测试 RMSE **8.50** 岁，测试 R² **-0.068**，3 折 CV R² **0.124 ± 0.125**。6 个生理指标对年龄的解释力很弱，测试集甚至略差于均值基线。
- KM：男性（sex=1）中位生存 **284 天**（n=104，事件 83）；女性（sex=2）中位生存 **426 天**（n=64，事件 38）。
- log-rank：χ² **6.155**，df **1**，P **0.0131**。
- Cox：n=168，事件 121，C-index **0.634**，log-likelihood **-502.89**。
  - `age`：HR **1.008**（95% CI 0.986–1.030），P **0.480**。
  - `sex_2.0`（女性相对男性）：HR **0.608**（95% CI 0.413–0.894），P **0.0114**。
  - `ph.ecog`：HR **1.568**（95% CI 1.202–2.047），P **0.000929**。
- 森林图中 age 与 ph.ecog 的效应方向相反：年龄略增风险但不确定；ECOG 体能状态每增加 1 级，死亡风险约增加 57%。

## 图

- `output/figures/km.png`：男性/女性总生存曲线，含删失标记和风险人数。
- `output/figures/forest.png`：Cox 模型的 HR 与 95% CI；竖线为 HR=1。
- `output/figures/` 中不含年龄回归的图；回归结果以 `output/steps/01_ridge_regression.json` 和终端摘要为准。

## 假设与限制

- 只保留 168/228 个完整病例，完整病例分析可能引入选择偏倚；不能代表全部 NCCTG 受试者。
- `sex` 的 1/2 编码来自原数据（1=男，2=女）；Cox 的 `sex_2.0` 是女性相对男性的 HR。
- Cox 模型未检验比例风险假设，也未加入交互项或非线性项；HR 是观测关联，不是因果效应。
- 年龄回归的测试 R² 为负，说明该组生理特征不适合预测年龄；不要把它解释为“年龄与生理指标无关”。
- 生存时间单位为天，中位生存期和 HR 仅适用于本数据的随访尺度。
- 本示例用于演示路线组合和结果可追溯性，不构成临床决策建议。
