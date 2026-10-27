"""Logged, cancellable external commands with run-local files and argv execution."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time


class ToolRunner:
    def __init__(self, ctx, params):
        self.ctx, self.params = ctx, params
        from uuid import uuid4
        self.directory = ctx.artifact_path("hic/" + uuid4().hex + "/run.json").parent
        self.directory.mkdir(parents=True, exist_ok=True)
        self.scratch = self.directory / "tmp"
        self.scratch.mkdir()
        mode = params.get("executor", "auto")
        self.wsl = mode == "wsl" or (mode == "auto" and os.name == "nt")
        self.prefix = ["wsl.exe"]
        if params.get("wsl_distribution"):
            self.prefix += ["--distribution", params["wsl_distribution"]]
        self.prefix += ["--exec"]
        self.memory_bytes = int(float(params.get("memory_mb", 256)) * 1024**2)
        config = getattr(getattr(ctx, "memory", None), "config", None)
        snapshot = getattr(ctx, "metadata", {}).get("external_resource_snapshot", {})
        self.budget = getattr(config, "budget_bytes", snapshot.get("budget_bytes", 0))
        self.disk_limit = getattr(config, "disk_limit_bytes", snapshot.get("disk_limit_bytes"))
        if self.budget and self.memory_bytes > self.budget:
            raise ValueError("External workspace exceeds the frozen run budget; lower memory_mb")
        self.threads = int(params.get("threads", 1))
        if os.environ.get('BIOPIPE_CPU_LIMIT'):
            self.threads = min(self.threads, max(1, int(os.environ['BIOPIPE_CPU_LIMIT'])))
        self.count = 0
        self.versions = {}
        if self.wsl:
            if not shutil.which("wsl.exe"):
                raise RuntimeError("Hi-C tools require Linux or an installed WSL2 distribution; see docs/HIC.md")
            try:
                self._probe(self.prefix + ["python3", "-c", "import sys; print(sys.version)"])
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                raise RuntimeError("WSL Python/tool environment is unavailable. Set executor=native on Linux, or configure WSL2; see docs/HIC.md") from exc

    def _probe(self, argv):
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=15, encoding="utf-8", errors="replace",
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode:
            raise RuntimeError(result.stdout[-2000:])
        return result.stdout.strip()

    def path(self, value):
        value = str(Path(value).resolve())
        if self.wsl:
            return self._probe(self.prefix + ["wslpath", "-a", "-u", value])
        return value

    def tool(self, name):
        value = self.params.get("tool_paths", {}).get(name, name)
        if self.wsl:
            if ":\\" in value or ":/" in value:
                value = self.path(value)
            # shutil.which in the execution environment, not the host PATH.
            found = self._probe(self.prefix + ["python3", "-c",
                "import shutil,sys; p=shutil.which(sys.argv[1]); print(p or ''); sys.exit(0 if p else 1)", value])
        else:
            found = shutil.which(value)
        if not found:
            raise RuntimeError(f"Missing external tool {name}; install the Hi-C tool environment from docs/HIC.md")
        return found

    def require(self, *names):
        for name in names:
            if name not in self.versions:
                tool = self.tool(name)
                log = self.directory / (name + ".version.txt")
                self.run([tool] + ([] if name == "bwa" else ["--version"]), stdout=log,
                         allowed_codes=(0, 1) if name == "bwa" else (0,), version_probe=True)
                self.versions[name] = {"stdout": str(log), "stderr": str(self.directory / f"{self.count:03d}.stderr.log")}

    def command(self, name, *args, stdout=None):
        return self.run([self.tool(name), *map(str, args)], stdout=stdout)

    def checkpoint(self, extra_disk=0):
        if (self.ctx.task_dir / "cancel.requested").exists():
            raise RuntimeError("Run cancelled by user")
        try:
            used = sum(p.stat().st_size for p in self.directory.parent.rglob("*") if p.is_file())
        except FileNotFoundError:
            used = 0
        store = getattr(getattr(self.ctx, 'memory', None), 'store', None)
        used += getattr(store, 'disk_bytes', 0)
        if self.disk_limit and used + extra_disk > self.disk_limit:
            raise RuntimeError("External working files exceed the run disk limit")
        if shutil.disk_usage(self.directory).free < extra_disk + 1024**2:
            raise RuntimeError("Insufficient disk space for external working files")
        return False

    def _stop(self, child, pid_file=None):
        if self.wsl and pid_file and pid_file.exists():
            try:
                pgid = int(pid_file.read_text(encoding="ascii"))
                for sig in ("-TERM", "-KILL"):
                    subprocess.run(self.prefix + ["kill", sig, "--", f"-{pgid}"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except (ValueError, OSError, subprocess.TimeoutExpired):
                pass
        if os.name != "nt":
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            import psutil
            try:
                process = psutil.Process(child.pid)
                children = process.children(recursive=True)
                for item in reversed(children):
                    try: item.kill()
                    except psutil.NoSuchProcess: pass
                process.kill()
                psutil.wait_procs(children, timeout=3)
            except psutil.NoSuchProcess:
                pass
        child.wait()

    def run(self, argv, *, stdout=None, allowed_codes=(0,), version_probe=False):
        self.count += 1
        log = self.directory / f"{self.count:03d}.stderr.log"
        output = Path(stdout) if stdout else self.directory / f"{self.count:03d}.stdout.log"
        output.parent.mkdir(parents=True, exist_ok=True)
        env = {"OMP_NUM_THREADS": str(self.threads), "OPENBLAS_NUM_THREADS": str(self.threads),
               "MKL_NUM_THREADS": str(self.threads), "TMPDIR": self.path(self.scratch),
               "TEMP": str(self.scratch), "TMP": str(self.scratch)}
        timeout = 15 if version_probe else self.params.get("timeout_seconds", 0)
        self.ctx.event("external_command", argv=list(argv), stderr=str(log), stdout=str(output), executor="wsl" if self.wsl else "native")
        executed = list(argv)
        pid_file = None
        if self.wsl:
            pid_file = self.directory / f"{self.count:03d}.pid"
            request = self.directory / f"{self.count:03d}.request.json"
            request.write_text(json.dumps({"argv": executed, "cwd": self.path(self.directory), "env": env,
                "pid_file": self.path(pid_file), "cancel": self.path(self.ctx.task_dir / "cancel.requested"),
                "timeout": timeout, "memory_bytes": self.memory_bytes}), encoding="utf-8")
            executed = self.prefix + ["python3", self.path(Path(__file__).with_name("tool_relay.py")), self.path(request)]
        start = time.monotonic()
        descendants = {}
        with output.open("wb") as out, log.open("wb") as err:
            child = subprocess.Popen(executed, stdout=out, stderr=err, cwd=self.directory,
                                     env={**os.environ, **env}, start_new_session=os.name != "nt",
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            try:
                while child.poll() is None:
                    self.checkpoint()
                    if timeout and time.monotonic() - start > timeout:
                        raise RuntimeError("External command timed out")
                    if not self.wsl:
                        import psutil
                        try:
                            process = psutil.Process(child.pid)
                            children = process.children(recursive=True)
                            descendants.update({p.pid: p for p in children})
                            rss = sum(p.memory_info().rss for p in [process, *children] if p.is_running())
                            if rss > self.memory_bytes:
                                raise RuntimeError("External process group exceeded memory_mb; increase the admitted workspace")
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    time.sleep(.1)
            except BaseException:
                self._stop(child, pid_file)
                self.ctx.event("external_failed", argv=list(argv), stderr=str(log), returncode=child.returncode)
                raise
            finally:
                if not self.wsl:
                    import psutil
                    for process in descendants.values():
                        try:
                            if process.is_running(): process.kill()
                        except psutil.NoSuchProcess:
                            pass
        self.ctx.event("external_exit", argv=list(argv), returncode=child.returncode, stderr=str(log), seconds=time.monotonic()-start)
        if child.returncode not in allowed_codes:
            with log.open("rb") as handle:
                handle.seek(max(0, log.stat().st_size - 4096))
                tail = handle.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{Path(argv[0]).name} exited {child.returncode}; full stderr: {log}\n{tail}")
        return output
