## 审校补充（VCF）

- 默认硬调用基因型；多等位按 ALT 拆分，一行可能变多行。
- 缺失/半缺失（`0/.` 等）按 NaN；在 ANALYSIS 写明 ploidy/缺失比例。
- `reader='vcf'` 是路由选择器，不是 Reader 参数。
- 大 VCF 先子集/转 BGEN/PLINK；全量读取耗时和内存都高。
- POS 是 1-based；与 BED 做区间分析前先确认坐标基准。
