"""Dependency isolation adapter for the existing Step/Reader resource protocols."""
from copy import deepcopy
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading

from biopipe.targets import command, paths_for
from biopipe.wire import Wire


def call(state, descriptor, operation, payload, *, ctx=None, chunks=None, writer=None):
    memory = ctx.memory if ctx is not None else None
    base = memory.run_dir if memory else Path(tempfile.gettempdir())
    with tempfile.TemporaryDirectory(prefix='ipc-', dir=base) as temporary:
        directory = Path(temporary)
        def usage():
            return sum(p.stat().st_size for p in directory.iterdir() if p.is_file())
        def admit(count):
            if memory:
                from src.task.memory.config import DiskBudgetError
                with memory.store.lock:
                    needed = usage() + int(count)
                    limit = memory.config.disk_limit_bytes
                    if limit is not None and memory.store.disk_bytes + memory.store.staging_disk_bytes + needed > limit:
                        raise DiskBudgetError('Isolated operator exchange exceeds the run disk quota')
                    memory.store.transport_disk_bytes = needed
        wire = Wire(directory, buffer_bytes=memory.config.io_buffer_bytes if memory else 65536, admit=admit)
        argv = None
        process = None
        control_thread = console_thread = None
        try:
            wire.write('request.json', {'descriptor': descriptor, 'operation': operation, **payload})
            argv = command(paths_for(state, descriptor), 'biopipe.isolated_worker', [directory], directory)
            process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8', errors='replace', bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if ctx:
                ctx.event('isolated_started', name=descriptor['id'], operation=operation, pid=process.pid, python=sys.executable)
            messages = queue.Queue()
            errors = []
            marker = '\x1eBioPipe:' + directory.name + '\x1f'
            def forward_console(line):
                print(line, end='', flush=True)
                errors.append(line)
                if len(errors) > 100:
                    errors.pop(0)
            def read_control():
                try:
                    for line in process.stdout:
                        position = line.find(marker)
                        if position < 0:
                            # Native extensions can write directly to fd 1,
                            # bypassing Python's redirect_stdout.
                            forward_console(line)
                            continue
                        if position:
                            forward_console(line[:position])
                        frame = line[position + len(marker):]
                        value, end = json.JSONDecoder().raw_decode(frame)
                        messages.put(value)
                        if frame[end:].strip():
                            forward_console(frame[end:])
                except BaseException as exc:
                    messages.put({'event': 'failed', 'error': str(exc)})
                finally:
                    messages.put(None)
            def read_console():
                for line in process.stderr:
                    # Preserve the full console in the pipeline's existing log.
                    forward_console(line)
            control_thread = threading.Thread(target=read_control, daemon=True)
            console_thread = threading.Thread(target=read_console, daemon=True)
            control_thread.start()
            console_thread.start()
            transient = set()
            complete = False
            while True:
                if ctx and (ctx.task_dir / 'cancel.requested').exists():
                    raise RuntimeError('Run cancelled by user')
                if memory:
                    memory._barrier()
                try:
                    message = messages.get(timeout=.1)
                except queue.Empty:
                    continue
                if message is None:
                    break
                event = message['event']
                if event == 'failed':
                    raise RuntimeError(f"Isolated {descriptor['id']} failed:\n{message['error']}")
                if event == 'complete':
                    complete = True
                    continue
                reply = {}
                if event == 'disk_admission':
                    admit(message['bytes'])
                elif event == 'log':
                    if ctx:
                        ctx.event(message['name'], **message['fields'])
                elif event == 'next_chunk':
                    for name in transient:
                        wire.path(name).unlink(missing_ok=True)
                    before = {p.name for p in directory.iterdir()}
                    try:
                        block = next(chunks)
                    except StopIteration:
                        reply['end'] = True
                    else:
                        wire.write('chunk.json', block)
                        del block
                        transient = {p.name for p in directory.iterdir()} - before | {'chunk.json'}
                elif event == 'reader_block':
                    row, column, values = wire.read('block.json')
                    getattr(writer, message['method'])(row, column, values)
                    del values
                    # The child waits for this acknowledgement before reusing
                    # its buffer. No unbounded queue or concatenation occurs.
                    encoded = json.loads(wire.path('block.json').read_text(encoding='utf-8'))
                    def remove_arrays(value):
                        if isinstance(value, dict):
                            if value.get('type') == 'array': wire.path(value['file']).unlink()
                            for child in value.values(): remove_arrays(child)
                        elif isinstance(value, list):
                            for child in value: remove_arrays(child)
                    remove_arrays(encoded)
                    wire.path('block.json').unlink()
                else:
                    raise ValueError(f'Unknown isolated worker event: {event}')
                process.stdin.write(json.dumps(reply) + '\n')
                process.stdin.flush()
            process.wait(timeout=10)
            console_thread.join(timeout=5)
            control_thread.join(timeout=5)
            if not complete or process.returncode:
                raise RuntimeError(f"Isolated {descriptor['id']} exited {process.returncode}: {''.join(errors)}")
            # Child has exited: output deserialization cannot overlap with its
            # retained output arrays. Inputs in the child were copy-on-write.
            result = wire.read('result.json')
            if ctx:
                ctx.event('isolated_finished', name=descriptor['id'], operation=operation, pid=process.pid)
            return result
        except BaseException as exc:
            if ctx:
                ctx.event('isolated_failed', name=descriptor['id'], operation=operation, message=str(exc))
            raise
        finally:
            if process:
                if process.poll() is None:
                    from biopipe.processes import stop_tree
                    stop_tree(process)
                for thread in (control_thread, console_thread):
                    if thread:
                        thread.join(timeout=5)
                for pipe in (process.stdin, process.stdout, process.stderr):
                    pipe.close()
            if memory:
                memory.store.transport_disk_bytes = 0


def proxy_step(descriptor, state):
    from src.task.step.base import Step
    from src.task.memory.store import footprint
    resources = descriptor['resources']
    class IsolatedStep(Step):
        _isolated = True
        _context = None
        _context_bytes = 0

        @classmethod
        def bind_context(cls, ctx):
            cls._context = ctx
            context = {key: getattr(ctx, key) for key in ('manifest', 'params', 'step_params', 'metadata', 'artifacts')}
            cls._context_bytes = 4 * sum(footprint(context).values())
            cls.stream_fixed_bytes = resources.get('stream_fixed_bytes', 0) + 2 * 65536 + cls._context_bytes

        @classmethod
        def estimate_memory(cls, inputs, params, profiles):
            extra = 2 * 65536 + cls._context_bytes
            for form in inputs:
                refs = footprint(form)
                # Numeric residency plus tagged-JSON encoding/decoding objects.
                extra += sum(size * (1 if key < 0 else 4) for key, size in refs.items())
            ctx = cls._context
            if ctx and ctx.memory:
                ctx.memory.store.reserved = extra
                ctx.memory.store.ensure(0, 'isolation_estimate_admission')
            workspace, output = call(state, descriptor, 'estimate', {'inputs': inputs, 'params': params, 'profiles': profiles}, ctx=ctx)
            if any(type(v) is not int or v < 0 for v in (workspace, output)):
                raise ValueError('estimate_memory must return two non-negative integer byte counts')
            return workspace + extra, output

        def _run(self, ctx, inputs, stream=None):
            payload = {'inputs': inputs, 'context': {key: getattr(ctx, key) for key in
                       ('task_dir', 'out_dir', 'manifest', 'params', 'step_params', 'metadata', 'artifacts')}}
            if stream:
                payload['stream'] = {k: stream[k] for k in ('metadata', 'shape')}
            result = call(state, descriptor, 'stream' if stream else 'run', payload, ctx=ctx,
                          chunks=stream['chunks'] if stream else None)
            for name, form in result['outputs'].items():
                ctx[name] = form
            ctx.metadata.clear()
            ctx.metadata.update(result['metadata'])
            # Preserve runner-owned list identities (exports is retained by
            # runner.run); merge operator artifact additions in place.
            for key, value in result['artifacts'].items():
                if key != 'exports': ctx.artifacts[key] = value
            self.report = result['export']

        def run(self, ctx, inputs): self._run(ctx, inputs)
        def run_stream(self, ctx, stream): self._run(ctx, [], stream)
        def export(self, ctx): return self.report

    for key in ('version', 'parameters_schema', 'inputs_arity', 'outputs', 'output_parameter', 'legacy_parameters'):
        if key in descriptor: setattr(IsolatedStep, key, deepcopy(descriptor[key]))
    IsolatedStep.name = descriptor['id']
    IsolatedStep.input_contracts = descriptor['contracts']['inputs']
    IsolatedStep.output_contract = descriptor['contracts']['output']
    IsolatedStep.supports_streaming = 'stream' in resources['memory_modes']
    IsolatedStep.stream_protocol = resources.get('stream_protocol')
    # Account for the IPC block in each process plus the encoded write buffer.
    IsolatedStep.stream_buffer_multiplier = resources.get('stream_buffer_multiplier', 4) + 3
    IsolatedStep.stream_fixed_bytes = resources.get('stream_fixed_bytes', 0) + 2 * 65536
    IsolatedStep._package_descriptor = descriptor
    return IsolatedStep


def proxy_reader(descriptor, state):
    from src.reader.base import Reader
    class IsolatedReader(Reader):
        _context = None
        def probe(self, path, **args):
            result = call(state, descriptor, 'probe', {'arguments': {'path': path, **args}}, ctx=self._context)
            result['isolated'] = True
            return result
        def read(self, path, dims, labels, **args):
            return call(state, descriptor, 'read', {'arguments': {'path': path, 'dims': dims, 'labels': labels, **args}}, ctx=self._context)
        def read_to_disk(self, path, dims, labels, writer, chunk_bytes, **args):
            return call(state, descriptor, 'read_to_disk', {'arguments': {'path': path, 'dims': dims, 'labels': labels,
                'chunk_bytes': chunk_bytes, **args}, 'writer_shape': writer.shape}, ctx=self._context, writer=writer)
    for key in ('extensions', 'requires_siblings', 'excludes_siblings', 'handles_compression', 'parameters_schema', 'file_input'):
        if key in descriptor: setattr(IsolatedReader, key, deepcopy(descriptor[key]))
    IsolatedReader.output_contract = descriptor['contracts']['output']
    IsolatedReader.supports_disk_read = 'disk' in descriptor['resources']['memory_modes']
    IsolatedReader.disk_protocol = descriptor['resources'].get('disk_protocol')
    IsolatedReader.__name__ = descriptor['id']
    return IsolatedReader
