## 审校补充（BED）

- 坐标是 **0-based、半开区间**：`chromStart` 含，`chromEnd` 不含；不要按 GFF/GTF 的 1-based inclusive 解释。
- 无表头；`track`/`browser` 行跳过；列数 3–12，缺列时按 BED 规范补空/默认，不要假设第 4 列一定是 name。
- 非数值列（chrom/name/strand 等）编码进 `info["encoders"]`；数值坐标保持精确。
- 若同目录存在 `.bim`/`.fam`，`.bed` 会优先被 `Plink1Reader` 认领；普通 BED 请确保没有 PLINK 兄弟文件，或用 `args.reader: bed` 明确指定。
- 坐标大于 2^24 时仍按整数/无损路径处理，避免 float32 丢精度。
