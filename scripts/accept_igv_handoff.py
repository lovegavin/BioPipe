"""Run a real public-API workflow and prepare its native output files for IGV.

This is an opt-in acceptance command, not a normal CI or GUI launch. It uses an
isolated workspace, installs the example package through the public CLI, starts
the ordinary headless service, and stops only the service it started. IGV and
Java are separately supplied; no desktop process is launched by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

INTERVALS = [('chrTest1', 100, 220), ('chrTest1', 180, 300), ('chrTest1', 300, 340),
             ('chrTest1', 900, 930), ('chrTest1', 1800, 1900), ('chrTest1', 1850, 2100),
             ('chrTest2', 500, 700), ('chrTest2', 650, 900), ('chrTest2', 1600, 1800)]
EXPECTED = [('chrTest1', 100, 340, 3), ('chrTest1', 900, 930, 1), ('chrTest1', 1800, 2100, 2),
            ('chrTest2', 500, 900, 2), ('chrTest2', 1600, 1800, 1)]


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def reference(directory):
    """Write a tiny two-contig FASTA with exact standard faidx byte offsets."""
    fasta = directory / 'synthetic.fa'
    entries = []
    with fasta.open('wb') as stream:
        for chromosome in ('chrTest1', 'chrTest2'):
            stream.write(f'>{chromosome}\n'.encode())
            offset = stream.tell()
            for _ in range(50):
                stream.write(b'ACGT' * 15 + b'\n')
            entries.append(f'{chromosome}\t3000\t{offset}\t60\t61\n')
    fasta.with_suffix('.fa.fai').write_text(''.join(entries), encoding='ascii', newline='\n')
    return fasta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New isolated acceptance directory')
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    scratch = root / 'tmp'; scratch.mkdir()
    os.environ.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', TEMP=str(scratch), TMP=str(scratch),
                      OPERON_ADMISSION_DIR=str(root / 'admission'))
    project = root / 'plugin'
    shutil.copytree(ROOT / 'examples/igv_handoff', project,
                    ignore=shutil.ignore_patterns('dist', 'build', '*.egg-info', '__pycache__'))
    workspace = root / 'workspace'; workspace.mkdir()
    data = workspace / '.studio'
    handoff = root / 'handoff'; handoff.mkdir()
    (workspace / 'input.bed').write_text(''.join(f'{c}\t{s}\t{e}\n' for c, s, e in INTERVALS),
                                         encoding='ascii', newline='\n')
    def cli(*arguments):
        value = subprocess.run([sys.executable, '-m', 'operon', '--workspace', str(workspace),
                                '--data-dir', str(data), *map(str, arguments)], cwd=ROOT,
                               capture_output=True, text=True, encoding='utf-8', timeout=240)
        if value.returncode:
            raise RuntimeError(f'CLI failed: {arguments}\n{value.stdout}\n{value.stderr}')
        return json.loads(value.stdout)
    built = cli('plugin', 'build', project)
    dump(root / 'build.json', built)
    installed = cli('plugin', 'install', built['wheels'][0])
    dump(root / 'install.json', installed)
    graph = {'schema_version': 2, 'name': 'Genome tracks for IGV', 'base_dir': '.',
             'memory': {'enabled': True, 'auto_spill': True, 'budget_mb': 32, 'process_limit_mb': 512,
                        'chunk_mb': .01, 'io_buffer_kb': 4, 'keep': ['tracks']},
             'nodes': [{'id': 'input', 'kind': 'source', 'source': {'path': 'input.bed', 'reader': 'BedReader',
                        'dims': ['region', 'field'], 'labels': {'region': 'auto', 'field': 'builtin'}}},
                       {'id': 'merge', 'kind': 'operator', 'operator': 'interval_merge',
                        'params': {'min_overlap': 0, 'output': 'merged'}},
                       {'id': 'tracks', 'kind': 'operator', 'operator': 'example.genome_tracks',
                        'params': {'assembly': 'operon-synthetic-v1', 'output': 'tracks'}}],
             'edges': [{'id': 'e1', 'source': 'input', 'target': 'merge'},
                       {'id': 'e2', 'source': 'merge', 'target': 'tracks'}]}
    dump(root / 'workflow.json', graph)
    from operon.client import Client, instances
    from operon.application import ACTIVE
    existed = bool(instances(data))
    client = Client(data, name='igv-acceptance', scopes=['context', 'edit', 'run'],
                    auto_start=True, workspace=workspace, require_api=1)
    try:
        assert client.sessions() == [], 'The acceptance workflow must not depend on a canvas'
        prepared = client.request('/v1/workflows/prepare', {'graph': graph})
        saved = client.request('/v1/workflows', {'graph': prepared})
        submitted = client.request('/v1/jobs', {'workflow_id': saved['id'], 'expected_version': saved['version'],
                                               'request_id': 'igv-acceptance-1'})
        key = submitted['id']
        deadline = time.monotonic() + args.timeout
        while True:
            job = client.request('/v1/jobs/' + key)
            if job['status'] not in ACTIVE:
                break
            if time.monotonic() > deadline:
                client.request('/v1/jobs/' + key + '/cancel', {})
                raise TimeoutError(f'Job {key} did not finish within {args.timeout}s')
            time.sleep(.25)
        dump(root / 'job.json', job)
        logs = client.request('/v1/jobs/' + key + '/logs?limit=1048576')
        (root / 'console.log').write_text(logs['text'], encoding='utf-8', newline='\n')
        if job['status'] != 'complete':
            raise RuntimeError('Job failed: ' + str(job.get('error')))
        index = client.request('/v1/jobs/' + key + '/artifacts')
        parameters = client.request('/v1/jobs/' + key + '/parameters')
        dump(root / 'artifact-index.json', index)
        dump(root / 'frozen-parameters.json', parameters)
        assert job['allocation']['memory_enabled']
        assert (data / 'jobs' / key / 'parameters.json').is_file()
        assert (data / 'workflows' / saved['parameters_file']).is_file()
        assert (data / 'workflows' / saved['execution_file']).is_file()
        retained = next(a for a in index['artifacts'] if a['kind'] == 'file' and a['available'])
        prefix = f'/v1/jobs/{key}/artifacts/{retained["artifact_id"]}/file'
        for role, name in [('bed', 'merged.bed'), ('bedgraph', 'values.bedgraph'), ('provenance', 'provenance.json')]:
            client.download(prefix + '?role=' + role, handoff / name)
        provenance = json.loads((handoff / 'provenance.json').read_text())
        actual = []
        for line in (handoff / 'values.bedgraph').read_text().splitlines():
            chromosome, start, end, value = line.split('\t')
            actual.append((chromosome, int(start), int(end), float(value)))
        assert actual == EXPECTED, (actual, EXPECTED)
        bed_rows = [line.split('\t') for line in (handoff / 'merged.bed').read_text().splitlines()]
        assert [(row[0], int(row[1]), int(row[2])) for row in bed_rows] == [row[:3] for row in EXPECTED]
        assert provenance['chromosomes'] == ['chrTest1', 'chrTest2']
        for role in ('bed', 'bedgraph'):
            assert digest(handoff / provenance['files'][role]['name']) == provenance['files'][role]['sha256']
        reference(handoff)
        # Relative resource paths make the complete handoff directory relocatable.
        session = ET.Element('Session', genome='synthetic.fa', locus='chrTest1:1-3000', version='3')
        resources = ET.SubElement(session, 'Resources')
        ET.SubElement(resources, 'Resource', path='merged.bed', name='Operon merged intervals')
        ET.SubElement(resources, 'Resource', path='values.bedgraph', name='Source intervals per merged region')
        ET.indent(session)
        ET.ElementTree(session).write(handoff / 'session.xml', encoding='UTF-8', xml_declaration=True)
        # Batch uses absolute paths only at this explicitly local launch boundary.
        def quote(path):
            return '"' + path.as_posix() + '"'
        snapshot = handoff / 'snapshots'; snapshot.mkdir()
        # IGV's batch runner skips its default (network) genome initialization
        # when the first command explicitly selects our local reference.
        batch = '\n'.join(['genome ' + quote(handoff / 'synthetic.fa'), 'load ' + quote(handoff / 'session.xml'),
                           'goto chrTest1:1-3000', 'snapshotDirectory ' + quote(snapshot),
                           'snapshot chrTest1.png', 'goto chrTest2:1-3000', 'snapshot chrTest2.png',
                           'goto chrTest1:1-3000', ''])
        (handoff / 'load-and-snapshot.bat.txt').write_text(batch, encoding='utf-8', newline='\n')
        evidence = {'status': 'computation-and-native-files-passed', 'igv_visual_status': 'pending',
                    'job_id': key, 'workflow_id': saved['id'], 'artifact_id': retained['artifact_id'],
                    'worker_python': sys.executable, 'protocol_version': 3,
                    'assembly': provenance['assembly'], 'coordinate_system': provenance['coordinate_system'],
                    'input_intervals': len(INTERVALS), 'output_intervals': len(actual), 'expected': EXPECTED,
                    'memory': parameters['memory'], 'allocation': job['allocation'],
                    'generation': index['provenance']['operator_generation'], 'canvas_sessions': 0,
                    'job_parameter_file': str(data / 'jobs' / key / 'parameters.json'),
                    'artifacts': {p.name: {'sha256': digest(p), 'bytes': p.stat().st_size}
                                  for p in handoff.iterdir() if p.is_file()},
                    'handoff': str(handoff), 'native_files_via_authenticated_api': True}
        dump(root / 'evidence.json', evidence)
        print(json.dumps({'evidence': str(root / 'evidence.json'), 'handoff': str(handoff), 'job_id': key}))
    finally:
        client.close()
        if not existed:
            cli('service', 'stop')


if __name__ == '__main__':
    main()
