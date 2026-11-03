# Agent guide: repairing the environment and provisioning resources

This page is written for an agent that receives a task, discovers a missing
dependency or a missing weight/database, and has to repair the host before the
task can run. It is deliberately command-oriented: every step below is a
command the agent can execute and verify.

## Decision tree

1. **Is the Python package installed?** `python -c "import biopipe"` and
   `python -m biopipe registry check`. A missing operator module is a package
   install, a missing third-party library is a pip install, and a missing
   binary (foldseek, mkdssp, prodigal, vina, pdb2pqr, fpocket) is an apt or
   build install. Never install NVIDIA drivers inside WSL; the driver comes
   from the Windows host.
2. **Is the weight or database present?**
   `python scripts/check_resources.py --json` reports `ok / partial / missing`
   per declared file. Operators that need a resource call
   `require(resource_id, operator)` and raise a message with the expected path,
   the environment variable and the install command — read that message first,
   it is authoritative.
3. **Should the resource be provisioned?** If the task can run without it, use
   the gated operator and record the boundary. If it cannot, provision it with
   the workflow below.

## Provisioning workflow

Provisioning is a **host-level, one-time** action, not part of a job.

```bash
# what is missing, per resource
python scripts/check_resources.py --json

# plan only (no network)
python scripts/provision_resources.py --root /data/biopipe-resources --plan

# fetch with a mirror, parallel downloads and resume
python scripts/provision_resources.py \
  --root /data/biopipe-resources \
  --only boltz --only esm3 \
  --mirror https://hf-mirror.com \
  --jobs 4 --retries 3 --timeout 60

# verify without touching the network
python scripts/provision_resources.py --root /data/biopipe-resources --offline
```

Rules the provisioner enforces:

- files are written atomically (`.part` then rename), so an interrupted run
  never leaves a truncated file under the final name;
- an existing file is verified by size and SHA-256 (when the manifest declares
  one) and skipped when valid;
- a failed checksum is deleted, never accepted;
- one provisioning process holds `.biopipe-provision.lock` in the root, so two
  agents cannot download the same file twice;
- `--jobs N` parallelises files, `--retries` bounds attempts, `--timeout` is a
  read timeout so a stalled socket fails instead of hanging forever.

## Slow or unstable server uplink

Downloading multi-GB weights directly onto a server with a bad uplink is the
most common source of "the agent hung". Prefer moving the bytes once:

1. On a machine with good bandwidth (or with an already provisioned cache),
   provision into a staging directory:
   `python scripts/provision_resources.py --root ~/biopipe-staging --only boltz`.
2. Transfer the staging directory with a resumable transfer
   (`rsync -avP --partial`, or `scp -C`), which survives disconnects.
3. On the server, copy from the staged tree and verify:
   `python scripts/provision_resources.py --root /data/biopipe-resources --from-dir ~/biopipe-staging --offline`.
   `--from-dir` re-checks size and SHA-256 before renaming each file.

If a mirror is acceptable, `--mirror https://hf-mirror.com` rewrites
`huggingface.co` URLs; `--rewrite OLD=NEW` handles any other prefix.

## Environment repair commands

```bash
python -m pip install -e . --no-deps --no-build-isolation   # editable install
python -m pip install <library>                              # missing import
apt-get install -y dssp prodigal vienna-rna                  # missing binary
python -m biopipe registry build && python -m biopipe registry check
```

Do not rebuild the registry by hand; run the two commands above and require
`errors []`. A stale registry is reported as
`ValueError: Implementation code hash mismatch: <operator>`.

## Recording the result

After provisioning, record in the task report:

- resource ids and file names provisioned, with their root paths;
- whether each file was `downloaded`, `copied` (from `--from-dir`) or `skipped`
  (already valid);
- remaining `missing` / `failed` entries and the exact remedy command;
- the environment variables that point to the roots (for example
  `BIOPIPE_BOLTZ_CACHE=/data/biopipe-resources`), so a later agent finds the
  same files instead of downloading them again.

## Do not

- do not download multi-GB files inside a job step: jobs have wall-clock
  budgets and a lost connection wastes the whole job;
- do not bypass size or checksum verification to "make it work";
- do not install Linux NVIDIA drivers inside WSL, and do not assume a GPU is
  available — `device=cpu` must remain a supported path;
- do not write new defaults or absolute local paths into operator JSON; use the
  resource manifest (`biopipe/resources.json`) and environment variables;
- do not claim a resource works until a minimal real run succeeded; otherwise
  report it as gated, as `docs/design/hard_capability_status.md` does.
