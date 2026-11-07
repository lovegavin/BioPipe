"""Coordinates and file identity for the optional genome-browser SDK example."""
from pathlib import Path
import hashlib
import importlib.util

import numpy as np
import pytest

from operon_sdk import Form

SOURCE = Path(__file__).resolve().parents[1] / 'examples/igv_handoff/operon_igv_example/tracks.py'
spec = importlib.util.spec_from_file_location('igv_example_under_test', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def merged(data, chroms):
    return Form(np.asarray(data, dtype=np.float64), ['merged_region', 'statistic'],
                {'merged_region': {str(i): i for i in range(len(data))},
                 'statistic': {'start': 0, 'end': 1, 'length': 2, 'n_intervals': 3}},
                {'representation': 'merged_intervals', 'chrom': chroms, 'missing_code': float('nan')},
                {'merged_region': ['chrom']})


def test_exact_coordinates_chromosomes_and_artifact_hashes(tmp_path):
    form = merged([[16777217, 16777219, 2, 3], [30, 60, 30, 2]], ['chrA', 'chrB'])
    before = form.data.copy()
    paths, metadata = module.write_tracks(form, tmp_path / 'tracks', assembly='test-assembly')
    assert paths['bed'].read_text() == 'chrA\t16777217\t16777219\tmerged_1\nchrB\t30\t60\tmerged_2\n'
    assert paths['bedgraph'].read_text() == 'chrA\t16777217\t16777219\t3\nchrB\t30\t60\t2\n'
    assert metadata['chromosomes'] == ['chrA', 'chrB']
    assert metadata['coordinate_system'] == '0-based-half-open'
    for role in ('bed', 'bedgraph'):
        assert hashlib.sha256(paths[role].read_bytes()).hexdigest() == metadata['files'][role]['sha256']
    np.testing.assert_array_equal(form.data, before)


@pytest.mark.parametrize('data,chroms,match', [
    ([[.5, 20, 19.5, 1]], ['chr1'], 'exact integers'),
    ([[10, 20, 10, 1], [19, 25, 6, 1]], ['chr1', 'chr1'], 'non-overlapping'),
    ([[10, 20, 10, float('nan')]], ['chr1'], 'finite signal'),
    ([[10, 20, 10, 1]], ['chr1\tchr2'], 'track-safe'),
])
def test_invalid_tracks_are_rejected_without_partial_files(tmp_path, data, chroms, match):
    target = tmp_path / 'tracks'
    with pytest.raises(ValueError, match=match):
        module.write_tracks(merged(data, chroms), target, assembly='test-assembly')
    assert not target.exists()


def test_chromosome_identity_cannot_be_guessed(tmp_path):
    form = merged([[10, 20, 10, 1]], ['chr1'])
    form.axis_info = {}
    with pytest.raises(ValueError, match='chromosome axis metadata'):
        module.write_tracks(form, tmp_path / 'tracks', assembly='test-assembly')


def test_cancellation_does_not_register_partial_output(tmp_path):
    def cancelled():
        raise RuntimeError('cancelled')
    with pytest.raises(RuntimeError, match='cancelled'):
        module.write_tracks(merged([[10, 20, 10, 1]], ['chr1']), tmp_path / 'tracks',
                            assembly='test-assembly', checkpoint=cancelled)
    assert not (tmp_path / 'tracks').exists()
