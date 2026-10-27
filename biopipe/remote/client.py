"""Explicit host trust and framed SSH control, including bounded file chunks."""
import base64
from collections import deque
import hashlib
import re
import shlex
import threading
import time
import uuid

from .protocol import ANSI, Decoder, transmit


class RemoteError(ValueError):
    def __init__(self, message, *, code='remote_error', node_id=None):
        super().__init__(message)
        self.code, self.node_id = code, node_id


class HostKeyRequired(RemoteError):
    def __init__(self, key, changed=False):
        self.key = {'type': key.get_name(), 'base64': key.get_base64(),
                    'fingerprint': 'SHA256:'+base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')}
        self.changed = changed
        super().__init__('服务器主机密钥已变化，请核对指纹。' if changed else '首次连接，请核对服务器主机指纹。', code='host_key_required')


class SSHConnection:
    def __init__(self, profile, credentials, *, progress=None, cancel=None):
        import paramiko
        self.profile, self.lock = profile, threading.RLock()
        self.channel = None
        self.client = paramiko.SSHClient()
        self.buffer, self.lines, self.stderr = b'', deque(), ''
        trusted = profile.get('host_key')
        class Trust(paramiko.MissingHostKeyPolicy):
            def missing_host_key(policy, client, hostname, key):
                if not trusted or trusted['type'] != key.get_name() or trusted['base64'] != key.get_base64():
                    raise HostKeyRequired(key, changed=bool(trusted))
        self.client.set_missing_host_key_policy(Trust())
        try:
            self.client.connect(profile['host'], port=profile['port'], username=profile['username'],
                                password=credentials.get('password') or None,
                                passphrase=credentials.get('passphrase') or None,
                                key_filename=profile.get('key_path') or None,
                                allow_agent=profile['auth'] == 'agent', look_for_keys=profile['auth'] == 'agent',
                                timeout=20, auth_timeout=30, banner_timeout=30)
            managed = profile.get('environment') == 'managed'
            def bridge_command():
                # Tools installed alongside Python must be visible to workers.
                from pathlib import PurePosixPath
                path = str(PurePosixPath(profile['python']).parent)
                prefix = ('export PATH=' + shlex.quote(path) + ':"$PATH"; ') if managed else ''
                return (prefix + 'unset PYTHONHOME PYTHONPATH; export PYTHONNOUSERSITE=1; cd -- '
                        + shlex.quote(profile['app_dir']) + ' && exec ' + shlex.quote(profile['python'])
                        + ' -u -m biopipe.remote.server --workspace ' + shlex.quote(profile['workspace']))
            if profile.get('mode', 'exec') == 'shell':
                self.channel = self.client.invoke_shell(term='vt100', width=160, height=50)
                self._enter_shell(profile.get('menu_choice', ''))
                # Binary container envelopes must not undergo terminal newline
                # rewriting: it changes both their length header and payload.
                self.channel.sendall(('stty -echo -opost; ' + ('PS1=; PS2=;' if managed else bridge_command()) + '\n').encode())
                self.channel.sendall(b'\n')
            else:
                self.channel = self.client.get_transport().open_session(timeout=20)
                self.channel.settimeout(2)
                self.channel.exec_command('bash --noprofile --norc' if managed else bridge_command())
            self.client.get_transport().set_keepalive(20)
            self.channel.settimeout(2)
            if managed:
                from .provision import provision
                profile = provision(self, profile, progress or (lambda message: None), cancel or threading.Event())
                self.profile = profile
                self.channel.sendall((bridge_command() + '\n').encode())
            deadline = time.monotonic()+90
            while True:
                line = self._line(deadline)
                if line.strip() == 'BIOPIPE_REMOTE_READY 1': break
                self.stderr = (self.stderr + line + '\n')[-6000:]
            self.info = self.call('bootstrap')
            if self.info.get('protocol_version') != 1:
                raise RemoteError('服务器与桌面端的远程接口版本不兼容。')
        except BaseException:
            self.close()
            raise

    @property
    def connected(self):
        return bool(self.channel and not self.channel.closed and self.client.get_transport()
                    and self.client.get_transport().is_active())

    def _enter_shell(self, choice):
        deadline = time.monotonic()+90
        output, sent, last = '', 0, time.monotonic()
        last_output = time.monotonic()
        while time.monotonic() < deadline:
            if self.channel.recv_ready():
                data = self.channel.recv(65536)
                output = (output + data.decode('utf-8', errors='replace'))[-16000:]
                last_output = time.monotonic()
            clean = ANSI.sub('', output).replace('\r', '')
            self.stderr = clean[-6000:]
            if re.search(r'(?:^|\n)[^\n]*[\w/:~][#$] ?$', clean):
                return
            # Only a user-configured numeric menu choice is sent to a gateway.
            if choice and not sent and time.monotonic()-last_output >= 1 and re.search(r'(?m)^\s*'+re.escape(choice)+r'\s', clean):
                self.channel.sendall(choice+'\n'); sent = 1; last=time.monotonic()
            elif sent >= 1 and time.monotonic()-last > 5:
                # Some numbered gateways wait for a second line before attaching
                # the selected PTY. Never repeat the choice into a pending shell.
                self.channel.sendall('\n'); sent += 1; last = time.monotonic()
            if self.channel.closed:
                raise RemoteError('SSH 网关关闭了连接。')
            time.sleep(.1)
        raise RemoteError('未能进入服务器终端；请核对网关实例编号，或使用普通 SSH 模式。')

    def _line(self, deadline):
        while time.monotonic() < deadline:
            if self.lines:
                return ANSI.sub('', self.lines.popleft().decode('utf-8', errors='replace')).rstrip('\r')
            if self.channel.recv_stderr_ready():
                self.stderr = (self.stderr + self.channel.recv_stderr(65536).decode('utf-8', errors='replace'))[-6000:]
            if self.channel.recv_ready():
                data = self.channel.recv(65536)
                self.buffer += data
                parts = self.buffer.split(b'\n'); self.buffer = parts.pop(); self.lines.extend(parts)
                continue
            if self.channel.closed or self.channel.exit_status_ready():
                raise RemoteError('服务器连接已结束。请确认远端 Python 已安装本版 BioPipe。\n'+self.stderr[-2000:], code='remote_disconnected')
            time.sleep(.02)
        raise TimeoutError('服务器响应超时；任务可能仍在服务器运行，重连后查看运行记录。')

    def call(self, method, params=None):
        with self.lock:
            if not self.connected:
                raise RemoteError('服务器未连接，请重新连接后查看任务。', code='remote_disconnected')
            identity = uuid.uuid4().hex
            try:
                transmit({'id': identity, 'method': method, 'params': params or {}}, 'Q',
                         lambda part: self.channel.sendall(part.encode()), self._line)
                decoder = Decoder('R'); deadline=time.monotonic()+100
                while True:
                    try: response = decoder.feed(self._line(deadline))
                    except ValueError: continue  # No receipt; sender retries a damaged frame.
                    if decoder.ack: self.channel.sendall(decoder.ack.encode())
                    if response is None or response.get('id') != identity: continue
                    if not response.get('ok'):
                        raise RemoteError(response.get('error', 'Remote operation failed'), node_id=response.get('node_id'))
                    return response['value']
            except RemoteError as exc:
                if exc.code == 'remote_disconnected': self.close()
                raise
            except Exception as exc:
                self.close()
                raise RemoteError('SSH 连接中断；服务器任务不会因此停止。请重新连接。', code='remote_disconnected') from exc

    def close(self):
        if self.channel: self.channel.close()
        self.client.close()
