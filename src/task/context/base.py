# src/task/context/base.py
"""Context — the runtime image of a manifest."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from biopipe.run_log import RunLog

from src.core import ContextError, Form
from src.task.memory.config import MemoryConfig
from src.task.memory.runtime import MemoryRuntime


class Context:
    """Holds forms, params and task-scoped state."""

    def __init__(self, task_dir: Path, manifest: dict, *, run_log=None):
        self.task_dir = Path(task_dir).resolve()
        self.manifest = manifest
        self.params = manifest.get("params", {})
        self.forms: dict[str, Form] = {}
        self.metadata: dict = {}
        self.step_params: dict = {}
        self.artifacts: dict = {}
        self.output_validator = None
        self.written_outputs = set()

        self.out_dir = self.task_dir / "output"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._run_status = "created"
        self._run_error = None
        self.memory = None
        self.run_log = run_log or RunLog(self.out_dir)
        try:
            config = MemoryConfig.parse(manifest)
            if config.enabled:
                self.memory = MemoryRuntime(config, self.out_dir, manifest, self.run_log)
                self.forms = self.memory.store
            else:
                self.event("run_started", run_id=self.run_log.run_id, memory_enabled=False)
        except BaseException as exc:
            if run_log is None:
                try:
                    self.run_log.bootstrap_failure(self.task_dir, exc)
                finally:
                    self.run_log.close()
            raise

    def register_source(self, name: str, spec: dict) -> None:
        """Managed sources are read on first use; legacy mode stays eager."""
        from src.reader import read_source, pick_reader
        path = self.task_dir / spec["path"]
        selected_reader = pick_reader(path)
        if hasattr(selected_reader, '_context'):
            selected_reader._context = self
        def loader():
            return read_source(path, dims=spec["dims"], labels=spec.get("labels", {}),
                               **spec.get("args", {}))
        if self.memory:
            reader = pick_reader(path)
            args = dict(spec.get("args", {}))
            if reader.parameters_schema is not None:
                from biopipe_sdk.protocol import validate_parameters
                args = validate_parameters(reader.parameters_schema, args)
            from contextlib import nullcontext
            from src.reader import _decompressed, Reader
            def reader_path():
                return nullcontext(path) if reader.handles_compression else _decompressed(path)
            if reader.supports_disk_read or type(reader).probe is not Reader.probe:
                with reader_path() as actual_path:
                    probe = reader.probe(actual_path, **args)
            else:
                # The inherited probe only stats the original file; it does not
                # need to decompress anything. Custom header probes do.
                probe = reader.probe(path, **args)
            probe["file_bytes"] = path.stat().st_size
            disk_loader = None
            if reader.supports_disk_read:
                from biopipe_sdk.resources import validate_probe
                validate_probe(probe)
                def disk_loader(writer, chunk):
                    import numpy as np
                    from src.core.contracts import validate_form, validate_output, source_schema
                    with reader_path() as actual_path:
                        metadata = reader.read_to_disk(actual_path, spec["dims"], spec.get("labels", {}), writer, chunk, **args)
                    placeholder = Form(np.broadcast_to(np.zeros((), dtype=writer.dtype), writer.shape), **metadata)
                    requirement = {k: v for k, v in reader.output_contract.items() if k != "values"}
                    validate_form(placeholder, requirement, f"reader {type(reader).__name__} metadata")
                    validate_output(placeholder, source_schema(reader.output_contract, spec["dims"]),
                                    f"reader {type(reader).__name__} metadata")
                    # Validate real numeric blocks after flushing, never a fake
                    # zero array. A disk reader's values contract covers all cells.
                    if reader.output_contract.get("values"):
                        from src.core.contracts import validate_values
                        writer.close(retain=True)
                        with writer.path.open("rb") as source:
                            source.seek(writer.offset)
                            while True:
                                values = np.fromfile(source, dtype=writer.dtype, count=max(1, chunk // writer.dtype.itemsize))
                                if not values.size:
                                    break
                                validate_values(values, metadata["info"], reader.output_contract, f"reader {type(reader).__name__} output")
                    return metadata
            self.forms.register_source(name, loader, path.resolve(), probe, disk_loader)
        else:
            self[name] = loader()
            from src.core.files import FileArtifact
            form = self[name]
            shape = [] if isinstance(form, FileArtifact) else list(form.data.shape)
            self.event("source_loaded", name=name, shape=shape, dims=form.dims)
            print(f"[source] {name}: shape={shape}, dims={form.dims}")

    def __getitem__(self, name: str) -> Form:
        if name not in self.forms:
            raise ContextError(
                f"Form '{name}' not in context. "
                f"Available: {sorted(self.forms)}"
            )
        return self.forms[name]

    def __setitem__(self, name: str, form: Form) -> None:
        form.validate()
        if self.output_validator is not None:
            self.output_validator(name, form)
        self.forms[name] = form
        self.written_outputs.add(name)

    def has(self, name: str) -> bool:
        return name in self.forms

    def event(self, action: str, **details) -> None:
        if self.memory:
            self.memory.event(action, **details)
        else:
            self.run_log.event(action, **details)

    def log(self, message: str, **details) -> None:
        """Write a structured plugin event and a human-readable console line."""
        event = {"message": str(message), **details}
        # Fail early rather than corrupting the JSONL log with arbitrary values.
        json.dumps(event, allow_nan=False)
        self.event("operator_log", **event)
        self.metadata.setdefault("operator_logs", []).append(event)
        print(str(message), flush=True)

    def artifact_path(self, name: str) -> Path:
        """Allocate a run-local artifact path without permitting traversal."""
        from pathlib import PureWindowsPath
        path = Path(name)
        if not name or path.is_absolute() or PureWindowsPath(name).drive or ".." in path.parts or "\\" in name:
            raise ContextError("Artifact names must be relative paths within the run")
        target = (self.out_dir / "artifacts" / path).resolve()
        if not target.is_relative_to((self.out_dir / "artifacts").resolve()):
            raise ContextError("Artifact path escapes the run")
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def finalize(self) -> None:
        """Persist the summary and close the event journal in every memory mode."""
        try:
            self._write_summary()
        finally:
            self.run_log.close()

    def _write_summary(self) -> None:
        """Write the run summary.

        Reads ``artifacts["exports"]`` populated by the runner and
        writes two files:

        * ``output/run_summary.json`` — machine-readable index
        * ``output/run_summary.txt``  — human-readable index

        The summary lists step names, elapsed times and the paths of
        per-step JSON files. It does not repeat step details.
        """
        exports = self.artifacts.get("exports", [])
        close_error = None
        memory_report = None
        if self.memory:
            try:
                memory_report = self.memory.close(self._run_status, self._run_error)
            except Exception as exc:
                close_error = exc
                self._run_status, self._run_error = "failed", exc
                memory_report = self.memory.close("failed", exc)
        else:
            self.event("run_finished", status=self._run_status, error=str(self._run_error) if self._run_error else None)

        summary = {
            "task_dir": str(self.task_dir),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "n_steps": len(exports),
            "total_elapsed": round(
                sum(e["elapsed"] for e in exports), 4
            ),
            "steps": exports,
            "status": self._run_status,
            "error": str(self._run_error) if self._run_error else None,
            "run_id": self.run_log.run_id,
            "event_log": str(self.run_log.event_path),
        }
        if memory_report:
            summary["run_id"] = self.memory.run_id
            summary["memory_report"] = str(self.memory.run_dir / "memory_report.json")
            summary["event_log"] = str(self.memory.event_path)
            summary["managed_peak_bytes"] = memory_report["managed_peak_bytes"]

        json_path = self.out_dir / "run_summary.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        txt_path = self.out_dir / "run_summary.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(self._render_text(summary))
        (self.run_log.run_dir / "run_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        if close_error:
            raise close_error

    @staticmethod
    def _render_text(summary: dict) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append("Run summary")
        lines.append("=" * 60)
        lines.append(f"task      : {summary['task_dir']}")
        lines.append(f"generated : {summary['generated_at']}")
        lines.append(f"steps     : {summary['n_steps']}")
        lines.append(f"elapsed   : {summary['total_elapsed']:.3f}s")
        lines.append(f"status    : {summary.get('status', 'complete')}")
        if summary.get("error"):
            lines.append(f"error     : {summary['error']}")
        lines.append("")
        lines.append("-" * 60)
        lines.append(f"{'#':<4}{'step':<20}{'elapsed':>10}   export")
        lines.append("-" * 60)

        for e in summary["steps"]:
            lines.append(
                f"{e['index']:<4}"
                f"{e['name']:<20}"
                f"{e['elapsed']:>9.3f}s   "
                f"{e['export_path']}"
            )

        lines.append("")
        lines.append("=" * 60)
        lines.append(
            "Per-step details are at the export paths above. "
            "This file is an index only."
        )
        lines.append("=" * 60)
        return "\n".join(lines) + "\n"
