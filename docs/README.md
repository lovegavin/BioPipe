# BioPipe Documentation

BioPipe is a modular bioinformatics pipeline framework. It converts heterogeneous file formats into a small set of in-memory forms, then runs declarative pipelines over those forms. The current release ships a complete GWAS pipeline; additional pipelines and machine-learning workflows are planned.

## Who are you?

| If you want to... | Start here |
|---|---|
| Run a pipeline on your own data | guide.md |
| Prepare input files correctly | input_spec.md |
| Understand how the code is organised | architecture.md |
| Add a reader, step or pipeline | developer.md |
| See what is planned next | roadmap.md |

## Documentation index

| File | Audience | Contents |
|---|---|---|
| guide.md | Users | Install, prepare data, run a task, read outputs, fix common errors. |
| input_spec.md | Users | Accepted formats, required column names, compression rules. |
| architecture.md | Contributors, maintainers | Layering, dependency rules, memory forms, IO pipeline, orchestration, contracts. |
| developer.md | Contributors | How to add a reader, a step, or a whole pipeline. |
| roadmap.md | Everyone | Milestones and prioritised backlog. |

## Quick reference

Three commands to run a task:

```bash
python scripts/init_task.py     --task tasks/<task_dir>
python scripts/validate_task.py --task tasks/<task_dir>
python scripts/run.py           --task tasks/<task_dir>
```

Input files are named by convention. Put them in `input/`:

```text
input/
  genotype.vcf.gz     # or genotype.vcf, or genotype.bed (+ .bim, .fam)
  phenotype.csv       # columns: sample_id, trait_value
  covariates.csv      # optional; columns: sample_id, ...
```

Column names are fixed. Readers reject any file whose columns do not match the contract. See input_spec.md for the exact list.

## Design in one paragraph

Every input format is read into a small set of in-memory forms (GenotypeMatrix, Table, ResultTable, ...). Pipelines are lists of independent steps that consume and produce these forms through a shared context. Steps never call each other; the context is the only channel for data. Format detection, file parsing, sample alignment and quality control all live in dedicated layers below the pipelines, so adding a new format or a new pipeline does not require touching the others.

Full details: architecture.md.

## Status

| Component | State |
|---|---|
| Core forms | Stable |
| IO readers (VCF, PLINK, tabular) | Stable |
| Orchestration (Step / Context / Runner) | Stable |
| GWAS pipeline | End-to-end working |
| ML/DL extension points | Reserved, not implemented |

See roadmap.md for the full picture.

## License

Copyright (c) 2026 Haojian Li. All rights reserved.

This software is proprietary. No part of this software may be copied, modified, distributed, sublicensed, or used for commercial purposes without the prior written permission of the copyright holder.

For commercial licensing, custom development, or collaboration, please contact: email: lovegavin118@outlook.com / WeChat: mylovegavin118 / No. 13727316173.