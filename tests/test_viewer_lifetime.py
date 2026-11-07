"""External viewers survive a Windows host job closing; computation stays owned."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil
import pytest


@pytest.mark.skipif(os.name != 'nt', reason='Windows Job Object lifecycle')
def test_viewer_survives_backend_job_close(tmp_path):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    class Basic(ctypes.Structure):
        _fields_ = [('per_process', ctypes.c_int64), ('per_job', ctypes.c_int64),
                    ('flags', wintypes.DWORD), ('min_working', ctypes.c_size_t), ('max_working', ctypes.c_size_t),
                    ('active', wintypes.DWORD), ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD), ('scheduling', wintypes.DWORD)]
    class IO(ctypes.Structure):
        _fields_ = [(key, ctypes.c_uint64) for key in ('read_count','write_count','other_count','read_bytes','write_bytes','other_bytes')]
    class Extended(ctypes.Structure):
        _fields_ = [('basic', Basic), ('io', IO), ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                    ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    limits = Extended(); limits.basic.flags = 0x2000 | 0x800  # kill owned work; permit explicit breakaway
    assert kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)), ctypes.get_last_error()
    script = tmp_path/'host.py'
    script.write_text('''import json,sys,time
from pathlib import Path
from types import SimpleNamespace
from operon.viewers import ViewerService
sys.stdin.readline()
folder=Path(sys.argv[1]); data=folder/'input.bed'; data.write_text('chr1\\t0\\t1')
app=SimpleNamespace(service=SimpleNamespace(directory=folder), artifacts=SimpleNamespace(preview=lambda *a,**kw:{'files':[{'role':'data','name':'input.bed','downloadable':True}]}, file=lambda *a:data))
service=ViewerService(app); entry=service.catalog()['igv']
entry.update(mode='manual', args=['-c','import time; time.sleep(60)'])
service.catalog=lambda:{'igv':entry}
service.configure('igv',sys.executable)
result=service.open('j','a','data','igv')
(folder/'viewer.pid').write_text(str(result['pid']))
time.sleep(60)
''', encoding='utf-8')
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1])}
    worker = subprocess.Popen([sys.executable, str(script), str(tmp_path)], stdin=subprocess.PIPE, env=env)
    viewer = None
    try:
        assert kernel.AssignProcessToJobObject(job, int(worker._handle)), ctypes.get_last_error()
        worker.stdin.write(b'go\n'); worker.stdin.flush()
        deadline = time.monotonic()+20
        while not (tmp_path/'viewer.pid').exists() and worker.poll() is None and time.monotonic()<deadline:
            time.sleep(.05)
        assert (tmp_path/'viewer.pid').exists(), 'Viewer did not launch'
        viewer = psutil.Process(int((tmp_path/'viewer.pid').read_text()))
        kernel.CloseHandle(job); job = None
        worker.wait(timeout=5)
        time.sleep(.3)
        assert viewer.is_running(), 'External viewer was terminated with Operon computation'
    finally:
        if job: kernel.CloseHandle(job)
        if worker.poll() is None: worker.kill()
        worker.wait(timeout=5)
        if viewer and viewer.is_running():
            viewer.terminate(); viewer.wait(timeout=5)
