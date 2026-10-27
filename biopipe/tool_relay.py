"""Standalone Linux process-group relay; also used inside WSL (stdlib only)."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main():
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    child = subprocess.Popen(request["argv"], start_new_session=True,
                             cwd=request["cwd"], env={**os.environ, **request["env"]})
    Path(request["pid_file"]).write_text(str(child.pid), encoding="ascii")
    start = time.monotonic()
    try:
        while child.poll() is None:
            if Path(request["cancel"]).exists():
                raise RuntimeError("Run cancelled by user")
            if request["timeout"] and time.monotonic() - start > request["timeout"]:
                raise RuntimeError("External command timed out")
            rss = 0
            for status in Path('/proc').glob('[0-9]*/stat'):
                try:
                    fields = status.read_text().rsplit(')', 1)[1].split()
                    if int(fields[2]) == child.pid:
                        rss += int(fields[21]) * os.sysconf('SC_PAGE_SIZE')
                except (OSError, ValueError, IndexError):
                    pass
            if request.get('memory_bytes') and rss > request['memory_bytes']:
                raise RuntimeError('External process group exceeded memory_mb; increase the admitted workspace')
            time.sleep(.1)
        return child.returncode
    finally:
        # Include grandchildren even if the group leader exited first.
        try:
            os.killpg(child.pid, signal.SIGTERM)
            time.sleep(.1)
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()


if __name__ == "__main__":
    sys.exit(main())
