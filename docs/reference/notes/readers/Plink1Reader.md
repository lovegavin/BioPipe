## 审校补充（PLINK 1.x）

- 只有 `.bed` + `.bim` + `.fam` 同时存在时才由 Plink1Reader 认领；否则 `.bed` 走 BedReader。
- 输出 variant × sample 的硬调用（0/1/2），缺失为 NaN；不是 dosage。
- 多等位位点按 ALT 拆分；variant 标签规则见页面。
- 三个文件不能压缩；Reader 需要 sibling 留在原目录。
- 做 MAF/HWE/LD 前先确认样本/变异缺失率和 ploidy。
