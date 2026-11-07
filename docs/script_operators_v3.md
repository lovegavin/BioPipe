# Script operators

A workflow-local script is a frozen source snapshot, a language, named file ports,
parameter schema and dependency declaration. Python, R, C and C++ files can be
inspected statically. No import, compilation or scientific computation occurs
during inspection.

```python
# input: data file.txt
# output: result file.txt
import argparse
from pathlib import Path

repeat = 2
parser = argparse.ArgumentParser()
parser.add_argument('--in-data', required=True)
parser.add_argument('--out-result', required=True)
args = parser.parse_args()
Path(args.out_result).write_text(Path(args.in_data).read_text() * repeat)
```

R uses `# input:` and `# output:`; C/C++ use `// input:` and `// output:`. Scripts
receive `--in-NAME path` and `--out-NAME path` arguments and must produce all
declared outputs. A zero exit code without a declared output is failure. The graph
adapter currently supports one output file per script node; the process helper
can validate multiple files, but the graph adapter rejects that interface until
multi-output projection is implemented. It never silently drops outputs.

```sh
operon script inspect ./copy.py
operon script parameters ./copy.py
operon script extract ./copy.py --names repeat --output ./copy.snapshot.json
```

Extraction returns source, schema, initial values and binding metadata together;
it does not overwrite the original script. Python extraction accepts selected
top-level scalar literals, rejects repeated or shadowed assignments, and rewrites
the selected AST assignment into a JSON lookup. Equal literal values elsewhere
are not replaced. The process sets `OPERON_PARAMETERS_FILE` to that run's frozen
values. Script source and schema are saved atomically by the document editing
service. R/C/C++ parameter wiring is explicit in this revision; automatic AST
binding for those languages is not advertised.

Python dependencies use PEP 723:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy==1.26.4"]
# ///
```

Readiness inspects the selected Python's installed package metadata and version.
Missing or incompatible dependencies block readiness. It does not import the
user's program or install anything. URL/extras requirements currently require a
separately prepared frozen environment. R requires Rscript; C/C++ require a
compatible compiler. Windows-specific compilation toolchains need a configured
adapter; a command called `cc` is not inferred from arbitrary installed IDEs.

Execution uses an owned subprocess tree, a fresh run directory, separate logs,
TMP/TEMP/TMPDIR and declared output validation. Cancellation or timeout terminates
the owned process tree. C/C++ currently compile in that attempt directory; reuse of
compiler-identity build caches remains a later optimization. This process boundary
does not sandbox malicious code or automatically make full-memory programs stream.

The graph adapter accepts single-file FileArtifact inputs with matching explicit
formats. Matrices require an explicit, registered file codec or scientific
conversion. This preserves memory/streaming contracts rather than eagerly dumping
arbitrary Forms. Existing managed host admission and spill remain in the shared
runner; the script's private heap is not directly spillable by Operon.

## Promote a script into the library

In the Studio inspector, choose the category and a distinct namespaced ID under
**Save to operator library**. This explicit action builds and registers a static
v3 wheel without importing the script or installing scientific dependencies.
Use the selected workflow's environment check before running it.

`export_script_package(snapshot, directory, operator_id="lab.my_filter",
title="My filter", category="data", version="0.1.0")` creates an ordinary v3
source project. It does not install or execute the script. Run `operon plugin
check PROJECT`, then `operon plugin build PROJECT`, and explicitly install the
wheel through Add operators. The selected category and title appear in the library.

The equivalent CLI authoring path is:

```sh
operon script extract copy.py --names repeat --output copy.snapshot.json
operon script package copy.snapshot.json --id lab.copy --title "Repeat text" --category data --output ./copy-project
operon plugin check ./copy-project
operon plugin build ./copy-project
```

The generated provider stores frozen source as literal data, calls the same
managed subprocess adapter at execution time, and owns `parameters.json` and an
adjacent Markdown guide. The implementation hash covers the script source.
Editing defaults in JSON changes the declaration without changing source identity;
saved workflows retain their own parameter values. Replace the generated generic
scientific guidance with a meaningful explanation before sharing the operator.

Python subprocesses inherit the selected worker's frozen absolute dependency
paths, including an isolated target, rather than silently falling back to host
packages. They do not add the script directory or current directory to imports.
Only declared metadata is checked at readiness; no user source is imported then.
