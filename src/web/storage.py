"""Small, process-safe primitives for a Studio profile shared by launchers."""
import json
import os
from pathlib import Path
import threading
import time
import uuid

from operon.bytecode import io_path

_states = {}
_states_lock = threading.Lock()


class FileLock:
    """Reentrant within a thread; an OS lock releases even after a crash."""
    def __init__(self, path, timeout=30):
        self.path, self.timeout = Path(path), timeout
        # Resolve the native alias before keying: logical/extended paths and
        # symlink aliases must share one reentrant thread state and OS handle.
        key = os.path.normcase(str(io_path(self.path).resolve()))
        with _states_lock:
            self.state = _states.setdefault(key, {"mutex": threading.RLock(), "depth": 0})

    def __enter__(self):
        state = self.state
        state["mutex"].acquire()
        try:
            if not state["depth"]:
                native = io_path(self.path)
                native.parent.mkdir(parents=True, exist_ok=True)
                handle = open(native, "a+b")
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
    path = io_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # CPython's Windows mkstemp retries PermissionError when access(W_OK) says
    # yes, potentially billions of times for an ACL/audit denial. Retry actual
    # name collisions only; all write failures must reach the caller promptly.
    for _ in range(16):
        temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                                 getattr(os, 'O_BINARY', 0), 0o600)
            break
        except FileExistsError:
            continue
    else:
        raise FileExistsError(f'Unable to allocate a temporary JSON file beside {path}')
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
