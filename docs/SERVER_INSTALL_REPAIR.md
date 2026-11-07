# Managed server installation: readiness and diagnostics

The installer distinguishes a usable base server from optional operator capabilities.
For example, adding an adapter that declares `resources.external_tools = ["flye"]`
must not prevent installation of a server whose base environment and Hi-C tools
are healthy. This declaration names an executable to check; it is not an automatic
Conda installation recipe or a database download instruction.

## Completion and failure rules

- Shared Python requirement failures and the explicit BWA, samtools, pairtools,
  cooler and cooltools checks still abort installation. A successful `pip check`
  alone is insufficient to publish a server registration.
- Missing external tools and unavailable dedicated environments retain `failed`
  status and their diagnostic text in `operon-ready.json`. The handshake restores
  matching successes **and failures**, without starting installation or probing
  the entire library again.
- Restored readiness is tied to implementation/dependency identity, runtime,
  external-tool declarations and environment declarations. A fresh failure is
  never overwritten with a historical success. Explicit dependency revalidation
  remains necessary after out-of-band changes to an existing environment.
- Execution placement still rejects hosts missing the tools required by a selected
  operator. A base server being ready does not make those operators executable.
- A failed model dependency command remains a failed capability in that setup
  attempt, even if importing the package afterwards happens to succeed.

The source/parameter JSON protocol, workflow values, memory planning, streaming,
spill, task admission and saved execution pins are unchanged.

## Locate the actual log

Use the installation directory in the desktop SSH connection profile, not the
current terminal directory. An empty installation-directory field uses the SSH
account's `$HOME/.local/share/operon`.

```text
<installation-directory>/managed-v1/setup-<source-digest-prefix>.log
```

The connection panel reports the absolute path before source upload. The file is
initialized then, records extraction and environment setup, and appends successive
attempts for the same source digest. Installation errors include its path. Failures
before the remote deployment directory exists cannot be logged there.

Read the last traceback and process result before interpreting earlier warnings.
The archive uses a fixed 2000-01-01 member timestamp for deterministic hashing
without epoch-zero warnings. A timestamp warning is not evidence of a dependency
resolution failure.

## Native environment hygiene

The verified micromamba binary lives under a versioned directory but keeps its
required executable basename:

```text
managed-v1/tools/micromamba-2.10.0/bin/micromamba
```

Managed Conda commands discard inherited activation variables, disable unrelated
Conda configuration files, and use explicit official channel URLs. SSH transport
and proxy settings are preserved. The installed environment's `bin` directory is
prepended to the server's PATH; developer-machine paths are never substituted.
Native package specifications are separate package-manager arguments but a quoted
single string in the installed marker. Empty optional requirement lists do not
invoke pip.

An HTTP 403 is a real download failure. This change avoids accidental inherited
mirror selection; it does not guarantee network access to an upstream channel or
install databases and weights automatically. Detailed per-operator diagnostics
remain available for repair.

## Scope of this repair

This repair addresses the reported 2.2.2 final failure for seven newly registered
external-tool adapters. It does not introduce package recipes for these tools or
turn the current monolithic server bootstrap into a fully independent library
installer. The remaining separation work is documented in
[the main/library audit](MAIN_LIBRARY_SEPARATION_AUDIT.md).
