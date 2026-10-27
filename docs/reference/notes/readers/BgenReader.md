## 审校补充（BGEN）

- 只支持双等位、二倍体 BGEN；haplotype/haploid/complex 会明确报错。
- `data` 是 ALT 期望 dosage `P(AB)+2*P(BB)`，不是硬调用；全零概率行变 NaN。
- `info.chrom`/`info.pos` 来自 BGEN 元数据，并声明在 `axis_info[variant]`。
- 复杂/多等位 BGEN 先转 VCF，再用 VcfReader。
