"""Hand-counted verification for gc_skew_profile.

Runs with: python tasks/gc_skew_demo/test_gc_skew_profile.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core import Form, StepError
from src.task.step.steps.gc_skew_profile import GcSkewProfileStep
from biopipe_sdk.testing import run_operator


_ALPHA_MAP = {"A": 0, "C": 1, "G": 2, "T": 3, "U": 3, "N": 4}


def _make_form(seq):
    codes = [_ALPHA_MAP[c] for c in seq]
    row = np.asarray(codes, dtype=np.float32)
    data = row.reshape(1, -1)
    return Form(
        data=data,
        dims=["sequence", "position"],
        labels={
            "sequence": {"seq0": 0},
            "position": {str(i): i for i in range(len(seq))},
        },
        info={
            "missing_code": np.nan,
            "representation": "sequence_codes",
            "alphabet_map": _ALPHA_MAP,
            "unknown_code": 5,
            "alphabet": "dna",
        },
    )


def _row(out, i):
    return {n: float(out.data[i, j])
            for j, n in enumerate(("start", "end", "gc", "at",
                                   "gc_skew", "cumulative_skew",
                                   "cumulative_gc"))}


def test_hand_counted_five_windows():
    # 20 bp: GGGG CCCC AAAA TTTT GGCC
    # window 4, step 4 -> 5 windows
    # w0: G=4 C=0 -> gc 1.0, skew 1.0, cum 1.0
    # w1: G=0 C=4 -> gc 1.0, skew -1.0, cum 0.0
    # w2: A=4     -> gc 0.0, at 1.0, skew NaN, cum 0.0
    # w3: T=4     -> gc 0.0, at 1.0, skew NaN, cum 0.0
    # w4: G=2 C=2 -> gc 1.0, skew 0.0, cum 0.0
    seq = "GGGGCCCCAAAATTTTGGCC"
    out = run_operator(GcSkewProfileStep, [_make_form(seq)],
                       {"window_size": 4, "step_size": 4})
    assert out.dims == ["window", "statistic"]
    assert out.data.shape == (5, 7)
    assert out.labels["statistic"] == {
        "start": 0, "end": 1, "gc": 2, "at": 3,
        "gc_skew": 4, "cumulative_skew": 5, "cumulative_gc": 6,
    }
    assert out.info["window_size"] == 4
    assert out.info["step_size"] == 4
    assert out.info["sequence_length"] == 20
    assert out.info["representation"] == "gc_skew_profile"

    r0 = _row(out, 0)
    assert r0["start"] == 0.0 and r0["end"] == 4.0
    assert r0["gc"] == 1.0 and r0["at"] == 0.0
    assert r0["gc_skew"] == 1.0
    assert r0["cumulative_skew"] == 1.0
    assert r0["cumulative_gc"] == 4.0

    r1 = _row(out, 1)
    assert r1["start"] == 4.0 and r1["end"] == 8.0
    assert r1["gc"] == 1.0 and r1["at"] == 0.0
    assert r1["gc_skew"] == -1.0
    assert r1["cumulative_skew"] == 0.0
    assert r1["cumulative_gc"] == 0.0

    r2 = _row(out, 2)
    assert r2["gc"] == 0.0 and r2["at"] == 1.0
    assert np.isnan(r2["gc_skew"])
    assert r2["cumulative_skew"] == 0.0

    r3 = _row(out, 3)
    assert r3["gc"] == 0.0 and r3["at"] == 1.0
    assert np.isnan(r3["gc_skew"])
    assert r3["cumulative_skew"] == 0.0

    r4 = _row(out, 4)
    assert r4["start"] == 16.0 and r4["end"] == 20.0
    assert r4["gc"] == 1.0
    assert r4["gc_skew"] == 0.0
    assert r4["cumulative_skew"] == 0.0

    print("  hand-counted five windows      ok")


def test_last_window_shorter_when_length_not_multiple():
    # length 10, window 4, step 4 -> windows [0,4), [4,8), [8,10)
    seq = "GGGGCCCCAA"
    out = run_operator(GcSkewProfileStep, [_make_form(seq)],
                       {"window_size": 4, "step_size": 4})
    assert out.data.shape == (3, 7)
    r2 = _row(out, 2)
    assert r2["start"] == 8.0
    assert r2["end"] == 10.0
    print("  short last window              ok")


def test_step_smaller_than_window_overlapping():
    # 8 bp, window 4, step 2 -> windows at 0, 2, 4  (6 is >= 8-4+... )
    # starts 0, 2, 4, 6 -> last start 6 end 8 is fine, but start 6
    # window is [6,8) length 2. Because 6 < 8 we emit it.
    seq = "GGGGAAAA"
    out = run_operator(GcSkewProfileStep, [_make_form(seq)],
                       {"window_size": 4, "step_size": 2})
    starts = [float(out.data[i, 0]) for i in range(out.data.shape[0])]
    assert starts == [0.0, 2.0, 4.0, 6.0]
    print("  overlapping windows             ok")


def test_n_and_padding_ignored():
    # length 10, window 5. Sequence with one N in each window.
    # w0: GGGGN -> G=4 valid 4, gc 1.0
    # w1: AAAAN -> A=4 valid 4, at 1.0
    seq = "GGGGNAAAAN"
    out = run_operator(GcSkewProfileStep, [_make_form(seq)],
                       {"window_size": 5, "step_size": 5})
    r0 = _row(out, 0)
    assert r0["gc"] == 1.0
    assert r0["at"] == 0.0
    r1 = _row(out, 1)
    assert r1["gc"] == 0.0
    assert r1["at"] == 1.0
    print("  N ignored in composition        ok")


def test_window_larger_than_sequence_rejected():
    seq = "ACGT"
    try:
        run_operator(GcSkewProfileStep, [_make_form(seq)],
                     {"window_size": 100})
        raise AssertionError("expected window-too-large rejection")
    except AssertionError:
        raise
    except StepError as exc:
        assert "shorter than window_size" in str(exc)
    print("  window > sequence rejected     ok")


def test_multiple_sequences_rejected():
    row = np.asarray([_ALPHA_MAP[c] for c in "ACGTACGT"], dtype=np.float32)
    data = np.stack([row, row], axis=0)
    form = Form(
        data=data,
        dims=["sequence", "position"],
        labels={
            "sequence": {"a": 0, "b": 1},
            "position": {str(i): i for i in range(8)},
        },
        info={
            "missing_code": np.nan,
            "representation": "sequence_codes",
            "alphabet_map": _ALPHA_MAP,
            "unknown_code": 5,
            "alphabet": "dna",
        },
    )
    try:
        run_operator(GcSkewProfileStep, [form], {"window_size": 4})
        raise AssertionError("expected multi-sequence rejection")
    except AssertionError:
        raise
    except StepError as exc:
        assert "exactly one sequence" in str(exc)
    print("  multiple sequences rejected    ok")


def test_wrong_representation_rejected():
    form = _make_form("ACGTACGT")
    form.info["representation"] = "hard_call"
    try:
        run_operator(GcSkewProfileStep, [form], {"window_size": 4})
        raise AssertionError("expected representation rejection")
    except AssertionError:
        raise
    except StepError as exc:
        msg = str(exc).lower()
        assert "sequence_codes" in msg or "representation" in msg
    print("  wrong representation rejected  ok")


def test_protein_alphabet_rejected():
    form = _make_form("ACGTACGT")
    form.info["alphabet"] = "protein"
    try:
        run_operator(GcSkewProfileStep, [form], {"window_size": 4})
        raise AssertionError("expected alphabet rejection")
    except AssertionError:
        raise
    except StepError as exc:
        assert "dna/rna" in str(exc) or "alphabet" in str(exc)
    print("  protein alphabet rejected      ok")


def test_bad_step_size_rejected():
    form = _make_form("ACGTACGTACGT")
    for bad in (0, -1):
        try:
            run_operator(GcSkewProfileStep, [form],
                         {"window_size": 4, "step_size": bad})
            raise AssertionError("expected step_size rejection")
        except AssertionError:
            raise
        except (StepError, ValueError) as exc:
            # The schema layer (minimum: 1) rejects before the operator
            # body runs and raises ValueError; the body check is only a
            # fallback when the schema is bypassed.
            msg = str(exc)
            assert "step_size" in msg, msg
    print("  bad step_size rejected         ok")


def main():
    print("gc_skew_profile verification")
    test_hand_counted_five_windows()
    test_last_window_shorter_when_length_not_multiple()
    test_step_smaller_than_window_overlapping()
    test_n_and_padding_ignored()
    test_window_larger_than_sequence_rejected()
    test_multiple_sequences_rejected()
    test_wrong_representation_rejected()
    test_protein_alphabet_rejected()
    test_bad_step_size_rejected()
    print()
    print("all checks passed")


if __name__ == "__main__":
    main()
