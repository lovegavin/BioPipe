# Unified main 0.116.0 validation

Date: 2026-11-01. Application: **0.116.0**. SDK: **3.1.0**. Operator protocol:
**v3**. This is a source integration acceptance record, not acceptance of a newly
packaged desktop executable.

## Environment and results

The local acceptance environment used Windows and Python 3.11.15. Additional
scientific test dependencies were installed in a separate test-only directory;
the previously distributed runtime was not modified.
These included scanpy 1.11.5, openpyxl 3.1.5 and arch 8.0.0; their absence would
skip the corresponding optional tests in a smaller installation.

| Check | Result |
| --- | --- |
| Complete Python regression | 1,233 passed, 129 skipped, 0 failures/errors; 1,362 collected, 27 min 14 s |
| Follow-up Markdown portability regressions | 12 passed, including two new newline/legacy-cache cases |
| Core-only static declaration/migration gate | 13 passed; implementations cannot be imported during declaration checks |
| Fresh Git source archive | Registry and documentation checks both report no changes or errors after the newline fix |
| Frontend tests | 117 passed across 17 files |
| TypeScript and production frontend build | Passed; existing bundle-size advisory remains |
| Static registry consistency | 405 operators, 88 Readers, 7 providers, 24 templates; no errors or pending generated changes |
| Bundled documentation | 493 Markdown companions; generation-aware search and selected-section retrieval |
| Five public-data workflows | 60 completed steps; 19 figure sets with PNG, PDF and SVG outputs |
| Legacy source archive | ZIP integrity and GitHub asset size/SHA-256 verified against the original main snapshot |

See [public-data workflow validation](../../examples/route_combinations/VALIDATION.md)
for the five execution records, input checksums, memory observations and scientific
interpretation limits. The old main archive preserves commit
`9b6bbdd024fb4f59aa65b0850f72c36ec6df4538` and is available from
[the legacy release](https://github.com/lovegavin/Operon/releases/tag/legacy-main-20261101).

## Coverage

- Shared workflow, task and artifact services through authenticated HTTP, CLI and
  MCP, without a desktop window or frontend build.
- A non-editable installed wheel executing a worker outside the source checkout.
- Frozen workflow parameters, historical implementation pins, declaration-only
  changes, package integrity and documentation-only updates.
- Separate read/edit/run scopes, revision conflicts, durable submission receipts,
  cancellation and bounded log reads.
- Managed memory, admission, streaming, disk-backed Readers, emergency spill and
  conflict-only dependency isolation.
- Local SSH fixtures covering transfers, reuse, reconnection and mixed execution;
  explicit Reader selection through import, save, export and execution.
- Registry portability, long Windows paths and configured input/output boundaries.

The full regression preceded a clean-checkout CI finding: Windows-generated
Markdown used CRLF bytes, while Git committed LF bytes. The follow-up fix
canonicalizes documentation digests, preserves historical raw-byte verification
and writes generated Markdown as LF. Its 12 focused checks and a fresh Git
archive check passed. Only documentation/declaration hashes changed for 490
generated pages; all operator code and execution identities remained unchanged.
The core-only CI environment also exposed an obsolete test that imported the whole
library to inspect schemas. That gate now compiles every declaration and compares
it to the registered descriptor while explicitly rejecting implementation imports;
optional scientific dependencies remain optional. Runtime execution tests remain
separate.

## Limits

The full Python run reported 20 warnings, including upstream deprecations and
small-fixture numerical warnings. Its 129 skips were explicit:

| Reason | Skipped tests |
| --- | ---: |
| R reference/integration checks: `Rscript` unavailable | 110 |
| External real-data SOP fixtures not present | 13 |
| `pysam` or `pyBigWig` unavailable | 3 |
| Opt-in real Linux Hi-C environment not enabled | 2 |
| Windows symbolic-link creation permission unavailable | 1 |

Local SSH fixtures do not constitute a new live-cloud acceptance run. The complete
bundled library is registered and documented, but this does not claim every
parameter combination or third-party program has been exercised.

Generated reference documents are identified as generated; they are descriptions
derived from the declared contracts and schemas, not independent scientific
review. The curated public-data runs likewise establish execution and output
integrity, not all of the author's biological interpretations.

No new Lite or bundled-environment EXE was built in this source-integration task.
The legacy archive does not replace v0.8.3 as the latest desktop release.
