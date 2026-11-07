"""Install cancellation must own descendants even after their parent exits."""
import subprocess
import sys
import threading
import time

import psutil
import pytest

from operon.plugins import process_context, run_process


@pytest.mark.parametrize('trigger', ['cancel', 'timeout'])
def test_stopped_installer_releases_orphaned_output_pipes(tmp_path, trigger):
    pid_file = tmp_path / 'descendant.pid'
    # The grandchild inherits both captured pipes. Its parent exits successfully
    # before cancellation; enumerating the now-dead parent's children loses it.
    child_code = ('import os,sys,time; from pathlib import Path; '
                  'Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(60)')
    parent_code = ('import subprocess,sys,time; from pathlib import Path; '
                   'subprocess.Popen([sys.executable,"-c",sys.argv[1],sys.argv[2]]); '
                   'p=Path(sys.argv[2]); '
                   '\nwhile not p.exists(): time.sleep(.01)\n')
    cancellation = threading.Event()
    errors = []

    def run():
        process_context.cancel = cancellation if trigger == 'cancel' else None
        try:
            run_process([sys.executable, '-c', parent_code, child_code, pid_file],
                        timeout=1.5 if trigger == 'timeout' else 60)
        except (ValueError, subprocess.TimeoutExpired) as error:
            errors.append(error)
        finally:
            process_context.cancel = None

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    deadline = time.monotonic()+10
    stopped = False
    descendant_alive = True
    try:
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert pid_file.exists(), 'The diagnostic descendant did not start'
        time.sleep(.3)  # Parent has no further work after writing this marker.
        cancellation.set()
        thread.join(4)
        stopped = not thread.is_alive()
        # killpg delivers a signal; the scheduler can briefly still report the
        # orphan as running after the installer worker has returned. Observe
        # actual termination with a bounded wait, not a single instantaneous read.
        termination_deadline = time.monotonic()+1
        observed_states = []
        while True:
            try:
                child = psutil.Process(int(pid_file.read_text()))
                state = child.status()
                descendant_alive = child.is_running() and state != psutil.STATUS_ZOMBIE
            except psutil.NoSuchProcess:
                state, descendant_alive = 'gone', False
            if not observed_states or observed_states[-1] != state:
                observed_states.append(state)
            if not descendant_alive or time.monotonic() >= termination_deadline:
                break
            time.sleep(.01)
    finally:
        cancellation.set()
        if pid_file.exists():
            try:
                child = psutil.Process(int(pid_file.read_text()))
                # Scope cleanup to this test's unique command, never process name.
                if str(pid_file) in child.cmdline():
                    child.kill()
            except psutil.NoSuchProcess:
                pass
        thread.join(5)
    assert stopped, 'Installer cancellation/timeout remained blocked on an orphaned pipe'
    assert not descendant_alive, f'An owned installer descendant survived cancellation: {observed_states}'
    assert len(errors) == 1
    if trigger == 'timeout':
        assert isinstance(errors[0], subprocess.TimeoutExpired)
    else:
        assert 'cancelled' in str(errors[0])
