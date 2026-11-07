# A small external application client

See [the API walkthrough](../../docs/api_quickstart.md). `run_workflow.py` uses the
public authenticated application API for preparation, validation, submission,
bounded waiting and native-file handoff. It does not start a desktop, embed an
agent or import an analysis implementation. Install Operon first, then run:

```text
python examples/api_client/run_workflow.py --workspace project --workflow project/route.json --request-id demo-001
```

Use `--job <id>` to reconnect without submitting. Results are already saved;
the output lists their API links. Copy only a chosen result when a third-party
application needs a local native file, using `--href <returned-href> --output
handoff/result.svg`. For multi-file artifacts also select a declared `--role`.
No credential is included in the output. Timeouts leave jobs running.
