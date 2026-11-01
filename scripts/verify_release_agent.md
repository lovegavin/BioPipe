# Packaged release agent acceptance

`verify_release_agent.py` connects to an **already running, explicitly selected**
BioPipe instance. Use a dedicated synthetic profile for each release variant.
Use a fresh evidence directory for each `backend` acceptance; subsequent phases
reuse that directory. Existing successful evidence is never silently overwritten
by launching a second analysis with the same submission identity.
It never creates a canvas session, publishes a selection, or changes an existing
user document. Backend results and actual EXE observations are separate evidence.

Use the tested package's `backend` directory as `--code-root`, its Python runtime
as `--python` (or the selected external Python for Lite), and the profile's
`workspace` directory as `--workspace`. Obtain the non-secret instance ID from
`biopipe --workspace <workspace> service status` or its discovery file. Do not copy
the discovery secret into the report. All phases require `--instance`.

```text
python scripts/verify_release_agent.py backend --code-root <package-code-root> --python <runtime-python> --workspace <test-workspace> --instance <id> --evidence .tmp/release116/<variant>/agent
```

The backend phase exercises real MCP stdio discovery and permission rejection,
workflow preparation/save/version conflicts, a managed CSV → PCA + statistics →
scatter run, independent parameter JSON, client-process exit during computation,
bounded logs, durable retries and original PNG/PDF/SVG file retrieval. The
synthetic input has mean 7.5; all figure formats have physical size 90 × 75 mm.
No browser or UI observation is claimed by this phase.

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
