"""One operator or Reader call in a fresh dependency process."""
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys
import traceback

from biopipe.wire import Wire


def main():
    directory = Path(sys.argv[1])
    control = sys.stdout
    marker = '\x1eBioPipe:' + directory.name + '\x1f'
    def exchange(message):
        control.write(marker + json.dumps(message) + '\n')
        control.flush()
        reply = json.loads(sys.stdin.readline())
        if 'error' in reply:
            raise RuntimeError(reply['error'])
        return reply
    def admit(count):
        exchange({'event': 'disk_admission', 'bytes': count})
    wire = Wire(directory, admit=admit)
    try:
        with redirect_stdout(sys.stderr):
            request = wire.read('request.json', mmap=True)
            from biopipe.install_targets import load_class
            cls = load_class(request['descriptor'])
            from biopipe_sdk.protocol import validate_extension, describe_operator, describe_reader
            descriptor = request['descriptor']
            validate_extension(cls, descriptor['kind'])
            actual = describe_operator(cls) if descriptor['kind'] == 'operator' else describe_reader(cls())
            if any(actual[k] != descriptor[k] for k in ('id', 'version', 'resources')):
                raise ValueError('Isolated implementation differs from its frozen descriptor')
            operation = request['operation']
            result = None
            if operation == 'estimate':
                result = cls.estimate_memory(request['inputs'], request['params'], request['profiles'])
            elif operation in ('read', 'probe', 'read_to_disk'):
                reader = cls()
                if operation == 'read_to_disk':
                    class Writer:
                        shape = tuple(request['writer_shape'])
                        def write(self, row, column, values): self.send('write', row, column, values)
                        def add(self, row, column, values): self.send('add', row, column, values)
                        def send(self, method, row, column, values):
                            import numpy as np
                            if np.asarray(values).nbytes > request['arguments']['chunk_bytes']:
                                raise ValueError('Reader block exceeds its declared chunk_bytes')
                            wire.write('block.json', (row, column, values))
                            exchange({'event': 'reader_block', 'method': method})
                    result = reader.read_to_disk(writer=Writer(), **request['arguments'])
                else:
                    result = getattr(reader, operation)(**request['arguments'])
            else:
                from src.task.context import Context
                # Reuse the SDK Context methods without creating another memory
                # runtime, another available-RAM scan, or a second run log.
                ctx = Context.__new__(Context)
                ctx.__dict__.update(request['context'])
                ctx.task_dir, ctx.out_dir = Path(ctx.task_dir), Path(ctx.out_dir)
                ctx.forms = dict(zip(ctx.step_params.get('_input_names', []), request.get('inputs', [])))
                ctx.memory = None
                ctx.output_validator = None
                ctx.written_outputs = set()
                def event(name, **fields):
                    exchange({'event': 'log', 'name': name, 'fields': fields})
                ctx.event = event
                step = cls()
                if operation == 'stream':
                    def chunks():
                        while not exchange({'event': 'next_chunk'}).get('end'):
                            chunk = wire.read('chunk.json')
                            try:
                                yield chunk
                            finally:
                                del chunk
                    stream = request['stream']
                    stream['chunks'] = chunks()
                    try:
                        step.run_stream(ctx, stream)
                    finally:
                        stream['chunks'].close()
                else:
                    step.run(ctx, request['inputs'])
                result = {'outputs': {name: ctx.forms[name] for name in ctx.written_outputs}, 'export': step.export(ctx),
                          'metadata': ctx.metadata, 'artifacts': ctx.artifacts}
            wire.write('result.json', result)
        control.write(marker + json.dumps({'event': 'complete'}) + '\n')
        control.flush()
    except BaseException:
        error = traceback.format_exc()
        print(error, file=sys.stderr, flush=True)
        control.write(marker + json.dumps({'event': 'failed', 'error': error}) + '\n')
        control.flush()
        raise SystemExit(1)


if __name__ == '__main__':
    main()
