"""Own and stop process trees, never select processes by executable name."""
from contextlib import contextmanager
import os
import signal
import subprocess
import time

import psutil


class _WindowsJob:
    """Kernel ownership survives the installer parent exiting before its child."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                        ('flags', wintypes.DWORD), ('min_working_set', ctypes.c_size_t),
                        ('max_working_set', ctypes.c_size_t), ('active_processes', wintypes.DWORD),
                        ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                        ('scheduling', wintypes.DWORD)]

        class Limits(ctypes.Structure):
            _fields_ = [('basic', BasicLimits), ('io', ctypes.c_uint64 * 6),
                        ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                        ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]

        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                     ctypes.c_void_p, wintypes.DWORD]
        self.api.SetInformationJobObject.restype = wintypes.BOOL
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.AssignProcessToJobObject.restype = wintypes.BOOL
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL
        self.api.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.api.TerminateJobObject.restype = wintypes.BOOL
        self.api.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                       ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
        self.api.QueryInformationJobObject.restype = wintypes.BOOL
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Limits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def attach(self, process):
        import ctypes
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None

    def stop(self):
        import ctypes
        from ctypes import wintypes

        class Accounting(ctypes.Structure):
            _fields_ = [('times', ctypes.c_int64 * 4), ('page_faults', wintypes.DWORD),
                        ('total', wintypes.DWORD), ('active', wintypes.DWORD),
                        ('terminated', wintypes.DWORD)]

        if not self.api.TerminateJobObject(self.handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())
        deadline = time.monotonic() + 5
        while True:
            accounting = Accounting()
            if not self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(accounting),
                                                       ctypes.sizeof(accounting), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if not accounting.active:
                return
            if time.monotonic() >= deadline:
                raise TimeoutError('Owned installer processes did not stop')
            time.sleep(.01)


@contextmanager
def owned_process(args, **options):
    """Bound an installer and its descendants to one cancellable operation.

    Windows starts suspended until attached to a nested job, eliminating the
    spawn-before-registration race. POSIX gives the operation its own session.
    Always stop descendants before closing pipes: an orphan may hold them open.
    """
    owner = _WindowsJob() if os.name == 'nt' else None
    if owner:
        options['creationflags'] = options.get('creationflags', 0) | 0x00000004
    else:
        options['start_new_session'] = True
    process = None
    try:
        with subprocess.Popen(args, **options) as process:
            try:
                if owner:
                    owner.attach(process)
                    psutil.Process(process.pid).resume()
                yield process
            finally:
                if owner:
                    try:
                        owner.stop()
                    finally:
                        owner.close()
                else:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
    finally:
        if owner:
            owner.close()
            if process is not None and process.returncode is not None:
                # Popen otherwise waits for GC to release this native handle;
                # an exception traceback can keep the terminated PID alive.
                process._handle.Close()
                try:
                    psutil.Process(process.pid).wait(timeout=1)
                except psutil.NoSuchProcess:
                    pass


def stop_tree(process):
    if process.poll() is not None:
        return
    try:
        root = psutil.Process(process.pid)
        # Stop dispatch before enumerating descendants. Then freeze children
        # before terminating them, so a worker cannot spawn a replacement.
        root.suspend()
        children = root.children(recursive=True)
        for child in children:
            try: child.suspend()
            except psutil.NoSuchProcess: pass
        for child in reversed(children):
            try: child.kill()
            except psutil.NoSuchProcess: pass
        process.kill()
        process.wait(timeout=10)
        psutil.wait_procs(children, timeout=5)
    except psutil.NoSuchProcess:
        process.wait(timeout=10)
    finally:
        if process.poll() is None:
            try: psutil.Process(process.pid).resume()
            except psutil.NoSuchProcess: pass
