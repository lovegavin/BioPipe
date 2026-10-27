## 审校补充（FASTA）

- 序列按最长序列补 NaN；编码 `A=0,C=1,G=2,T/U=3,N=4,其他=5`。
- `alphabet` 由观测字符推断为 dna/rna/protein；蛋白序列不要当核酸做 GC。
- 空记录会保留为全 NaN 行；header 只取 `>` 后第一个 token 作为序列标签。
- 同一文件不能混用不同 alphabet 假设；需要分开读取或在 ANALYSIS 说明。
