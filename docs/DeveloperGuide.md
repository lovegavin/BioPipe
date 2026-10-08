# developer.md

# Developer Guide

This document explains how to extend BioPipe: adding a new input format, a new pipeline step, a new statistical model, or an entire pipeline.

It assumes you have read [architecture.md](architecture.md). The conventions below are mandatory; deviating from them breaks the plugin contract.

---

## 1. Conventions

Every source file follows the same rules.

### 1.1 File header

The first line of every `.py` file is its repository-relative path, as a comment:

```python
# src/io/readers/bgen.py
"""BGEN reader.

...docstring...
"""
```

This makes files self-locating when copied, pasted or diffed.

### 1.2 Language

All code, identifiers, comments, docstrings and error messages are in English.

### 1.3 Docstrings

NumPy-style docstrings. Every public function states purpose, parameters, returns, and any exception it raises.

```python
def read_bgen(path: str) -> dict:
    """Read a BGEN file into memory forms.

    Parameters
    ----------
    path : str
        Path to the ``.bgen`` file.

    Returns
    -------
    dict
        ``{"genotype": GenotypeMatrix,
           "variant_table": VariantTable,
           "sample_table": SampleTable}``

    Raises
    ------
    ReaderFormatError
        If the extension is unsupported.
    """
```

### 1.4 Import order

1. `from __future__ import annotations`
2. Standard library
3. Third-party (`numpy`, `pandas`, ...)
4. BioPipe internal (`src.core...`, `src.io...`)

One blank line between groups.

### 1.5 Error messages

Every error states what was expected and what was received.

```python
raise ReaderSchemaError(
    path=path,
    expected=["sample_id", "trait_value"],
    actual=list(df.columns),
    hint="Rename the first columns to match the contract.",
)
```

Never raise bare `Exception`. Use the hierarchy defined in `src/core/errors/`.

### 1.6 Version string

The version comes from `src/version.py`. Do not hard-code `"0.1.0"` anywhere else. Bumping the version is a one-line edit.

---

## 2. Adding a new reader

Use this when you want BioPipe to accept a file format it does not yet support (BGEN, PLINK 2.x, Parquet-encoded genotypes, etc.).

### 2.1 When a new reader is needed

A new reader is required when:

- The file format is not handled by any existing reader.
- The format cannot be converted to a supported format without loss.

A new reader is **not** needed when:

- The file is a variant of an existing format (e.g. a gzipped CSV is still a CSV).
- The data can be trivially converted upstream (BGEN → VCF).

### 2.2 Reader contract

Every reader:

1. Lives in `src/io/readers/`.
2. Has signature `read_<role>(path: str, **kwargs) -> dict[str, Form]`.
3. Returns a dictionary mapping form names to form objects.
4. Calls `validate()` on every form before returning.
5. Raises `ReaderFormatError` for format issues and `ReaderSchemaError` for schema issues.
6. Does not silently rename, coerce or drop columns.
7. Returns exactly the keys listed for its role in `architecture.md` §3.2.

### 2.3 Template

```python
# src/io/readers/bgen.py
"""BGEN reader."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.core.errors import ReaderFormatError
from src.core.forms import GenotypeMatrix, VariantTable, SampleTable


def read_bgen(path: str) -> dict:
    """Read a BGEN file into memory forms.

    Parameters
    ----------
    path : str
        Path to the ``.bgen`` file.

    Returns
    -------
    dict
        Genotype, variant and sample forms.
    """
    # 1. Open the file.
    # 2. Read sample IDs.
    # 3. Read variant metadata (CHROM, POS, REF, ALT, ID).
    # 4. Read dosages into an (n_snps, n_samples) float32 array.
    # 5. Encode missing calls with the missing_code sentinel.
    # 6. Record ploidy and allele_mode explicitly.
    # 7. Construct the three forms.
    # 8. Validate each form.
    # 9. Return the dict.

    data = ...              # np.ndarray, shape (n_snps, n_samples)
    variant_ids = ...       # np.ndarray of str
    sample_ids = ...        # np.ndarray of str

    genotype = GenotypeMatrix(
        data=data,
        variant_ids=variant_ids,
        sample_ids=sample_ids,
        ploidy=2,
        missing_code=-1.0,
        allele_mode="alt_dosage",
        genome_build="unknown",
        source_format="bgen",
    )

    variant_data = pd.DataFrame(
        {"CHROM": ..., "POS": ..., "REF": ..., "ALT": ...},
        index=pd.Index(variant_ids, name="ID"),
    )
    variant_table = VariantTable(
        data=variant_data,
        genome_build="unknown",
        source_format="bgen",
    )

    sample_data = pd.DataFrame(index=pd.Index(sample_ids, name="sample_id"))
    sample_table = SampleTable(data=sample_data, source_format="bgen")

    genotype.validate()
    variant_table.validate()
    sample_table.validate()

    print(
        f"[bgen] loaded {genotype.n_snps} variants x "
        f"{genotype.n_samples} samples"
    )

    return {
        "genotype": genotype,
        "variant_table": variant_table,
        "sample_table": sample_table,
    }
```

### 2.4 Registration

Add the extension to `src/io/detect.py`:

```python
GENOTYPE_EXT = {
    ".vcf": "vcf",
    ".bed": "plink",
    ".bgen": "bgen",       # new
}
```

Add the reader to `src/io/registry.py`:

```python
READER_MAP = {
    "genotype": {
        "vcf":   "src.io.readers.vcf:read_vcf",
        "plink": "src.io.readers.plink:read_plink",
        "bgen":  "src.io.readers.bgen:read_bgen",   # new
    },
    ...
}
```

No changes to forms or pipelines are required.

### 2.5 Validation against a golden dataset

A reader is not complete until it produces numerically correct output. Validate it against an official tool.

**Procedure:**

1. Pick a small dataset (a few hundred variants, a few dozen samples).
2. Convert it to VCF using the format's official tool (e.g. `bgenix`, `plink2 --export vcf`).
3. Run BioPipe twice: once with the new reader, once with the VCF reader.
4. Compare `gwas_result.tsv` column by column: `BETA`, `SE`, `P` must match to `1e-4`.

A reader that has not been validated against a reference tool is not accepted.

### 2.6 Common pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Missing-code sentinel mismatch | Dosages near 0 or 2, no `-1` values | Confirm the sentinel matches the reader's convention |
| A1/A2 reversed | Effect sizes have the wrong sign | Check allele orientation; document it in the reader docstring |
| Silently dropping samples | Sample count lower than expected | Check that no IDs are filtered during read |
| `validate()` skipped | Malformed form propagates downstream | Always call `validate()` before returning |

---

## 3. Adding a new step

Use this when you want a pipeline to perform an additional operation.

### 3.1 Step contract

A step:

1. Lives in `src/pipelines/<pipeline>/steps/`.
2. Inherits from `Step` (or `LoopStep` for iterative workflows).
3. Sets `name`, `consumes`, `produces`.
4. Implements `run(ctx)`.
5. Reads inputs from `ctx.forms` and writes outputs back to `ctx.forms`.
6. Does not import other steps.

### 3.2 `consumes` and `produces`

- `consumes`: forms that must already be present in the context.
- `produces`: forms that must be registered on exit.

**Rules:**

- Both are tuples of form names.
- `produces` lists mandatory outputs only. Optional forms (e.g. `covariates` when the input file is absent) are written to the context but not declared.
- If a step produces nothing, `produces = ()`.
- A step may modify a form in place (consume `genotype`, produce `genotype`); this is the standard pattern for filtering steps.

### 3.3 Template

```python
# src/pipelines/gwas/steps/example.py
"""ExampleStep — one-line description of what it does."""

from __future__ import annotations

from src.orchestration.context import PipelineContext
from src.orchestration.step import Step


class ExampleStep(Step):
    """One-sentence description for the docstring."""

    name = "example"
    consumes = ("genotype",)
    produces = ("genotype",)

    def run(self, ctx: PipelineContext) -> None:
        genotype = ctx.get("genotype")

        # Read parameters from the manifest.
        threshold = ctx.config.get("example", {}).get("threshold", 0.5)

        # Perform the operation.
        mask = ...  # boolean mask over variants or samples
        result = genotype.subset_snps(mask)

        # Register the produced form.
        ctx.put("genotype", result)

        # Optional: record a summary in metadata.
        ctx.metadata["example"] = {"n_before": genotype.n_snps,
                                   "n_after": result.n_snps}

        print(f"[example] {genotype.n_snps} -> {result.n_snps}")
```

### 3.4 Registration

Import the step in `src/pipelines/<pipeline>/steps/__init__.py`:

```python
from src.pipelines.gwas.steps.example import ExampleStep

__all__ = [..., "ExampleStep"]
```

Add it to the pipeline's step list in `src/pipelines/<pipeline>/pipeline.py`:

```python
steps = [
    LoadStep(),
    ...
    ExampleStep(),    # inserted at the correct position
    ...
]
```

### 3.5 Where outputs go

| Output type | Destination |
|---|---|
| Domain result (a form) | `ctx.put(name, form)` |
| Intermediate file (text, table) | `ctx.proc_dir / "..."` |
| Figure | `ctx.fig_dir / "..."` |
| Final result file | `ctx.out_dir / "..."` |
| Summary statistics | `ctx.metadata["<step_name>"]` |

Form outputs go through `ctx.put()`, which validates them automatically.

### 3.6 Common pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Declaring an optional form in `produces` | `PipelineError: declared form 'X' but did not register it` | Remove optional forms from `produces` |
| Not registering a declared form | Same as above | Call `ctx.put()` for every declared form |
| Importing another step | Circular dependencies, untestable code | Only share data through the context |
| Storing a form in `ctx.artifacts` | Downstream `ctx.get()` fails | Forms go in `ctx.forms`, artefacts in `ctx.artifacts` |

---

## 4. Adding a statistical model

Use this when the pipeline needs a new association or prediction method.

### 4.1 Model contract

A model:

1. Lives in `src/pipelines/<pipeline>/models/`.
2. Is a plain function (not a class), unless the model carries state.
3. Accepts `(y, X)` and returns `(beta, se, pvalue)` or `None` on failure.
4. Does not raise on numerical failure; returns `None` instead.
5. Does not print; the calling step handles logging.

### 4.2 Template

```python
# src/pipelines/gwas/models/example.py
"""Example regression model."""

from __future__ import annotations

import numpy as np


def fit_example(
    y: np.ndarray,
    X: np.ndarray,
) -> tuple[float, float, float] | None:
    """Fit the example model and return the dosage coefficient.

    Parameters
    ----------
    y : np.ndarray
        Response vector, shape ``(n,)``.
    X : np.ndarray
        Design matrix ``[intercept, dosage, covariates...]``.

    Returns
    -------
    (beta, se, pvalue) or None on failure.
    """
    try:
        beta = ...
        se = ...
        pval = ...
    except Exception:
        return None

    if not all(np.isfinite([beta, se, pval])):
        return None

    return float(beta), float(se), float(pval)
```

Register it in `src/pipelines/<pipeline>/models/__init__.py` and dispatch to it from the relevant step (usually `assoc.py`).

---

## 5. Adding a new pipeline

Use this when you want a complete new workflow (PRS, RNA-seq, methylation, ...).

### 5.1 Directory skeleton

```text
src/pipelines/<name>/
  __init__.py
  manifest.py       # default manifest + validation
  init.py           # scan input/, produce the input section
  pipeline.py       # <Name>Pipeline class
  steps/
    __init__.py
    step_1.py
    step_2.py
    ...
  models/
    __init__.py
    ...
```

### 5.2 Manifest

```python
# src/pipelines/<name>/manifest.py
"""<Name> manifest: default values and validation."""

from src.core.errors import ValidationError
from src.version import __version__


def default_manifest() -> dict:
    return {
        "pipeline": "<name>",
        "version": __version__,
        "input": {...},
        "runtime": {"seed": 42, "device": "cpu"},
        # pipeline-specific sections
    }


def validate_manifest(cfg: dict) -> None:
    if cfg.get("pipeline") != "<name>":
        raise ValidationError("Manifest", "pipeline name mismatch")
    # validate every section
```

### 5.3 Init

```python
# src/pipelines/<name>/init.py
"""Scan the task input directory and populate the input section."""

from pathlib import Path


def init_from_input_dir(task_dir) -> dict:
    input_dir = Path(task_dir) / "input"
    if not input_dir.exists():
        raise FileNotFoundError(f"Missing input directory: {input_dir}")
    # find files by convention
    return {...}
```

### 5.4 Pipeline class

```python
# src/pipelines/<name>/pipeline.py
"""<Name> pipeline."""

from __future__ import annotations

from pathlib import Path

from src.orchestration.bootstrap import bootstrap_context, load_manifest
from src.orchestration.runner import run_pipeline
from src.pipelines.<name>.manifest import validate_manifest
from src.pipelines.<name>.steps import Step1, Step2, ...
from src.version import __version__


class <Name>Pipeline:
    name = "<name>"
    version = __version__

    steps = [Step1(), Step2(), ...]

    def run(self, task_dir: Path) -> None:
        task_dir = Path(task_dir)
        config = load_manifest(task_dir)
        validate_manifest(config)
        ctx = bootstrap_context(task_dir, config, self.name)
        run_pipeline(self.steps, ctx)
```

Directory layout, logging and context construction are handled by `bootstrap_context`. Do not duplicate that logic in the pipeline class.

### 5.5 Registration

In `src/pipelines/__init__.py`:

```python
from src.pipelines.<name> import manifest as <name>_manifest
from src.pipelines.<name> import init as <name>_init
from src.pipelines.<name> import pipeline as <name>_pipeline
from src.pipelines.<name>.pipeline import <Name>Pipeline


class _<Name>Plugin:
    manifest = <name>_manifest
    init = <name>_init
    pipeline = <name>_pipeline
    pipeline_class = <Name>Pipeline


PIPELINES = {
    "gwas": _GwasPlugin(),
    "<name>": _<Name>Plugin(),
}
```

No changes to `scripts/` are required.

### 5.6 Task directory naming

The pipeline name is inferred from the final token of the task directory:

```text
tasks/task_010_myname_PRS      ->  pipeline = "prs"
tasks/task_011_myname_METHYL   ->  pipeline = "methyl"
```

Alternatively, pass `--pipeline` explicitly to `init_task.py`.

---

## 6. Testing

### 6.1 Three levels

| Level | Purpose | Location |
|---|---|---|
| Unit | Test one function in isolation | `tests/unit/` |
| Contract | Test that a plugin honours its declared interface | `tests/contract/` |
| Golden | Test end-to-end against a reference tool | `tests/golden/` |

### 6.2 Unit tests

Test a single function with hand-crafted inputs. No file IO, no pipeline.

```python
def test_compute_maf_all_heterozygous():
    data = np.ones((1, 10), dtype=np.float32)
    maf = compute_maf(data, ploidy=2)
    assert maf[0] == 0.5
```

### 6.3 Contract tests

Verify that a plugin satisfies the interface.

For a reader:

- Accepts a path and optional kwargs.
- Returns a dict of forms.
- Every returned form passes `validate()`.
- The returned dict keys match the role contract in `architecture.md` §3.2.

For a pipeline:

- `manifest.default_manifest()` and `manifest.validate_manifest()` are callable.
- `init.init_from_input_dir()` returns a dict.
- `pipeline.<Name>Pipeline` has `name`, `version`, `steps`, and `run`.
- The registry entry exposes a `pipeline_class` attribute.
- `pipeline_class.name` matches the registry key.

### 6.4 Golden tests

The most important level. A golden test compares BioPipe output against an established tool on the same input.

**Procedure:**

1. Store a small dataset under `tests/golden/<pipeline>/input/`.
2. Store the reference output under `tests/golden/<pipeline>/expected/`.
3. Run the pipeline.
4. Compare the produced `gwas_result.tsv` against the expected file, column by column, within a numerical tolerance (`1e-4`).

Golden tests catch the errors that unit tests miss: missing-code mismatch, allele orientation, off-by-one indexing, silent sample loss.

### 6.5 What to test first

Priority order:

1. Reader: byte-identical output on a small VCF against PLINK2 or GEMMA.
2. Alignment: sample IDs reordered correctly, drop count matches.
3. QC: MAF, missing rate and HWE match PLINK2.
4. Association: OLS coefficients match `statsmodels` on a synthetic dataset.
5. Firth: coefficients match the R `logistf` package within tolerance.

---

## 7. Style and review checklist

> **Note on testing status.** The repository currently ships no test infrastructure (`tests/` does not exist). The checklist below describes the target state. Items that depend on `tests/` will be enforced once the v0.2 hardening milestone lands.

Before submitting a change:

- [ ] File header contains the repository-relative path.
- [ ] All identifiers, comments and messages are in English.
- [ ] Public functions have NumPy-style docstrings.
- [ ] Errors use the `BioPipeError` hierarchy.
- [ ] No reverse-layer imports (`core` never imports from `io`, `pipelines` never import from `scripts`, etc.).
- [ ] Steps do not import other steps.
- [ ] Readers call `validate()` on every returned form.
- [ ] Forms are registered with `ctx.put()`, artefacts with `ctx.artifacts`.
- [ ] A reader is accompanied by a golden test.
- [ ] A new pipeline is registered in `src/pipelines/__init__.py` with a `pipeline_class` attribute.
- [ ] No hard-coded version strings outside `src/version.py`.
- [ ] Documentation has been updated if a public contract changed.

---

## 8. Reference

- Architecture and layering: [architecture.md](architecture.md)
- Input contract: [input_spec.md](input_spec.md)
- Planned features: [roadmap.md](roadmap.md)