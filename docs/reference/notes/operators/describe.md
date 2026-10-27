## 审校补充（数据概览）

- 不修改数据，只输出 shape、dims、info、有限值统计和缺失数量；适合作为中间检查点。
- 统计为有限值统计：NaN/Inf 不计入 min/max/mean/std，但 `n_missing` 会报告数量。
- 大矩阵走 `flat-reduction-v1` 流式路径，float64 矩可能与一次性 NumPy 有极小舍入差。
- 不替代 QC：不检查标签重复、编码一致性、批次或分布假设。
- 均值/标准差是全局的，不是按样本/基因分层；分层统计用 `qc_metrics` 或 `reduce_axis`。
