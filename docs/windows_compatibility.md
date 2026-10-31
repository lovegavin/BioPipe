# Windows 兼容性

BioPipe 的核心 Python 代码在 Windows 和 WSL 都可运行；少数 Reader 依赖的
原生库没有 Windows wheel，**只影响这些格式**。需要完整格式覆盖时请在 WSL/Linux
运行；Windows 桌面版可以正常使用其余 Reader/算子。

## 依赖分层

| 能力 | Windows 原生 | WSL/Linux | 说明 |
|---|---|---|---|
| CSV/TSV/TXT/Excel/Parquet/HDF5/Zarr | 可用 | 可用 | pandas/openpyxl/h5py/zarr |
| BED/GFF3/GTF/FASTA/FASTQ/SAM/PAF/BEDPE | 可用 | 可用 | 纯 Python |
| VCF | 可用 | 可用 | 纯 Python 主路径；pysam VCF 可选 |
| BAM/CRAM | 不可用 | 可用 | 依赖 pysam；CRAM 还需 reference FASTA |
| BCF | 不可用 | 可用 | 依赖 pysam |
| BigWig | 不可用 | 可用 | 依赖 pyBigWig |
| PLINK1/2、BGEN | 可用 | 可用 | 现有依赖 |
| R oracle 测试 | 跳过 | 可用 | 需要 R 4.3+ 与 limma/fgsea/metafor/GSVA |

## 测试行为

- `pytest.importorskip("pysam")` / `pytest.importorskip("pyBigWig")` 让对应测试在
  Windows 上跳过，而不是失败。
- 最近一次全量（0.84）在 WSL/Linux 为 **974 passed, 1 skipped**；唯一 skip 是
  增量门在 full-suite 模式的分支，不是平台跳过。Windows 本地缺 pysam/pyBigWig 时，
  对应 Reader 测试按 `importorskip` 跳过，需要在 CI/本地验证说明中记录。
- D 盘测试副本不要求安装 pysam/pyBigWig；BAM/CRAM/BCF/BigWig 的 smoke test 在 WSL
  完成后同步代码即可。

## 安装建议

WSL/Ubuntu：

```bash
sudo apt-get install -y libcurl4-openssl-dev libssl-dev libbz2-dev liblzma-dev
python -m pip install pysam pyBigWig
```

原生 Windows：优先使用不依赖这些包的格式；需要时使用 WSL 运行 BioPipe，或从
conda-forge 安装带 Windows 构建的包（当前环境未提供）。
