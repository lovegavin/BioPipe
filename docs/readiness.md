# Selected-environment readiness

Studio, CLI and MCP use the same route-scoped validation service before a run.
Registering an operator does not install its scientific dependencies. Ordinary
validation is read-only: it checks the selected environment and reports blocked
declarations. Dependency preparation is a separate explicit request; validation
never silently modifies the running Python installation.

Placement during validation can select a host whose dependencies or tools are
missing, so that their exact failures can be reported and preparation remains
reachable. It still rejects unavailable hosts, unsupported operating systems,
missing operator declarations and unavailable code pins. Such a plan is marked
`validation_only`; submitting a task recomputes strict placement after readiness,
and never treats a validation-only placement as permission to execute.
Automatic placement prefers already compatible hosts when available; manual
placement can select a compatible operating system that still needs preparation.

Only operators and Readers used by the selected stages are checked. Sources in a
reusable route are interface placeholders, not additional physical input files.
The route remains an atomic placement unit, including its nested scripts.
Historical pins are resolved on the execution host; unrelated operators assigned
to another host do not become prerequisites for that host.

Each SSH target receives the required IDs and frozen script declarations. Script
language tools and Python requirements are inspected on that server. A disconnected
server cannot be considered ready based on a previous client result. An older
server without this validation operation must be upgraded explicitly.

Local successful results can be reused while the following identities remain
unchanged:

- the semantic workflow, parameter values, selected targets and frozen generation;
- source file metadata and declared companion-file metadata;
- marked operator reference paths;
- interpreter identity, environment directory metadata and immutable target receipts;
- declared tool executables, named interpreters, managed R receipts and PATH.

Canvas positions, titles and viewport changes do not invalidate readiness.
Blocked results are not reused. Successful dependency probes remain session-scoped
across ordinary parameter edits; an identified runtime replacement revokes the
affected success. Remote targets always receive a live request, while their
dependency session can retain passed probes.

This is metadata-based invalidation, not a complete filesystem integrity scan.
Input files are not read merely to validate availability. Out-of-band modifications
inside an installed dependency that retain all tracked metadata require an
explicit environment refresh. Execution still performs its normal file, contract,
memory-admission and task-lifecycle checks; a ready result is not a permanent
reservation of server capacity.

Initially, inline scripts support exactly one file output. Python requirement
versions and R/C/C++ executable availability are checked without executing the
script. Non-Python package declarations and Python direct URLs/extras require an
explicitly prepared environment; the service does not guess an installer command.
