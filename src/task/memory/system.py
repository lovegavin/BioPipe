"""One-shot host and Linux container memory headroom detection."""
from pathlib import Path, PurePosixPath
import re
import sys


def cgroup_available(host_available, membership, mountinfo):
    """Respect this process's cgroup and every visible parent hard limit.

    Subtract charged usage conservatively, including page cache. Do not count
    swap or assume that cached pages can all be reclaimed by an operator.
    """
    groups = {}
    for line in membership.splitlines():
        _, controllers, path = line.split(':', 2)
        if not controllers: groups['cgroup2'] = PurePosixPath(path)
        elif 'memory' in controllers.split(','): groups['cgroup'] = PurePosixPath(path)
    available = host_available
    unescape = lambda value: re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), value)
    for line in mountinfo.splitlines():
        before, after = line.split(' - ', 1)
        fields, options = before.split(), after.split()
        kind = options[0]
        if kind not in groups or (kind == 'cgroup' and 'memory' not in options[2].split(',')):
            continue
        root = PurePosixPath(unescape(fields[3])); mount = Path(unescape(fields[4]))
        try: relative = groups[kind].relative_to(root)
        except ValueError: continue
        current = mount.joinpath(*relative.parts)
        limit_name, usage_name = ('memory.max', 'memory.current') if kind == 'cgroup2' else ('memory.limit_in_bytes', 'memory.usage_in_bytes')
        while True:
            try: limit_text = (current/limit_name).read_text().strip()
            except FileNotFoundError: limit_text = 'max'  # Root may have no controller.
            if limit_text != 'max':
                limit = int(limit_text)
                usage = int((current/usage_name).read_text().strip())
                available = min(available, max(0, limit-usage))
            if current == mount: break
            current = current.parent
    return available


def available_memory():
    import psutil
    available = int(psutil.virtual_memory().available)
    if sys.platform == 'linux':
        try:
            membership = Path('/proc/self/cgroup').read_text()
            mountinfo = Path('/proc/self/mountinfo').read_text()
            available = cgroup_available(available, membership, mountinfo)
        except (OSError, ValueError) as exc:
            raise RuntimeError('Cannot determine Linux container memory headroom') from exc
    return available
