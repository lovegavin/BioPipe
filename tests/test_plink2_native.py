"""Native wheel regression: real binary genotypes, missingness and metadata."""
import numpy as np
import pytest


def test_plink2_native_roundtrip(tmp_path):
    pgenlib = pytest.importorskip('pgenlib')
    from src.reader.readers.plink_reader import Plink2Reader
    directory = tmp_path / '基因型 with spaces'
    directory.mkdir()
    path = directory / 'genotypes.pgen'
    rng = np.random.default_rng(128)
    genotypes = rng.integers(0, 3, size=(13, 67), dtype=np.int8)
    genotypes[0, 3] = -9
    genotypes[5, 1::3] = -9
    with pgenlib.PgenWriter(str(path).encode(), 67, variant_ct=13, nonref_flags=False) as writer:
        for row in genotypes:
            writer.append_biallelic(row)
    path.with_suffix('.psam').write_text('#IID\n' + '\n'.join(f's{i}' for i in range(67)) + '\n')
    path.with_suffix('.pvar').write_text('#CHROM\tPOS\tID\tREF\tALT\n' + ''.join(
        f'1\t{100+i}\tv{i}\tA\tG\n' for i in range(13)))
    result = Plink2Reader().read(path, ['variant', 'sample'], {})
    expected = genotypes.astype(np.float32)
    expected[expected == -9] = np.nan
    np.testing.assert_array_equal(result.data, expected)
    assert result.info['ploidy'] == 2
    assert result.info['pos'] == list(range(100, 113))
    assert result.axis_info == {'variant': ['chrom', 'pos']}
    assert list(result.labels['sample']) == [f's{i}' for i in range(67)]
