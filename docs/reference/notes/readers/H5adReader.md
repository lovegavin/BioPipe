## 审校补充（H5AD）

- 读 `adata.X`；`layer` 指定时读 `adata.layers[layer]`。
- 稀疏矩阵会被 densify；超大 H5AD 先确认内存预算，或使用支持 disk 的路径。
- 标签来自 `obs.index`/`var.index`；重复标签会加 `#position`。
- 外部 `.gz/.bz2/.xz` 由 framework 解压；H5AD 内部压缩由 h5py 处理。
- 不要假设 `X` 已归一化/对数化；在 ANALYSIS 写明 layer 和预处理状态。
