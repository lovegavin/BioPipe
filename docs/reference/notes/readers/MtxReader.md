## 审校补充（MTX）

- 需要同目录的 `matrix.mtx` + `barcodes.tsv` + `features.tsv`（旧版 `genes.tsv`）。
- 三个文件可各自 gzip；压缩按 magic bytes 检测，不只看扩展名。
- 矩阵是 gene × cell 的 UMI counts；MatrixMarket 坐标 1-based。
- 只指向 `.mtx`；缺少 sibling 会报错，不会静默读空。
- 重复 gene/cell 标签会加 `#position`；下游按标签对齐时注意。
