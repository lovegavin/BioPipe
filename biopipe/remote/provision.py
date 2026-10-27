"""SSH bootstrap without a preinstalled Python. Only owned server paths change."""
import base64
import hashlib
import gzip
import io
import json
from pathlib import Path
import re
import shlex
import tarfile
import time
import uuid

MAMBA_URL = 'https://conda.anaconda.org/conda-forge/linux-64/micromamba-2.10.0-0.tar.bz2'
MAMBA_ARCHIVE_SHA = '9a97976244929bbae28fb1fae504e74a3e7e6d1932870e3a03321f01b7fbd07b'
MAMBA_SHA = '701f39c06f8e6a670a0e186c8479b9e5c0502a2f0cda6cef65d83bdd2875e8bd'


def source_archive(root):
    """Explicit code allowlist. Never includes profiles, datasets, SSH or git files."""
    root = Path(root)
    files = [root / name for name in ('pyproject.toml', 'README.md', 'requirements-hic-linux.txt',
                                     'scripts/run.py', 'scripts/desktop_server.py')]
    for directory in ('biopipe', 'biopipe_sdk', 'src'):
        files += [p for p in (root / directory).rglob('*') if p.is_file()
                  and p.suffix in ('.py', '.json', '.png', '.jpg', '.jpeg', '.svg', '.webp', '.gif')
                  and '__pycache__' not in p.parts]
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        for path in sorted(files):
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError('Deployment source cannot contain symlinks outside its code root')
            data = path.read_bytes()
            member = tarfile.TarInfo(path.relative_to(root).as_posix())
            member.size = len(data); member.mode = 0o644; member.mtime = 0
            archive.addfile(member, io.BytesIO(data))
    return gzip.compress(stream.getvalue(), mtime=0)


class Shell:
    """Small acknowledged commands work on normal SSH and numbered PTY gateways."""
    def __init__(self, connection, progress, cancel):
        self.connection, self.progress, self.cancel = connection, progress, cancel

    def run(self, command, *, timeout=120):
        from .client import RemoteError
        if self.cancel.is_set():
            raise RemoteError('环境准备已取消。', code='remote_cancelled')
        marker = 'BP_SETUP_' + uuid.uuid4().hex
        # A subshell confines cd/env/exit and redirects only this command's output.
        self.connection.channel.sendall(('( ' + command + ' ) 2>&1; printf "\\n' + marker + ' %s\\n" "$?"\n').encode())
        end = time.monotonic() + timeout
        output = []
        while time.monotonic() < end:
            if self.cancel.is_set():
                self.connection.close()
                raise RemoteError('环境准备已取消；重新连接可重试。', code='remote_cancelled')
            try:
                line = self.connection._line(min(end, time.monotonic() + 1))
            except TimeoutError:
                continue
            match = re.search(re.escape(marker) + r' (\d+)\s*$', line)
            if match:
                if int(match[1]):
                    raise RemoteError('服务器环境准备失败：\n' + '\n'.join(output[-12:]), code='remote_setup_failed')
                return '\n'.join(output)
            if line.strip():
                output.append(line[-2000:]); output = output[-80:]
                self.progress(line[-2000:])
        raise RemoteError('服务器环境准备超时；可重新连接重试。', code='remote_setup_failed')

    def upload(self, path, data):
        """Idempotent indexed chunks, then a full checksum before use."""
        target = shlex.quote(path)
        encoded = base64.b64encode(data).decode()
        chunks = [encoded[i:i+768] for i in range(0, len(encoded), 768)]
        staging = path + '.parts-' + uuid.uuid4().hex
        self.run('mkdir -m 700 -- ' + shlex.quote(staging))
        for index, chunk in enumerate(chunks):
            self.run('printf %s ' + shlex.quote(chunk) + ' > ' + shlex.quote(staging + f'/{index:08d}'))
            if index % 100 == 0:
                self.progress(f'上传程序 {index + 1}/{len(chunks)}')
        # No recursive cleanup or executable unpack until exact content verified.
        self.run('cat ' + shlex.quote(staging) + '/* | base64 -d > ' + target +
                 ' && printf %s ' + shlex.quote(hashlib.sha256(data).hexdigest() + '  ' + path + '\n') +
                 ' | sha256sum -c - && rm -- ' + shlex.quote(staging) + '/* && rmdir -- ' + shlex.quote(staging))


def provision(connection, profile, progress, cancel, root=None):
    from .client import RemoteError
    shell = Shell(connection, progress, cancel)
    progress('检查服务器系统与部署目录')
    probe = shell.run('printf "\\nBP_SYSTEM=%s\\nBP_ARCH=%s\\nBP_HOME=%s\\n" "$(uname -s)" "$(uname -m)" "$HOME"; for bp_tool in bash tar base64 sha256sum flock; do command -v "$bp_tool" || exit 1; done')
    if not re.search(r'BP_SYSTEM=Linux\s*(?:\n|$)', probe) or not re.search(r'BP_ARCH=x86_64\s*(?:\n|$)', probe):
        raise RemoteError('自动部署目前支持 Linux x86_64；其他系统请使用已有环境。')
    home = re.search(r'BP_HOME=(/[^\r\n]*)', probe)
    if not home:
        raise RemoteError('无法确定服务器用户目录。')
    base = profile.get('managed_root') or home[1].rstrip('/') + '/.local/share/biopipe'
    q = shlex.quote
    shell.run('umask 077; mkdir -p -- ' + q(base) + '; test -w ' + q(base))
    # Own only a dedicated namespace, never an existing arbitrary installation.
    managed = base + '/managed-v1'
    shell.run('umask 077; mkdir -p -- ' + q(managed))
    data = source_archive(root or Path(__file__).resolve().parents[2])
    digest = hashlib.sha256(data).hexdigest()
    code = managed + '/code-' + digest[:20]
    archive = managed + '/source-' + digest[:20] + '.tar.gz'
    present = shell.run('if test -f ' + q(code + '/.source-sha') + '; then cat ' + q(code + '/.source-sha') + '; fi')
    if digest not in present:
        progress('上传与桌面端匹配的 BioPipe 程序')
        shell.upload(archive, data)
        # Concurrent publishers serialize extraction; published code stays immutable.
        shell.run('flock ' + q(managed + '/publish.lock') + ' bash -c ' + q(
            'set -eu; mkdir -p -- ' + q(code) + '; tar -xzf ' + q(archive) + ' -C ' + q(code) +
            '; printf %s ' + q(digest) + ' > ' + q(code + '/.source-sha')))
    env = managed + '/env-' + digest[:20]
    python = env + '/bin/python'
    log = managed + '/setup-' + digest[:20] + '.log'
    installer = code + '/biopipe/remote/install_linux.py'
    # micromamba is static: the server does not need Python, Conda, sudo or a compiler.
    mamba = managed + '/micromamba-2.10.0'
    install = f'''set -eu
umask 077
if ! printf '%s  %s\\n' {q(MAMBA_SHA)} {q(mamba)} | sha256sum -c - >/dev/null 2>&1; then
  echo 'Downloading the verified environment manager'
  if command -v curl >/dev/null; then
    for bp_attempt in 1 2 3; do
      curl --fail --location --continue-at - --connect-timeout 30 --max-time 600 --silent --show-error {q(MAMBA_URL)} -o {q(mamba + '.download')} && break
      echo "Download interrupted; resuming attempt $bp_attempt"
    done
  elif command -v wget >/dev/null; then wget --continue --timeout=30 --tries=3 -O {q(mamba + '.download')} {q(MAMBA_URL)};
  else echo 'Install curl or wget to download the managed runtime'; exit 1; fi
  printf '%s  %s\\n' {q(MAMBA_ARCHIVE_SHA)} {q(mamba + '.download')} | sha256sum -c -
  tar -xOjf {q(mamba + '.download')} bin/micromamba > {q(mamba + '.new')}
  printf '%s  %s\\n' {q(MAMBA_SHA)} {q(mamba + '.new')} | sha256sum -c -
  chmod 700 {q(mamba + '.new')}; mv -- {q(mamba + '.new')} {q(mamba)}
fi
export MAMBA_ROOT_PREFIX={q(managed + '/mamba-cache')}
if ! test -f {q(env + '/biopipe-ready.json')} || ! test -x {q(env + '/bin/bwa')} || ! test -x {q(env + '/bin/samtools')}; then
  echo 'Preparing Python and native Hi-C dependencies'
  bp_action=create; bp_repair=''
  if test -d {q(env + '/conda-meta')}; then
    bp_action=install
    if ! test -x {q(env + '/bin/bwa')} || ! test -x {q(env + '/bin/samtools')} || ! test -x {q(python)}; then bp_repair=--force-reinstall; fi
  fi
  {q(mamba)} --no-rc "$bp_action" $bp_repair -y -p {q(env)} --override-channels -c conda-forge -c bioconda --strict-channel-priority python=3.11 pip bwa=0.7.19 samtools=1.22.1 c-compiler cxx-compiler
fi
export PATH={q(env + '/bin')}:"$PATH"
export PYTHONNOUSERSITE=1
unset PYTHONPATH PYTHONHOME
{q(mamba)} --no-rc run -p {q(env)} {q(python)} -I {q(installer)} --code {q(code)} --digest {q(digest)}
'''
    # Redirect noisy resolver output on the server, but show bounded live lines.
    # The lock prevents two desktops from mutating the same target environment.
    script = managed + '/install-' + uuid.uuid4().hex + '.sh'
    shell.upload(script, install.encode())
    progress('检查并补齐 Python、BioPipe 与 Hi-C 依赖（首次可能需要数分钟）')
    # A dedicated process-group subprocess is killed if its SSH parent disconnects.
    command = ('umask 077; flock ' + q(managed + '/environment.lock') + ' bash ' + q(script) +
               ' > ' + q(log) + ' 2>&1 & bp_setup_pid=$!; ' +
               'trap \'kill "$bp_setup_pid" 2>/dev/null || true\' HUP INT TERM; ' +
               'while kill -0 "$bp_setup_pid" 2>/dev/null; do tail -n 1 ' + q(log) +
               '; printf "\\n"; sleep 2; done; wait "$bp_setup_pid"; bp_status=$?; tail -n 12 ' + q(log) + '; exit "$bp_status"')
    shell.run(command, timeout=3600)
    workspace = profile.get('workspace') or base + '/workspace'
    progress('环境就绪，正在连接运行服务')
    return {**profile, 'python': python, 'app_dir': code, 'workspace': workspace,
            'setup_log': log, 'managed_root': base}
