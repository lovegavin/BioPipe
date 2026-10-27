# Independent server handshake validation

Date: 2026-10-27. Branch: `work/server-handshake`, based on v0.7.1.
These results describe the development implementation, not a newly published
desktop package. See [the contract](SERVER_HANDSHAKE.md) for usage and cache rules.

## Local regression

| Check | Result |
| --- | --- |
| Complete Python suite, Windows / Python 3.11 | 611 passed, 6 skipped |
| Frontend suite | 97 passed across 14 files |
| TypeScript and production frontend build | Passed |
| Git whitespace/error check | Passed |

The Python suite includes manifest-only startup, retained registry overlays and
enabled state, runtime pin validation, cached dependency readiness, installer
receipt seeding, forced revalidation, nonblocking refresh, host trust, real
loopback SSH framing, file transfers and execution admission. UI tests distinguish
connect/install/refresh, preserve the selected action through host trust, and
retain actionable upgrade instructions. Skipped cases are not counted as passes;
the opt-in full native Hi-C analysis suite was not rerun in this validation.

## Real Linux server

The candidate was uploaded once into a new acceptance directory. It reused the
previously validated Python/Hi-C environment, without changing system Python or
the prior installation. This is a connection/reuse test, not another clean-machine
environment bootstrap test.

Candidate application archive: 434,749 bytes.
SHA-256: `c73475c97b6a422f58126ba742df43ed15584a60acd6c240cc58b3abe23da2b2`.

The provider's interactive SSH gateway disconnected during the first fixture
upload. A fresh connection completed and verified the candidate transfer before
testing. No partial upload was accepted as a runnable installation.

| Scenario | Observed result |
| --- | --- |
| Register a server installation | Stable application, interpreter and workspace paths published |
| Register a symlink-based virtual environment | Venv executable path retained; not replaced with base Python |
| Two independent client connections | Same workspace daemon identity and application directory |
| Client with the first client's catalog digest | Server omitted the unchanged catalog; client reused its verified copy |
| Manual installation without a readiness receipt | 86 entries reported unchecked, without automatic probes |
| Explicit registry/dependency refresh | All 67 operators and 19 Readers passed |
| Declared Hi-C executables | BWA, samtools, pairtools, cooler and cooltools available |
| Other client during background refresh | Resource and handshake requests completed while maintenance was running |
| Three subsequent handshakes | Dependency log remained exactly 49,762 bytes; dependency revision unchanged |
| New connections after disconnect | Passed readiness reused without another scan/probe/install |
| Branched workflow submission followed by client disconnect | Server completed missing-value filtering, PCA and describe |
| Other client following the task | Complete result and nonempty console available |
| Reconnect after completion | Same task history, cached catalog and passed readiness |

All ordinary connections in the acceptance harness ran with application packing,
installation and source-upload entry points replaced by assertions that fail if
called. No such entry point was called. These were independent SSH clients on one
Windows host, not a test involving two physical desktop computers.

This small server exposed a 1 GiB memory limit. Its frozen available-memory
snapshot was 483,803,136 bytes; the 90% admission pool was 435,422,822 bytes.
An initial test request for a 768 MiB process limit was correctly rejected.
The completed job used a 207 MiB managed budget, a 415 MiB process limit and
8 MiB chunks, selected from that server snapshot. Its host reservation was
released on completion, memory reporting was retained, and two requested final
artifacts were saved. The tiny input did not require emergency spilling.

Acceptance job: `20261027T143400-ed8f4405`; status `complete`, three analysis steps,
complete logs. Local diagnostic files are under `.tmp/handshake-acceptance/` and
are excluded from version control; they contain synthetic test evidence only.

## Shutdown and scope

The authorized shutdown request returned HTTP 200. A subsequent SSH gateway check
reported that no device was available and that the instance must be started to
connect. The test server was therefore not left running.

Daemon-restart receipt restoration, changed requirements, invalidated runtime
targets, incompatible protocols and forced verification were covered by local
regression tests. They are not presented as additional cloud scenarios. This
change does not replace the existing streaming, spill, per-route parameter JSON
or per-route execution settings. No GitHub release or desktop package was updated
as part of this acceptance run.
