"""Large catalogs must survive a slow but continuously advancing SSH transfer."""
from collections import deque
import random
import threading
from types import SimpleNamespace

import pytest

from operon.remote.client import SSHConnection, RemoteError
from operon.remote.protocol import frames, Decoder


def test_slow_valid_response_exceeds_old_absolute_deadline(monkeypatch):
    import operon.remote.client as module
    clock, lines = [0.0], deque()
    payload = random.Random(19).randbytes(8000).hex()
    def transmit(request, direction, write, read):
        lines.extend(frames({'id': request['id'], 'ok': True, 'value': payload}, 'R'))
        assert len(lines) > 5
    def read(deadline):
        if clock[0] + 20 > deadline:
            raise TimeoutError('test response still advancing')
        clock[0] += 20
        return lines.popleft()
    monkeypatch.setattr(module, 'transmit', transmit)
    monkeypatch.setattr(module.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(SSHConnection, 'connected', property(lambda self: True))
    client = SSHConnection.__new__(SSHConnection)
    client.lock = threading.RLock()
    client.channel = SimpleNamespace(sendall=lambda data: None)
    client._line = read
    client.close = lambda: None
    assert client.call('handshake') == payload
    assert clock[0] > 100


def test_duplicate_frames_do_not_count_as_forward_progress():
    decoder = Decoder('R')
    part = frames({'data': random.Random(1).randbytes(8000).hex()}, 'R')[0]
    decoder.feed(part)
    progress = decoder.progress
    decoder.feed(part)
    assert decoder.ack and decoder.progress == progress == 1
