# Operon Quickstart (English)

中文版见 [quickstart_full_flow.zh.md](quickstart_full_flow.zh.md).

## 0. Preflight

```bash
wsl -d Ubuntu-24.04
cd ~/Operon
git status --short
conda activate operon
python -m operon registry check     # expect errors []
```

## 1. Install the backend

```bash
python -m pip install -e . --no-deps --no-build-isolation
python -m operon registry check
```

## 2. Build the frontend

```bash
cd frontend
pnpm install
pnpm run build
```

## 3. Start Studio

Start the packaged desktop app, or run the web service from the repository root:

```bash
python -m operon web
```

## 4. Connect a remote server (optional)

Fill in host, user, port and the private-key path in Studio, then press test.
For a managed install, set the managed root (for example
`/public/home/<user>/operon`); Studio installs the environment and code there.
`operon_remote_status` / `operon_remote_ensure` reconnect key-based profiles
automatically; password profiles must be connected from the panel.
The dependency counter must be non-zero on the first connection.

## 5. Connect MCP (DeepSeek Harness first)

Add a `dsh-mcp-client` entry in `~/.dsh/profiles/desktop/cordis.patch.yml`
pointing at:

```yaml
command: operon
args: ["mcp", "--allow-run"]
```

Restart DSH and Studio, then open a new agent conversation with the single line:

```text
Please read docs/agent_bootstrap.md and prepare for the next task.
```

The agent calls `operon_status` and `operon_context` first, then waits for your
request. Other clients use the equivalent JSON config printed by the Agent panel.

## 6. Ask the agent for a route

Inputs in `examples/smoke_real_data/input/`: `vhh_1mel.pdb` (VHH chains A/B plus
lysozyme L/M) and `vhh.fasta` (the real 132-aa chain-A sequence).

```text
Use examples/smoke_real_data/input to design one route, any direction, and give me
an analysis that is genuinely valuable. Present the nodes, parameters and expected
artifacts first; run only after I confirm.
```

The agent searches and describes operators, proposes a graph with parameters and
expected outputs, and submits only after your confirmation. Do not reuse any
route.json or task.yaml from the repository; the route must be designed from the
operator catalog.

## 7. Edit the canvas

Agent edits are one undoable transaction. `operon_open` replaces or appends into
the current document; `operon_set_graph` swaps a whole graph;
`operon_set_execution` switches local/remote.

## 8. Start a run

`operon_validate`, then `operon_workflow_prepare(require_files=true)`, then
`operon_submit` (requires `--allow-run`). Jobs survive window closes.

## 9. Read results

Finished jobs list every run regardless of origin (frontend, agent, terminal).
Previews show labelled tables with `columns/row_labels/total/offset/limit`;
`operon_artifact_table` pages through the same data; download the artifact from
the row.

## 10. FAQ

- `operon_operator_search` empty: check that MCP points at the same interpreter.
- Run rejected: `operon_submit` needs `--allow-run` and an available admission slot.
- Remote run fails: call `operon_remote_ensure`, then check the installed version.
- Large weights: `python scripts/check_resources.py` prints what is missing and the
  install command.

## 11. Clean acceptance from scratch

1. Create an empty managed root (for example `/public/home/<user>/operon-accept`).
2. Install from Studio and wait for "environment ready".
3. Confirm first-connection counts: 867 operators, 108 Readers, 0 errors.
4. Run the route above and download one artifact.
5. Restart Studio; the connection and dependency counter must be restored without
   pressing refresh.
