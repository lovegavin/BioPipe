from __future__ import annotations

from pathlib import Path

import pytest

from src.core import FileArtifact, StepError
from src.task.step.steps import _vcf_transform as tx
from src.task.step.steps.vcf_normalize import VcfNormalizeStep
from src.task.step.steps.vcf_merge import VcfMergeStep
from src.task.step.steps.vcf_concat import VcfConcatStep


class Ctx(dict):
    def __init__(self, params, root):
        super().__init__()
        self.step_params = dict(params)
        self._root = Path(root)

    def artifact_path(self, name):
        path = self._root / name
        path.mkdir(parents=True, exist_ok=True)
        return str(path)


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding='utf-8', newline='\n')
    return path


def fasta(path: Path, seq: str, name: str = '22') -> Path:
    return write(path, f'>{name}\n{seq}\n')


HEADER = '##fileformat=VCFv4.2\n##contig=<ID=22,length=1000>\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT'


def vcf_text(records: str, samples=('S1',)) -> str:
    return HEADER + '\t' + '\t'.join(samples) + '\n' + records


def test_trim_alleles_moves_shared_bases():
    pos, ref, alt = tx.trim_alleles(10, 'GATC', 'GAC')
    assert (pos, ref, alt) == (11, 'AT', 'A')


def test_left_align_homopolymer():
    assert tx.left_align(5, 'AA', 'A', 'CAAAAA') == (1, 'CA', 'C')  # matches bcftools norm 1.19


def test_normalize_splits_and_remaps_genotypes(tmp_path):
    ref = fasta(tmp_path / 'ref.fa', 'ACGTACGTACGTACGTACGT')
    source = write(tmp_path / 'in.vcf', vcf_text(
        '22\t5\t.\tAC\tG,T\t50\tPASS\tAC=1;AF=0.5;AN=2\tGT\t1|2\n', samples=('S1', 'S2')))
    ctx = Ctx({'output': 'norm', 'split_multiallelic': True}, tmp_path)
    step = VcfNormalizeStep()
    step.run(ctx, [FileArtifact('vcf', {'x': str(source)}), FileArtifact('fasta', {'r': str(ref)})])
    out = ctx['norm']
    lines = Path(next(iter(out.files.values()))).read_text().splitlines()
    body = [line for line in lines if not line.startswith('#')]
    assert len(body) == 2
    first, second = (line.split('\t') for line in body)
    assert (first[3], first[4]) == ('AC', 'G')
    assert (second[3], second[4]) == ('AC', 'T')
    assert first[-1] == '1|0' and second[-1] == '0|1'


def test_merge_unions_sites_and_samples(tmp_path):
    a = write(tmp_path / 'a.vcf', vcf_text(
        '22\t10\t.\tA\tC\t50\tPASS\t.\tGT\t0|1\n', samples=('S1',)))
    b = write(tmp_path / 'b.vcf', vcf_text(
        '22\t10\t.\tA\tC\t50\tPASS\t.\tGT\t1|1\n'
        '22\t20\t.\tG\tT\t50\tPASS\t.\tGT\t0|1\n', samples=('S2',)))
    ctx = Ctx({'output': 'merged'}, tmp_path)
    VcfMergeStep().run(ctx, [FileArtifact('vcf', {'a': str(a)}), FileArtifact('vcf', {'b': str(b)})])
    body = [line for line in Path(next(iter(ctx['merged'].files.values()))).read_text().splitlines() if not line.startswith('#')]
    assert len(body) == 2
    first = body[0].split('\t')
    assert first[1] == '10' and first[-2:] == ['0|1', '1|1']
    second = body[1].split('\t')
    assert second[1] == '20' and second[-2:] == ['./.', '0|1']


def test_merge_rejects_shared_samples(tmp_path):
    a = write(tmp_path / 'a.vcf', vcf_text('22\t10\t.\tA\tC\t50\tPASS\t.\tGT\t0|1\n', samples=('S1',)))
    b = write(tmp_path / 'b.vcf', vcf_text('22\t10\t.\tA\tC\t50\tPASS\t.\tGT\t0|1\n', samples=('S1',)))
    with pytest.raises(StepError, match='share sample'):
        VcfMergeStep().run(Ctx({'output': 'm'}, tmp_path),
                           [FileArtifact('vcf', {'a': str(a)}), FileArtifact('vcf', {'b': str(b)})])


def test_concat_preserves_order(tmp_path):
    a = write(tmp_path / 'a.vcf', vcf_text('22\t30\t.\tA\tC\t50\tPASS\t.\tGT\t0|1\n', samples=('S1',)))
    b = write(tmp_path / 'b.vcf', vcf_text('22\t10\t.\tG\tT\t50\tPASS\t.\tGT\t1|1\n', samples=('S1',)))
    ctx = Ctx({'output': 'cat'}, tmp_path)
    step = VcfConcatStep()
    step.run(ctx, [FileArtifact('vcf', {'a': str(a)}), FileArtifact('vcf', {'b': str(b)})])
    body = [line for line in Path(next(iter(ctx['cat'].files.values()))).read_text().splitlines() if not line.startswith('#')]
    assert [line.split('\t')[1] for line in body] == ['30', '10']


def test_concat_rejects_different_samples(tmp_path):
    a = write(tmp_path / 'a.vcf', vcf_text('22\t10\t.\tA\tC\t50\tPASS\t.\tGT\t0|1\n', samples=('S1',)))
    b = write(tmp_path / 'b.vcf', vcf_text('22\t20\t.\tG\tT\t50\tPASS\t.\tGT\t0|1\n', samples=('S2',)))
    with pytest.raises(StepError, match='identical samples'):
        VcfConcatStep().run(Ctx({'output': 'c'}, tmp_path),
                            [FileArtifact('vcf', {'a': str(a)}), FileArtifact('vcf', {'b': str(b)})])
