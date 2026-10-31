# PBC：竞争风险下的生存分析与 Fine-Gray 回归

## 数据来源

本示例使用 R 包 `survival` 的公开数据集 `pbc`（Primary Biliary Cirrhosis，原发性胆汁性胆管炎）。该数据来自 Mayo Clinic 的 PBC 临床随访研究，常用于生存分析和竞争风险方法的教学与验证。

- 数据：R package `survival`，`data(pbc)`，CRAN: <https://cran.r-project.org/package=survival>。
- 数据集说明：`?survival::pbc`；原始研究背景见 Therneau, T.M. & Grambsch, P.M. (2000), *Modeling Survival Data: Extending the Cox Model*, Springer。
- 本示例从 `pbc` 导出 418 行，重新编号为 `P001...P418`；只保留分析所需的字段，不做插补或删改随访时间。

## 数据概况

- 418 个样本；随访时间 `time` 单位为天。
- 终点 `status` 三分类：**232 例删失（0）、25 例肝移植（1）、161 例死亡（2）**。
- `death = 1` 当且仅当 `status = 2`；肝移植作为竞争事件处理。
- 性别：**女性 374、男性 44**；`sex_code` 为数值编码（女=0，男=1），供需要数值协变量的算子使用。
- 协变量：`age`（岁）、`bili`（胆红素）、`albumin`（白蛋白）、`edema`（水肿分级 0/0.5/1）。
- 上述字段在 418 行中没有缺失；其他 PBC 字段（如 `platelet`、`protime`）未纳入本示例。

## 分析路线

任务把“生存分析”路线和“竞争风险”路线展开为扁平 DAG：

1. `kaplan_meier`：按性别绘制死亡累积生存曲线，报告中位生存时间。
2. `logrank_test`：按性别比较死亡风险，`pairwise: false` 输出整体 log-rank 检验。
3. `cox_regression`：以 `age + sex_code + bili + albumin + edema` 拟合 cause-specific Cox 模型；肝移植在该模型中作为删失处理。
4. `forest_plot`：把 Cox 的 HR 与 95% CI 画成森林图。
5. `cumulative_incidence`：以死亡为感兴趣事件、肝移植为竞争事件，按性别估计 Aalen-Johansen 累积发生率，`horizon: 3650` 天（10 年）。
6. `fine_gray`：以同一组协变量拟合 Fine-Gray 子分布风险模型；肝移植作为竞争事件保留在风险集中。
7. 两个 `describe`：输出 CIF 与 Fine-Gray 结果的形状和摘要。

## 结果

### Kaplan-Meier 与 log-rank

- 女性：n=374，死亡事件 137，中位生存 **3445 天**。
- 男性：n=44，死亡事件 24，中位生存 **2386 天**。
- 整体 log-rank：χ² = **2.977**，df = 1，P = **0.0845**。

男女中位生存相差约 1059 天，但 log-rank 检验在 0.05 水平不显著；男性样本只有 44 例，估计的不确定性很大。

### Cause-specific Cox 模型

n=418，死亡事件 161，C-index = **0.8114**，loglik = **-784.626**，AIC = **1579.252**。

| 协变量 | HR | 95% CI | P |
|---|---:|---:|---:|
| age（每岁） | 1.0359 | 1.0194–1.0527 | 1.73e-5 |
| sex_code（男 vs 女） | 1.5349 | 0.9813–2.4009 | 0.0605 |
| bili（每单位） | 1.1285 | 1.1004–1.1572 | 4.39e-21 |
| albumin（每单位） | 0.3677 | 0.2464–0.5486 | 9.60e-7 |
| edema（每级） | 2.9501 | 1.6964–5.1301 | 1.27e-4 |

年龄、胆红素、白蛋白和水肿与死亡风险显著相关；男性相对女性的 HR 为 1.53，但 95% CI 跨 1，P=0.0605。

### 累积发生率（竞争风险）

Aalen-Johansen CIF 共 177 个时间点、2 个性别组；CIF 最大值 **0.5974**，均值 **0.2314**。

10 年（3650 天）时的 CIF：

| 事件 | 女性 | 男性 |
|---|---:|---:|
| 死亡 | 0.5194 | 0.5974 |
| 肝移植 | 0.0853 | 0.0797 |

如果把肝移植简单当作删失，会高估死亡累积发生率；CIF 将肝移植保留为竞争事件，因此数值更适合解释“在肝移植竞争下发生死亡”的绝对风险。

### Fine-Gray 子分布风险模型

n=418，死亡事件 161，竞争事件（肝移植）25，删失 232；loglik = **-795.553**，6 次迭代收敛。

| 协变量 | 子分布 HR | P |
|---|---:|---:|
| age | 1.0408 | 1.16e-6 |
| sex_code | 1.5159 | 0.0669 |
| bili | 1.1217 | 1.22e-12 |
| albumin | 0.4240 | 2.61e-5 |
| edema | 3.3129 | 1.16e-4 |

Fine-Gray 的系数方向与 Cox 模型一致；HR 的解释是子分布风险比，不是 cause-specific hazard ratio。算子导出的 `CI_low` / `CI_high` 是系数尺度区间，不应直接当作 HR 的置信区间使用。

## 图

- `output/figures/km_death_by_sex.png`：按性别分层的死亡 Kaplan-Meier 曲线，带 95% CI；对应中位数 3445 天（女）与 2386 天（男）。
- `output/figures/cox_forest.png`：Cause-specific Cox 模型的 HR 森林图；年龄、胆红素、白蛋白、水肿的 CI 不跨 1，男性指示变量的 CI 跨 1。

## 假设与限制

- 这是观察性临床随访数据，HR 和 CIF 差异不能解释为因果效应。
- PBC 数据来自较早期的单中心研究；治疗背景与当代临床实践不同，不能直接外推到今天的患者。
- 男性只有 44 例，性别效应和男性亚组 CIF 的精度有限。
- log-rank 检验只比较死亡风险，不处理肝移植竞争；竞争风险结论以 CIF 和 Fine-Gray 模型为主。
- Fine-Gray 模型使用稳健 sandwich 方差；未做模型诊断、比例子分布风险检验或校准评估。
- CIF 的 3650 天数值来自 `cmprsk::cuminc` 的独立核对；BioPipe 结果的最大值/均值与之一致。
- 本示例用于演示路线组合与竞争风险算子，不构成临床建议。

## 复现

在项目根目录执行：

    python scripts/run.py examples/route_combinations/pbc_competing_survival

只做静态校验：

    python scripts/run.py examples/route_combinations/pbc_competing_survival --check

输出写入 `examples/route_combinations/pbc_competing_survival/output/`；`output/` 已被 `.gitignore` 忽略。
