"""One-shot host and Linux container memory headroom detection."""
from pathlib import Path, PurePosixPath
import re
import sys


def _clean_inactive_cache(directory, kind):
    """Estimate reclaimable file pages, never swap/anonymous or dirty pages.

    memory.current includes page cache populated by package installation. Only
    count the clean inactive file portion, bounded by non-shmem file bytes.
    v1 total_* counters include descendants, like the hierarchical usage charge.
    Missing/old counters retain the conservative raw-usage calculation.
    """
    try:
        stats = dict(line.split() for line in (directory/'memory.stat').read_text().splitlines())
        names = ('file', 'inactive_file', 'shmem', 'file_dirty', 'file_writeback') if kind == 'cgroup2' else (
            'total_cache', 'total_inactive_file', 'total_shmem', 'total_dirty', 'total_writeback')
        file, inactive, shmem, dirty, writeback = (int(stats[name]) for name in names)
        if min(file, inactive, shmem, dirty, writeback) < 0:
            return 0
        return max(0, min(inactive, max(0, file-shmem))-dirty-writeback)
    except (OSError, ValueError, KeyError):
        return 0


def cgroup_available(host_available, membership, mountinfo):
    """Respect this process's cgroup and every visible parent hard limit.

    Subtract charged usage after the clean inactive file-cache estimate. Never
    count swap, active cache, shared memory or pages awaiting disk writeback.
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
                reclaimable = min(usage, _clean_inactive_cache(current, kind))
                available = min(available, max(0, limit-usage+reclaimable))
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
