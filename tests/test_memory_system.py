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


@pytest.mark.parametrize('version', [1, 2])
def test_clean_inactive_file_cache_is_available_but_dirty_and_shmem_are_not(tmp_path, version):
    cap, usage = ('memory.max', 'memory.current') if version == 2 else ('memory.limit_in_bytes', 'memory.usage_in_bytes')
    (tmp_path/cap).write_text('1000'); (tmp_path/usage).write_text('900')
    stats = {'file': 700, 'inactive_file': 600, 'shmem': 100,
             'file_dirty': 50, 'file_writeback': 20} if version == 2 else {
                 'total_cache': 700, 'total_inactive_file': 600, 'total_shmem': 100,
                 'total_dirty': 50, 'total_writeback': 20, 'inactive_file': 900}
    (tmp_path/'memory.stat').write_text('\n'.join(f'{key} {value}' for key, value in stats.items()))
    kind, member = ('cgroup2', '0::/') if version == 2 else ('cgroup', '3:memory:/')
    mounts = f'29 20 0:26 / {tmp_path.as_posix()} rw - {kind} cgroup rw,memory'
    assert cgroup_available(5000, member, mounts) == 630
    assert cgroup_available(250, member, mounts) == 250
    stats['file_dirty' if version == 2 else 'total_dirty'] = 900
    (tmp_path/'memory.stat').write_text('\n'.join(f'{key} {value}' for key, value in stats.items()))
    assert cgroup_available(5000, member, mounts) == 100


@pytest.mark.parametrize('contents', ['', 'inactive_file 800', 'file bad\ninactive_file 800', 'file 800\ninactive_file -1'])
def test_incomplete_or_invalid_cache_counters_keep_conservative_headroom(tmp_path, contents):
    (tmp_path/'memory.max').write_text('1000'); (tmp_path/'memory.current').write_text('900')
    (tmp_path/'memory.stat').write_text(contents)
    mounts = f'29 20 0:26 / {tmp_path.as_posix()} rw - cgroup2 cgroup rw'
    assert cgroup_available(5000, '0::/', mounts) == 100
