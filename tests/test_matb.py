"""MATB-II / E4 primary-dataset software tests (synthetic fixtures; never evidence)."""
import numpy as np
import pandas as pd
from myndos.io_matb import read_matb_resman, parse_elapsed, matb_cadence_anomalies, expected_matb_segments, MATB_TARGET_LEVEL
from myndos.binning import make_bins
from myndos.metrics import robust_reference, normalize, recovery, first_sustained_departure


def test_resman_parser_bom_and_elapsed(tmp_path):
    p = tmp_path / "p99resman.csv"
    p.write_text("﻿ELAPSED_TIME,TANK_A,TANK_B,TANK_C,TANK_D,DIFF_A,DIFF_B\n00:10.0,2456,2396,1010,1000,-44,-104\n00:20.1,2600,2500,1,1,100,0\n01:00.0,2500,2400,1,1,0,-100\n")
    d = read_matb_resman(str(p))
    assert list(d.t_task_s) == [10.0, 20.1, 60.0]
    assert d.diff_consistent.all() and MATB_TARGET_LEVEL == 2500
    assert list(d.abs_err) == [74.0, 50.0, 50.0]
    assert parse_elapsed("01:02:03.5") == 3723.5
    anom = matb_cadence_anomalies(d.t_task_s.to_numpy())
    assert anom.tolist() == [2]  # 20.1 -> 60.0 is a 39.9-s gap


def test_resman_diff_inconsistency_is_flagged(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("ELAPSED_TIME,TANK_A,TANK_B,TANK_C,TANK_D,DIFF_A,DIFF_B\n00:10.0,2456,2396,1,1,-44,-999\n")
    assert not read_matb_resman(str(p)).diff_consistent.iloc[0]


def test_tag_anchors_blocks_and_bins_never_cross_boundaries():
    tag = 1_700_000_061.62
    segs = expected_matb_segments(tag, 360.0)
    bins = make_bins(segs, width=10.0)
    assert len(bins) == 5 * 36
    # every bin lies inside exactly one block, and the bin ending at task time 360 belongs to the baseline
    for b in bins.itertuples():
        s, e, lab = segs[b.seg_index]
        assert s - 1e-9 <= b.t_start and b.t_end <= e + 1e-9 and b.condition == lab
    r = bins[np.isclose(bins.t_end - tag, 360.0)]
    assert len(r) == 1 and r.condition.iloc[0] == "working_baseline"
    r = bins[np.isclose(bins.t_end - tag, 370.0)]
    assert r.condition.iloc[0] == "challenge_1" and np.isclose(r.elapsed.iloc[0], 10.0)
    # MATB snapshot at elapsed 370 maps to the same bin end (task clock == tag clock)
    assert np.isclose(tag + 370.0, r.t_end.iloc[0])


def test_recovery_censoring_and_not_estimable():
    t = np.arange(10, 370, 10.0)
    z = np.full(t.size, 3.0)  # never returns
    r = recovery(z, t, band=2.0, k=3, excursion=True)
    assert r["status"] == "censored" and np.isnan(r["return_time"]) and r["residual_60"] == 3.0
    r = recovery(z, t, band=2.0, k=3, excursion=False)
    assert r["status"] == "not_estimable"
    z = np.array([3, 3, 1, 1, np.nan, 1, 1, 1] + [0] * 28, float)  # NaN breaks the run
    r = recovery(z, t, band=2.0, k=3, excursion=True)
    assert r["status"] == "returned" and r["return_time"] == 80.0


def test_zero_mad_flag_blocks_normalization():
    med, sc, flag = robust_reference(np.ones(18))
    assert flag and np.isnan(sc)
    assert np.isnan(normalize(np.array([1.0, 5.0]), med, sc)).all()
    assert np.isnan(first_sustained_departure(normalize(np.array([9.0] * 5), med, sc), np.arange(5.0)))


def test_eeg_working_start_from_markers():
    import sys; sys.path.insert(0, "scripts")
    from matb_eeg import find_working_start
    mt = np.array([5.0, 65.0, 425.5, 785.0, 1144.0, 1505.0, 1865.0])  # rest, working start, 4 transitions (+/- few s), end
    i, devs, cands = find_working_start(mt)
    assert i == 1 and np.allclose(devs, [0.5, 0.0, -1.0, 0.0]) and cands[0][0] == 1 and len(cands) >= 2  # later transitions also chain; earliest wins
    # a missing transition marker makes the anchor ambiguous (no candidate)
    i2, d2, c2 = find_working_start(np.array([5.0, 65.0, 425.0, 1145.0, 1505.0]))
    assert i2 is None and len(c2) == 0


def test_combined_csv_row_streaming_skips_unwanted_rows(tmp_path):
    from myndos.io_matb import stream_combined_csv_rows, COMBINED_ROWS
    p = tmp_path / "c.csv"; p.write_text("\n".join(",".join(str(r * 10 + k) for k in range(4)) for r in range(80)) + "\n")
    rows = stream_combined_csv_rows(str(p), [COMBINED_ROWS["time"], COMBINED_ROWS["marker"]])
    assert set(rows) == {1, 74} and rows[74][0] == 730 and rows[1][3] == 3
    assert COMBINED_ROWS["eeg"] == list(range(34, 66)) and len(COMBINED_ROWS["eeg"]) == 32
