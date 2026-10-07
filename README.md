# BioPipe

模块化生物信息学分析框架。当前包含 GWAS 流水线。

## 简介

BioPipe 把生信分析流程标准化为可复用的插件。所有输入格式在读入阶段收敛为统一的内存形式，下游分析无需感知原始格式。每条流水线是独立目录，包含配置、初始化、主流程和分析步骤，互不干扰。

## 特性

| 类别 | 内容 |
|---|---|
| 格式收敛 | VCF / PLINK / CSV / TSV / Excel 在读入阶段转成统一内存形式 |
| 模块化 | 每个功能一个文件，每个文件只做一件事 |
| 插件化 | 每条流水线是独立目录，新增不污染已有代码 |
| 最小分支 | 保留的分支仅是“做/不做”开关，无算法路由 |

## 安装

```bash
conda env create -f environment.yml
conda activate biopipe
```

依赖：Python 3.11、numpy、pandas、scipy、statsmodels、pysam、bed-reader、matplotlib、pyyaml。

## 快速开始 (GWAS)

```bash
cd ~/biopipe

# 1. 生成示例数据
python tasks/task_001_userA_GWAS/make_data.py

# 2. 生成配置
python scripts/init_task.py --task tasks/task_001_userA_GWAS/

# 3. 运行流水线
python scripts/run.py --task tasks/task_001_userA_GWAS/
```

用你自己的数据：

```bash
# 1. 放数据到 tasks/task_010_myrun_GWAS/input/
#    genotype.vcf.gz / phenotype.csv / covariates.csv

# 2. 扫描生成配置
python scripts/init_task.py --task tasks/task_010_myrun_GWAS/

# 3. （可选）编辑 config.yaml
vim tasks/task_010_myrun_GWAS/config.yaml

# 4. 运行
python scripts/run.py --task tasks/task_010_myrun_GWAS/
```

## 项目结构

```text
biopipe/
├── src/
│   ├── datapipe/                   # 通用 IO 层
│   │   ├── memory.py               #   统一内存形式（dataclass）
│   │   ├── detect.py               #   文件格式探测
│   │   ├── genotype.py             #   读基因型 → GenotypeMatrix
│   │   ├── table.py                #   读表格 → Table
│   │   └── align.py                #   样本对齐
│   └── pipelines/
│       ├── __init__.py             #   流水线注册表
│       └── gwas/                   #   GWAS 流水线插件
├── scripts/
│   ├── init_task.py                #   扫描 input/ → config.yaml
│   ├── run.py                      #   读 config.yaml → 执行流水线
│   └── gen_all_data.py             #   批量生成示例数据
├── tasks/                          #   任务目录
│   └── task_XXX_yyy_GWAS/
│       ├── make_data.py            #   数据生成脚本（仅演示）
│       ├── config.yaml
│       ├── input/
│       ├── processed/
│       └── output/
├── environment.yml
└── README.md
```

## 分层设计

框架分三层。

入口层 `scripts/`

命令行入口，只做分派。`init_task.py` 扫描数据目录、生成配置；`run.py` 读配置、找到对应流水线、调用主流程。此层不含业务逻辑。

插件层 `src/pipelines/`

每条流水线一个目录，自包含配置、初始化、主流程和分析步骤。目录之间互不影响。

通用 IO 层 `src/datapipe/`

提供格式读取和样本对齐能力。所有格式读取集中在这一层，新增格式在此添加 reader，而不是往流水线里塞。

该层不做业务解释——读出来的数据代表“表型”还是“协变量”、要不要做 QC，由流水线决定。

## 统一内存形式

所有格式读取后收敛为有限几种内存形式。每个形式是一个 dataclass，字段固定，操作封装在对象上。

### GenotypeMatrix

基因型数据的统一表示。

| 字段 | 类型 | 说明 |
|---|---|---|
| dosage | np.ndarray | (n_snps, n_samples) float32，缺失 = -1 |
| variant_info | pd.DataFrame | 列 [CHROM, POS, ID, REF, ALT] |
| sample_ids | list[str] | 顺序与 dosage 列一致 |
| ploidy | int | 倍性 |
| source_format | str | 原始格式标识 |

方法：`subset_samples(indices)`、`subset_snps(mask)`。

来源格式：VCF、PLINK。

### Table

通用二维表格。

| 字段 | 类型 | 说明 |
|---|---|---|
| data | pd.DataFrame | 第一列已设为索引 |
| source_format | str | 原始格式标识 |

方法：`subset_rows(sample_ids)`。

来源格式：CSV、TSV、Excel。

### 未来扩展

新内存形式按需添加，模式统一：dataclass + subset_samples / subset_rows + 对应 reader 文件。

| 形式 | 物理本质 | 典型来源 |
|---|---|---|
| ExpressionMatrix | 基因 × 样本表达量 | count 矩阵、10x |
| IntervalTable | 基因组区间 | BED、GTF、GFF |
| SequenceReads | 测序读段路径 | FASTQ、BAM |

## 插件契约

每条流水线插件提供三个接口文件：

| 文件 | 函数 | 职责 |
|---|---|---|
| config.py | default_config() -> dict | 返回默认配置 |
|  | validate_config(config) | 校验配置，不合法抛异常 |
| init.py | init_from_input_dir(task_dir) -> dict | 扫描 input/ 识别文件角色，返回 input section |
| pipeline.py | run(task_dir) | 主入口，读配置，执行流水线 |

注册方式：在 `src/pipelines/__init__.py` 的 `PIPELINES` 字典里添加：

```python
from src.pipelines import gwas, rnaseq

PIPELINES = {
    "gwas": gwas,
    "rnaseq": rnaseq,
}
```

## 配置约定

所有流水线共享顶层 `pipeline` 字段，用于 `run.py` 分派：

```yaml
pipeline: gwas      # 必填

# 以下为 gwas 自己的 section
input: ...
qc: ...
```

各流水线自定义自己的 section，互不干扰。

## 当前状态

已实现：GWAS。详见 `src/pipelines/gwas/README.md`。

计划方向：WES/WGS 变异分析、CNV、bulk RNA-seq、可变剪接、非编码 RNA、DNA 甲基化、ChIP-seq/ATAC-seq、单细胞、空间转录组、宏基因组、蛋白/代谢组、多组学整合、机器学习预后模型、孟德尔随机化、共定位、药物敏感性、免疫治疗响应、分子分型、单基因泛癌。

## 许可

版权所有 (c) 2026 Haojian Li。保留所有权利。

本软件为专有软件。未经版权所有者书面许可，任何人不得复制、修改、分发、再许可或用于商业用途。

如需商业授权、定制开发或合作，请联系：email: lovegavin118@outlook.com / WeChat: mylovegavin118 / No. 13727316173。