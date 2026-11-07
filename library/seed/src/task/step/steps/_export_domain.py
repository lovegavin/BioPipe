"""Semantic exports used by the single public output operator."""
import io
import re
from xml.sax.saxutils import escape, quoteattr

import numpy as np

from biopipe.bytecode import io_path
from src.core import StepError


def axis_values(form, keys):
    if not form.dims or any(k not in form.axis_info.get(form.dims[0], []) for k in keys):
        raise StepError('Export metadata must be explicitly aligned with the first axis in axis_info: ' + ', '.join(keys))
    if any(len(form.info.get(k, [])) != form.data.shape[0] for k in keys):
        raise StepError('Export metadata length differs from the first axis')
    return (form.info[k] for k in keys)


def write_genbank(path, form, params):
    from Bio import SeqIO
    from Bio.Seq import Seq
    from Bio.SeqRecord import SeqRecord
    if 'genbank_records' in form.info:
        records, = axis_values(form, ['genbank_records'])
        with io_path(path).open('w', encoding='utf-8', newline='\n') as stream:
            for text in records:
                record = SeqIO.read(io.StringIO(text), 'genbank')
                if not len(record.seq):
                    raise StepError('GenBank record has no sequence')
                # Original record text preserves compound/fuzzy locations, qualifiers and topology.
                stream.write(text.rstrip() + '\n')
        return {'sequence_source': 'preserved GenBank records', 'annotations': 'preserved'}
    sequences, = axis_values(form, ['sequences'])
    names = sorted(form.labels[form.dims[0]], key=form.labels[form.dims[0]].get)
    def records():
        for name, sequence in zip(names, sequences):
            if not isinstance(sequence, str) or not re.fullmatch('[ACGTRYSWKMBDHVNacgtryswkmbdhvn]+', sequence):
                raise StepError('GenBank DNA export requires nonempty IUPAC nucleotide sequences')
            if not re.fullmatch(r'[^\s]+', str(name)) or len(str(name)) > 64:
                raise StepError('GenBank record identifiers must be nonempty, whitespace-free and at most 64 characters')
            record = SeqRecord(Seq(sequence), id=str(name), name=str(name), description='BioPipe sequence export')
            record.annotations = {'molecule_type': 'DNA', 'topology': params.get('topology', 'linear')}
            yield record
    with io_path(path).open('w', encoding='utf-8', newline='\n') as stream:
        SeqIO.write(records(), stream, 'genbank')
    return {'sequence_source': 'info.sequences', 'annotations': 'not supplied', 'topology': params.get('topology', 'linear')}


def write_track(path, form, params, format):
    if form.info.get('coordinate_system') != '0-based-half-open':
        raise StepError('BED/bedGraph export needs coordinate_system=0-based-half-open')
    chroms, starts, ends = axis_values(form, ['chrom', 'start', 'end'])
    column = params.get('value_column', 0)
    if format == 'bedgraph' and (form.data.ndim != 2 or not 0 <= column < form.data.shape[1]):
        raise StepError('bedGraph value_column is outside the matrix')
    with io_path(path).open('w', encoding='utf-8', newline='\n') as stream:
        for i, (chrom, start, end) in enumerate(zip(chroms, starts, ends)):
            if (not isinstance(chrom, str) or not chrom or any(c.isspace() for c in chrom)
                    or not isinstance(start, (int, np.integer)) or not isinstance(end, (int, np.integer))
                    or start < 0 or end <= start):
                raise StepError('Invalid genomic interval')
            fields = [chrom, str(start), str(end)]
            if format == 'bedgraph':
                value = float(form.data[i, column])
                if not np.isfinite(value):
                    raise StepError('bedGraph cannot encode missing/infinite values; filter explicitly')
                fields.append(str(value))
            stream.write('\t'.join(fields) + '\n')
    return {'coordinate_system': '0-based-half-open', 'assembly': params.get('assembly') or form.info.get('assembly', 'unknown')}


def write_graphml(path, form, params):
    if form.info.get('representation') != 'adjacency' or form.data.ndim != 2 or form.data.shape[0] != form.data.shape[1]:
        raise StepError('GraphML export requires a square matrix with representation=adjacency')
    names = [sorted(form.labels[d], key=form.labels[d].get) for d in form.dims]
    if names[0] != names[1]:
        raise StepError('Adjacency axes must have identical ordered node labels')
    directed = params.get('directed', False)
    with io_path(path).open('w', encoding='utf-8', newline='\n') as stream:
        stream.write('<?xml version="1.0" encoding="UTF-8"?>\n<graphml xmlns="http://graphml.graphdrawing.org/xmlns">\n'
                     '<key id="label" for="node" attr.name="label" attr.type="string"/>\n'
                     '<key id="weight" for="edge" attr.name="weight" attr.type="double"/>\n'
                     '<graph edgedefault=' + quoteattr('directed' if directed else 'undirected') + '>\n')
        for i, name in enumerate(names[0]):
            stream.write(f'<node id="n{i}"><data key="label">{escape(str(name))}</data></node>\n')
        for i, row in enumerate(form.data):
            for j in range(0 if directed else i, len(row)):
                value = float(row[j])
                if not np.isfinite(value) or (not directed and value != form.data[j, i]):
                    raise StepError('GraphML needs finite weights; undirected adjacency must be symmetric')
                if value:
                    stream.write(f'<edge source="n{i}" target="n{j}"><data key="weight">{value}</data></edge>\n')
        stream.write('</graph></graphml>\n')
    return {'directed': directed}


def write_newick(path, form):
    from Bio import Phylo
    text = form.info.get('newick')
    if not isinstance(text, str) or not text.strip().endswith(';'):
        raise StepError('Newick export requires a complete tree in info.newick; a distance matrix is not a tree')
    Phylo.read(io.StringIO(text), 'newick')
    io_path(path).write_bytes((text.strip() + '\n').encode('utf-8'))
    return {'tree_source': 'info.newick'}
