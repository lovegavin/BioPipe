"""Checksummed short-line frames also work through canonical-mode SSH gateways."""
import base64
import hashlib
import json
import re
import time
import zlib

VERSION = 1
MAX_MESSAGE = 128 * 1024**2
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)')


def frames(value, direction):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()
    if len(raw) > MAX_MESSAGE:
        raise ValueError('SSH control message is too large')
    data = base64.b64encode(zlib.compress(raw)).decode()
    digest = hashlib.sha256(raw).hexdigest()
    parts = [data[i:i+768] for i in range(0, len(data), 768)]
    # A leading newline separates container gateway envelopes from the frame.
    # Fixed-size atomic writes and acknowledgements avoid overflowing PTY queues.
    return [('\n'+f'BIOPIPE-{direction} {digest} {i} {len(parts)} '
             + f'{zlib.crc32(part.encode()):08x} {part}').ljust(1023)+'\n'
            for i, part in enumerate(parts)]


def receipt(part):
    fields = part.strip().split(' ', 4)
    return f'BIOPIPE-ACK {fields[1]} {fields[2]}'


def transmit(value, direction, write, read_line):
    """Send a bounded frame, waiting for its receipt before sending another."""
    for part in frames(value, direction):
        expected = receipt(part)
        for attempt in range(3):
            write(part)
            deadline = time.monotonic()+15
            try:
                while True:
                    if ANSI.sub('', read_line(deadline)).strip() == expected:
                        break
                break
            except TimeoutError:
                if attempt == 2:
                    raise TimeoutError('SSH frame was not acknowledged')


class Decoder:
    def __init__(self, direction):
        self.direction, self.pending, self.ack = direction, {}, None

    def feed(self, line):
        self.ack = None
        line = ANSI.sub('', line).strip()
        prefix = f'BIOPIPE-{self.direction} '
        if not line.startswith(prefix):
            return None
        try:
            _, digest, index, total, crc, data = line.split(' ', 5)
            index, total = int(index), int(total)
            if (not re.fullmatch('[a-f0-9]{64}', digest) or not 0 <= index < total <= 250000
                    or len(data) > 768 or f'{zlib.crc32(data.encode()):08x}' != crc):
                raise ValueError('Invalid SSH frame')
            record = self.pending.setdefault(digest, {'total': total, 'parts': {}})
            if record['total'] != total:
                raise ValueError('Inconsistent SSH frame count')
            record['parts'][index] = data
            self.ack = f'\nBIOPIPE-ACK {digest} {index}\n'
            if len(record['parts']) != total:
                return None
            packed = base64.b64decode(''.join(record['parts'][i] for i in range(total)), validate=True)
            inflater = zlib.decompressobj()
            raw = inflater.decompress(packed, MAX_MESSAGE+1)
            if len(raw) > MAX_MESSAGE or not inflater.eof or inflater.unused_data:
                raise ValueError('Invalid compressed SSH message')
            del self.pending[digest]
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError('SSH payload checksum mismatch')
            return json.loads(raw)
        except (ValueError, KeyError, TypeError, zlib.error) as exc:
            self.ack = None
            raise ValueError('Invalid BioPipe SSH response frame') from exc
