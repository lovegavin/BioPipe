# Independent server lifecycle and manifest handshake

Included in both v0.8.1 desktop editions. Operator SDK 3, graph pins and the
framed SSH transport remain unchanged. Older v0.7.1 desktop packages retain the
previous deployment-on-connect behavior.

See [validation results](SERVER_HANDSHAKE_VALIDATION.md) for local regression and
real-server acceptance evidence.

## Three separate actions

| Action | Work performed |
| --- | --- |
| Connect | Authenticate SSH, verify host trust, read the installed endpoint, negotiate compatibility, read registry/readiness documents and job history |
| Install / upgrade server | Upload the allowed application source, prepare an immutable code/environment directory, verify dependencies, atomically publish an installation pointer |
| Refresh operators and dependencies | Explicitly scan source/drop-in locations, publish valid registry changes, check entries whose readiness is not passed, refresh declared executable availability |

Connecting never invokes installation, source packaging, a recursive operator
scan, pip resolution or import probes. A desktop update does not choose a new
server environment. Installation and refresh remain explicit maintenance actions.
Background maintenance is single-flight and does not occupy the daemon's control
loop; other desktop clients can still handshake, inspect tasks and read logs.
Refresh checks dependencies but does not automatically install missing packages.

## Installation and workspace ownership

The default registry is `$HOME/.local/share/biopipe/server.json`, with HOME resolved
on the server. A configured installation directory overrides that location.
This compact document contains schema version 1, a stable installation identity,
absolute Linux application/Python paths, a default workspace and an audit version.
It contains no SSH passwords or private keys. Publication is locked and atomic.

Code and Python dependencies belong to the installation. Jobs, uploaded inputs,
transfer receipts and runtime dependency generations belong to the selected
workspace. Multiple desktops using the same SSH account, registered installation
and workspace share the server daemon and job history. They can also select
separate workspaces while reusing the installation. This is not a multi-tenant
authorization system: access continues to follow the SSH account and filesystem
permissions. Separate users must be granted access and configure a shared registry
location explicitly if they intend to share an installation.

Manual paths remain supported; no installation document is required for that
connection mode. An administrator can register existing compatible code without
uploading it from a desktop:

```sh
/srv/env/bin/python -m biopipe.remote.installation register \
  --base /srv/biopipe-service \
  --app-dir /srv/biopipe \
  --workspace /srv/biopipe-work
```

These are example paths, not built-in locations. Registration does not create a
Python environment or verify arbitrary system packages. A fresh manual installation
can return unchecked dependencies until explicit refresh validates them.

## Handshake contract

The client sends `handshake` over authenticated, checksummed SSH framing:

```json
{
  "version": 1,
  "protocol_version": 1,
  "operator_protocol": 3,
  "required_capabilities": [
    "manifest_handshake", "dependency_readiness", "registry_refresh", "jobs",
    "execution_pins", "streaming", "spill", "upload"
  ],
  "known_catalog_digest": "optional digest from the last successful connection"
}
```

The response contains the server application version for display, its workspace
identity, supported protocol/capabilities, registry digest, dependency revision,
readiness entries, declared tool availability, host resources and job history.
Application versions do not need to be identical. Required interface/capability
mismatches reject the connection with an actionable error; no automatic downgrade,
installation or lock rewriting follows. If the catalog digest matches, the server
omits the catalog and the desktop reuses its verified cached copy.

Missing or unchecked dependencies are reported per operator/Reader; they do not
prevent browsing files or viewing existing tasks. Workflow preparation, pin
compatibility and worker loading still enforce the selected operator code and
requirements. A successful connection is not a claim that every optional operator
can execute. Frozen parameter JSON and execution JSON remain per workflow.

## Document-first discovery and readiness

Server startup uses compiled `biopipe/builtin_packages.json` and the workspace's
plugin registry. It does not enumerate/stat/hash each provider's Python source.
Explicit refresh remains the operation that detects new or changed source.
Switching an existing workspace into this mode preserves its registered metadata
overrides and enabled/disabled providers. Actual worker loading still verifies
code identities; unchecked in-place source edits cannot silently run as old pins.

Successful checks stay passed across connections and can be reused after daemon
restart through `.studio/remote/readiness.json`. They are bound to the operator's
dependency/implementation identity, interpreter identity, environment directory
metadata and declared immutable target receipts. Default values and display-only
changes do not invalidate a successful dependency check. New/changed requirements
and changed runtime targets invalidate affected entries. Verified fresh installer
results seed this document without importing everything a second time.

Only named documents/directories and declared executables are inspected. This is
deliberately not continuous disk monitoring. Out-of-band edits inside installed
packages may not alter their directory identity; administrators can explicitly
revalidate every entry with `POST /api/remote/{id}/refresh` and the JSON body
`{"verify_all": true}`. This bypasses prior passed and installer receipts for the
maintenance run. Do not treat old receipts as a security attestation of arbitrary
administrator changes. Managed dependency targets remain immutable.

## Upgrade boundary

Older servers lack the handshake interface and require one explicit upgrade.
Registering an old installation alone cannot add that interface. An incompatible
running daemon is never killed/replaced during connection: finish its active jobs,
close its clients and allow its idle shutdown before reconnecting to upgraded
code. A workspace already served by a compatible daemon can be reached from a
different bridge path without restarting it. Existing jobs keep their original
worker environments, memory/spill settings and audit locks.

Local HTTP endpoints are `/api/remote/{id}/connect`, `/install` and `/refresh`.
Installation progress remains available from `/setup`. Server maintenance uses
`refresh_registry` and `refresh_status`; neither starts a scientific workflow.
SSH password/passphrase values remain session-only and are never persisted in
registration, readiness or workflow files.
