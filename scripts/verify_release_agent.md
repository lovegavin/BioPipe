# Operon packaged release agent acceptance

For the management-runtime Setup, explicitly add `--prepare-environment` to the
`backend` phase to authorize route-only dependency preparation before the run.
Without that flag, a fresh profile may correctly fail preflight for missing
scientific packages. Preparation uses the separate plugins capability and does
not install into the application Python. Other phases reuse the prepared profile.

`verify_release_agent.py` connects to an **already running, explicitly selected**
Operon instance. Use a dedicated synthetic profile for the candidate installation.
Use a fresh evidence directory for each `backend` acceptance; subsequent phases
reuse that directory. Existing successful evidence is never silently overwritten
by launching a second analysis with the same submission identity.
It never creates a canvas session, publishes a selection, or changes an existing
user document. Backend results and actual EXE observations are separate evidence.

Use the package root containing `operon`, `src` and `scripts` as `--code-root`, its Python runtime
as `--python`, and the profile's
`workspace` directory as `--workspace`. Obtain the non-secret instance ID from
`operon --workspace <workspace> service status` or its discovery file. Do not copy
the discovery secret into the report. All phases require `--instance`.
The `operon` module, CLI and MCP identifiers are retained compatibility names;
they do not mean that an old Operon installation should be selected. Older
Lite/Full release reports remain historical; current Setup includes its runtime.

```text
<runtime-python> scripts/verify_release_agent.py backend --code-root <package-code-root> --python <runtime-python> --workspace <test-workspace> --instance <id> --evidence <new-evidence-directory>/agent --version 3.0.0
```

Pass `--version 3.0.0` explicitly; the script retains a historical default. The
complete Setup checklist is in [Operon 3.0 acceptance](../docs/OPERON_3_TEST_ACCEPTANCE.md).

The backend phase exercises real MCP stdio discovery and permission rejection,
workflow preparation/save/version conflicts, a managed CSV → PCA + statistics →
scatter run, independent parameter JSON, client-process exit during computation,
bounded logs, durable retries and original PNG/PDF/SVG file retrieval. The
synthetic input has mean 7.5; all figure formats have physical size 90 × 75 mm.
No browser or UI observation is claimed by this phase.
It also checks layered guides, conditional guide retrieval, compact query defaults,
the authenticated OpenAPI document and the packaged third-party client example.

For restart acceptance, close and reopen the test EXE normally after completion,
find its **new** instance ID, then run `retry` with the same workspace and evidence
directory. The script requires a different instance ID and must return the
original job without adding a task. The script does
not stop or restart a desktop-owned service itself.

For a real canvas acceptance, use the same arguments with these phase names:

1. `open`: open a new synthetic tab through MCP in a real existing desktop session.
2. In the EXE, click **PCA** once. Do not publish selection through an HTTP test stub.
3. `capture`: verify that MCP's selection tool and resource both report PCA.
4. `apply`: perform four edits in one transaction. In the EXE, verify the new
   **Agent diagnostic** branch, the changed tab name, and PCA's three components.
   Confirm that editing did not start another scientific run.
5. `undo`: issue one MCP undo. In the EXE, confirm the branch disappears and the
   previous name/PCA settings return. The script also checks exact graph equality.

If several real sessions are open, supply `--session <id>`. If the graph changed
after the batch, undo deliberately stops instead of undoing another person's work.
Record screenshot paths and actual EXE observations in a separate evidence file.

`--allow-headless` is only for a development smoke run. Such a report is not
packaged desktop or real UI acceptance. Reports contain local paths, versions,
synthetic data and run logs, but omit authentication tokens and discovery secrets.

The optional `verify_operon_candidate.py` is a different package-only backend
check. Run it with the bundled Python `-I`, a new report and a nonexistent work
directory outside the installation, without `--allow-development`. It uses a
temporary home/profile and cannot stand in for these six actual desktop phases.
