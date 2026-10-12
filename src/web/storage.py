"""Small, process-safe primitives for a Studio profile shared by launchers."""
import json
import os
from pathlib import Path
import tempfile
import threading
import time

_states = {}
_states_lock = threading.Lock()


class FileLock:
    """Reentrant within a thread; an OS lock releases even after a crash."""
    def __init__(self, path, timeout=30):
        self.path, self.timeout = Path(path), timeout
        key = os.path.normcase(str(self.path.resolve()))
        with _states_lock:
            self.state = _states.setdefault(key, {"mutex": threading.RLock(), "depth": 0})

    def __enter__(self):
        state = self.state
        state["mutex"].acquire()
        try:
            if not state["depth"]:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                handle = open(self.path, "a+b")
                handle.seek(0, os.SEEK_END)
                if not handle.tell():
                    handle.write(b"\0"); handle.flush()
                deadline = time.monotonic() + self.timeout
                try:
                    while True:
                        try:
                            handle.seek(0)
                            if os.name == "nt":
                                import msvcrt
                                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                            else:
                                import fcntl
                                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            break
                        except OSError:
                            if time.monotonic() >= deadline:
                                raise TimeoutError(f"Studio 数据目录正忙，请稍后重试：{self.path}")
                            time.sleep(.05)
                except BaseException:
                    handle.close()
                    raise
                state["handle"] = handle
            state["depth"] += 1
            return self
        except BaseException:
            state["mutex"].release()
            raise

    def __exit__(self, *exc):
        state = self.state
        try:
            state["depth"] -= 1
            if not state["depth"]:
                # Closing releases the OS lock on both Windows and POSIX.
                state.pop("handle").close()
        finally:
            state["mutex"].release()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
