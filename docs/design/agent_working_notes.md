# Agent working notes

Practical rules for agents that extend Operon, debug remote installs or run the
release loop. These are process rules, not API documentation.

## Context and token discipline

- One shell call should do several checks (`git log` + `git status` + a filtered
  `pytest` tail), not one command per question.
- Generate files with a script (`python make_x.py` or a heredoc written to a
  file) instead of passing large content through the tool call.
- Filter long output: `| tail -20`, `| grep -E "FAILED|ERROR|passed"`,
  `| wc -l`. Never paste whole logs into the conversation.
- Reuse earlier results. Re-reading the same file or re-running the same probe
  costs a full context resend.
- Keep replies short: state the conclusion and the next action, not a retelling
  of the tool output.

## Shell and platform rules

- `ops_bash` runs Windows bash. `wsl.exe -d Ubuntu-24.04 -- bash -lc '...'` is
  the bridge to the Linux environment; `$VAR` inside that payload is consumed
  by the outer shell, so use literal absolute paths or a script file.
- The `write`/`edit` tools cannot write `\\wsl.localhost\...` paths
  (`ENOTSUP`). Write under `<temporary-directory>` and copy with a WSL script.
- PowerShell must run from `.ps1` files; avoid `$env:` in inline `-Command`.
- Server work: use Windows `ssh`/`scp` (`scp -O` or `ssh 'cat > file'` because
  the server may lack an SFTP subsystem); WSL egress to the server is blocked
  in this environment.

## Authoring and release gate

1. Three files per capability: `<module>.py`, `<module>.<Class>.parameters.json`
   and the generated `<module>.<Class>.md`.
2. `scripts/build_operator_docs.py` -> `python -m operon registry build` ->
   `python -m operon registry check`; the check must report `errors []`.
3. Tests: hand-computed case plus an authoritative oracle or a fake runner that
   asserts the exact command line and parsed output.
4. Version bump in `pyproject.toml`, `operon/__init__.py`, `README.md`,
   `docs/UNIFIED_MAIN.md`, `docs/package_protocol.md`,
   `docs/backend_versioning.md`, plus `docs/releases/vX.Y.Z.md`.
5. Run focused tests, then the six packaging tests, then commit with
   `Backend version: X.Y.Z (operators N, Readers 101)` in the body, annotated
   tag, push, sync `<Operon-directory>` when the user asks for it.
6. If the push fails, record the pending version in
   `~/operon-backlog.md` and retry next batch; never claim a release
   that is not on the remote.

## Remote install debugging

- Reproduce on the real host before changing code: read
  `~/.local/share/operon/managed-v1/setup-*.log`, then run the failing pip
  command by hand.
- Check the host `ldd --version`, `python -V`, and whether the failed package
  has a wheel for that platform (`pip download --only-binary=:all: --dry-run`).
- Prefer resolving packages on the host (conda-forge/bioconda for native
  binaries, pip wheels for Python) over compiling; compile only as the last
  stage with an explicit toolchain step.
- A conda package installed before pip can change the pip NumPy plan: put
  conda-only binaries (for example `pysam`) after the pip solve.

## Honesty rules

- Do not report a release, test pass or download that was not actually
  observed. Verify with `git log`, `git tag --points-at HEAD`, the receipt file
  or the printed counts.
- When a capability cannot be verified in this environment, ship the honest
  gate (resource preflight + explicit skip) and record the blocker instead of
  mocking the result.
