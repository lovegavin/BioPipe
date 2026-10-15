"""Exercise the portable VCF parser without a native htslib installation."""
import gzip

import numpy as np
import pytest

from src.core import ReaderError
from src.reader.readers import vcf_reader


def write_vcf(tmp_path, records, compressed=False):
    text = ('##fileformat=VCFv4.2\n'
            '#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\tS2\tS3\n'
            + '\n'.join(records) + '\n')
    path = tmp_path / ('input.vcf.gz' if compressed else 'input.vcf')
    path.write_bytes(gzip.compress(text.encode()) if compressed else text.encode())
    return path


@pytest.mark.parametrize('compressed', [False, True])
def test_portable_vcf_missing_multiallelic_and_metadata(tmp_path, monkeypatch, compressed):
    path = write_vcf(tmp_path, [
        '1\t10\tmissing\tA\tG\t.\tPASS\t.\tGT\t.\t.\t.',
        '1\t20\trs1\tA\tG\t.\tPASS\t.\tGT:DP\t0/1:9\t.:0\t1|1:7',
        '2\t30\t.\tA\tC,G\t.\tPASS\t.\tDP:GT\t9:1/2\t0:./.\t7:0/2',
    ], compressed)
    monkeypatch.setattr(vcf_reader, '_read_cyvcf2', vcf_reader._read_pure_python)
    form = vcf_reader.VcfReader().read(path, ['variant', 'sample'], {})
    np.testing.assert_allclose(form.data, [
        [np.nan, np.nan, np.nan], [1, np.nan, 2],
        [1, np.nan, 0], [1, np.nan, 1],
    ])
    assert list(form.labels['variant']) == ['missing', 'rs1', '2:30:C', '2:30:G']
    assert list(form.labels['sample']) == ['S1', 'S2', 'S3']
    assert form.info['ploidy'] == 2
    assert form.info['chrom'] == ['1', '1', '2', '2']
    assert form.info['pos'] == [10, 20, 30, 30]
    assert form.axis_info == {'variant': ['chrom', 'pos']}


@pytest.mark.parametrize('calls,match', [
    ('0/1\t0\t1/1', 'mixed ploidy'),
    ('0/1\t1/2\t1/1', 'allele index'),
    ('0/1\t1/1', 'sample count'),
])
def test_portable_vcf_rejects_invalid_calls(tmp_path, calls, match):
    path = write_vcf(tmp_path, ['1\t10\trs1\tA\tG\t.\tPASS\t.\tGT\t' + calls])
    with pytest.raises(ReaderError, match=match):
        vcf_reader._read_pure_python(path)
