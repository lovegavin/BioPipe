# mtcars：油耗回归、变速箱分类与结构探索

## 数据来源

- 数据集：R datasets 包的 mtcars，1974 年《Motor Trend》杂志汽车道路测试数据，32 辆汽车、11 个变量。
- 引用：Henderson, H.V. & Velleman, P.F. (1981). Building multiple regression models interactively. Biometrics, 37(2), 391–411. 数据最初由 Motor Trend 收集。
- 本示例用 R 的 datasets::mtcars 导出，未改动数值；样本 ID 使用车型名（如 Mazda RX4），仅用于展示。

## 数据概况

- 32 辆汽车；无缺失值。
- 连续目标：mpg（每加仑英里数），范围 10.4–33.9，均值 20.09。
- 二分类目标：am，0=自动挡 19 辆，1=手动挡 13 辆；am_label 为 automatic/manual。
- 回归/分类特征（9 个）：cyl（气缸数）、disp（排量）、hp（马力）、drat（后轴比）、wt（重量，1000 lb）、qsec（1/4 英里加速时间）、vs（V/S 发动机）、gear（前进挡数）、carb（化油器数）。
- 结构探索表额外包含 mpg，用于 PCA 与相关热图；回归时 mpg 只作为目标，不作为特征，避免泄漏。

## 路线设计

本示例把 5 个分析分支组合成一个任务，共 13 步：

1. 变速箱分组比较：compare_groups 对 mpg、wt、hp 做自动挡 vs 手动挡的 Welch 检验，describe 输出统计量。
2. 油耗回归：ridge_regression 用 9 个特征预测 mpg，alpha=1.0，75%/25% 划分，3 折 CV；describe 输出训练/测试指标。
3. 变速箱分类：logistic_regression 用同一组 9 个特征预测 am（0/1），标准化后拟合，3 折 CV；describe 输出准确率、AUC、混淆矩阵与系数重要性。
4. 随机森林对照：random_forest_classifier 用 am_label 做二分类，500 棵树、同一划分、3 折 CV；describe 输出指标与特征重要性。
5. 无监督结构与相关：pca 对含 mpg 的 10 个变量取 2 个成分，join 合并 am_label，scatter 按变速箱着色；correlation 计算 Spearman 矩阵，heatmap 做层次聚类热图。

## 主要结果

### 变速箱分组差异

- mpg：自动挡均值 17.147，手动挡 24.392；Welch t=3.767，P=0.00137。
- wt：自动挡 3.769，手动挡 2.411；t=-5.494，P=6.27e-06。
- hp：自动挡 160.263，手动挡 126.846；t=-1.266，P=0.221。

手动挡车在这份样本中更轻、油耗更低；马力差异不显著。分组不是随机实验，不能据此作因果解释。

### 油耗回归

- 24 训练 / 8 测试；测试 RMSE 2.755、MAE 2.127、R² 0.8569。
- 3 折 CV R² 分别为 0.493、0.426、-0.373，均值 0.182，标准差 0.393。
- 系数绝对值最大的特征：wt（2.046）、hp（1.374）、gear（1.065）、cyl（0.931）。

测试集 R² 较高，但 CV 有一折为负，说明 32 个样本下模型对划分很敏感；不能把 0.857 当作稳定泛化性能。

### 变速箱分类

- 逻辑回归：测试 accuracy 1.0000、AUC 1.0000、macro F1 1.0000；3 折 CV 也是 1.0000；混淆矩阵 [[5,0],[0,3]]。
- 随机森林：测试 accuracy 1.0000、AUC 1.0000；3 折 CV 0.9167 ± 0.0589；混淆矩阵 [[5,0],[0,3]]。
- 随机森林重要性：wt 0.245、drat 0.192、gear 0.180、qsec 0.133。

完美分类更可能是小样本 + 特征与变速箱强关联造成的分离，而不是可推广的“换挡类型识别器”；测试集只有 8 辆，且两组在重量、油耗上本来就有系统差异。

### PCA 与相关结构

- PCA：PC1 62.94%、PC2 21.60%，前两轴合计 84.53%。
- Spearman 相关范围 -0.9108 到 0.9277，均值 -0.0671。
- 最强正相关：cyl–disp 0.928、cyl–hp 0.902、disp–wt 0.898。
- 最强负相关：mpg–cyl -0.911、mpg–disp -0.909、mpg–hp -0.895、mpg–wt -0.886。

PCA 与相关矩阵是探索性描述；变量之间高度共线，不能把单个相关系数解释为独立效应。

## 图片

- output/figures/pca_by_transmission.png：PC1–PC2 散点，按自动/手动挡着色。前两轴解释大部分变异，但分组重叠与分离要结合样本量看待。
- output/figures/mtcars_spearman_correlation.png：10 个变量的 Spearman 相关热图，行列层次聚类；用于观察共线块，不替代回归诊断。

## 限制

- 32 辆汽车、8 辆测试集，统计功效和泛化评估都有限；分类 1.0 不能外推。
- 数据来自 1974 年道路测试，车型、道路、驾驶条件与现代车辆不同。
- am、cyl 等分组不是随机分配；分组差异是描述性的，不作因果结论。
- 回归使用全部 9 个特征，未做变量选择；CV 波动说明需要外部验证或更稳健的建模。
- 相关热图包含 mpg，仅用于结构探索；回归分支已排除 mpg 特征。
- 本示例不新增算子/Reader/路线，registry 仍为 402/85/21/6。

## 复现

在项目根目录执行：

    python scripts/run.py examples/route_combinations/mtcars_regression_classification --check
    python scripts/run.py examples/route_combinations/mtcars_regression_classification

运行结果写入该目录的 output/；output/ 不应提交。数据文件在 input/，任务定义在 task.yaml。
