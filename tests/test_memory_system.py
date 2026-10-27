from pathlib import Path
import pytest
from src.task.memory.system import cgroup_available


@pytest.mark.parametrize('version', [1, 2])
def test_nested_container_headroom_uses_tightest_parent(tmp_path, version):
    root = tmp_path/'memory'; child = root/'job'; child.mkdir(parents=True)
    limit, usage = ('memory.max', 'memory.current') if version == 2 else ('memory.limit_in_bytes', 'memory.usage_in_bytes')
    for path, cap, used in [(root, 900, 400), (child, 800, 100)]:
        (path/limit).write_text(str(cap)); (path/usage).write_text(str(used))
    kind = 'cgroup2' if version == 2 else 'cgroup'
    member = '0::/group/job' if version == 2 else '3:memory:/group/job'
    mounts = f'29 20 0:26 /group {root.as_posix()} rw - {kind} cgroup rw,memory'
    assert cgroup_available(10000, member, mounts) == 500
    assert cgroup_available(200, member, mounts) == 200
    (child/usage).write_text('900')
    assert cgroup_available(10000, member, mounts) == 0


def test_unlimited_cgroup_and_unreadable_usage(tmp_path):
    (tmp_path/'memory.max').write_text('max')
    mounts = f'29 20 0:26 / {tmp_path.as_posix()} rw - cgroup2 cgroup rw'
    assert cgroup_available(1000, '0::/', mounts) == 1000
    (tmp_path/'memory.max').write_text('900')
    with pytest.raises(FileNotFoundError): cgroup_available(1000, '0::/', mounts)


def test_container_namespace_mount_root(tmp_path):
    (tmp_path/'memory.limit_in_bytes').write_text('900')
    (tmp_path/'memory.usage_in_bytes').write_text('100')
    mounts = f'29 20 0:26 /docker/example {tmp_path.as_posix()} rw - cgroup cgroup rw,memory'
    assert cgroup_available(1000, '3:memory:/docker/example', mounts) == 800
