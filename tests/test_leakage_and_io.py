import numpy as np
import pandas as pd
from myndos.io_matb import read_e4_regular, read_e4_ibi, read_e4_tags, stream_combined_csv_rows, expected_matb_segments
from myndos.modeling import make_targets, participant_folds


def test_e4_parsers(tmp_path):
    p = tmp_path / "EDA.csv"; p.write_text("1700000000.000000\n4.000000\n0.1\n0.2\n0.3\n0.4\n")
    t, v, t0, fs = read_e4_regular(str(p))
    assert fs == 4 and t0 == 1700000000 and np.allclose(t - t0, [0, .25, .5, .75]) and v[-1] == 0.4
    q = tmp_path / "IBI.csv"; q.write_text("1700000000.000000, IBI\n1.5,0.8\n2.3,0.81\n")
    tt, ibi, t0 = read_e4_ibi(str(q))
    assert np.allclose(tt - t0, [1.5, 2.3]) and np.allclose(ibi, [0.8, 0.81])
    g = tmp_path / "tags.csv"; g.write_text("1700000060.12\n1700000420.5\n")
    assert read_e4_tags(str(g)).size == 2
    c = tmp_path / "p.csv"; c.write_text("0,0.004,0.008\n1,2,3\n4,5,6\n")
    rows = stream_combined_csv_rows(str(c), [1, 3])
    assert np.allclose(rows[1], [0, .004, .008]) and np.allclose(rows[3], [4, 5, 6]) and 2 not in rows
    segs = expected_matb_segments(100.0)
    assert segs[1] == (460.0, 820.0, "challenge_1") and segs[-1][2] == "recovery_2"


def test_targets_are_strictly_future_and_within_condition():
    # 10-s bins, one condition; horizon 30 s target must use only bins ending at/after t+30
    df = pd.DataFrame({"pid": ["a"] * 8, "file": ["f"] * 8, "condition": ["task"] * 8,
                       "t_end": np.arange(10, 90, 10.0), "err": np.arange(8, dtype=float)})
    tg = make_targets(df, horizon=30.0, value_col="err")
    # for row with t_end=10, target = mean err over bins with t_end in (10, 40] -> rows 1,2,3 -> mean 2
    assert tg.loc[0] == 2.0
    # last rows lack a full horizon -> NaN
    assert np.isnan(tg.iloc[-1]) and np.isnan(tg.iloc[-3])
    df2 = df.copy(); df2.loc[4:, "condition"] = "rest"
    tg2 = make_targets(df2, horizon=30.0, value_col="err")
    assert np.isnan(tg2.loc[3]) and np.isnan(tg2.loc[2])  # horizon would cross the condition boundary


def test_participant_folds_disjoint():
    pids = np.array(["a"] * 5 + ["b"] * 5 + ["c"] * 5 + ["d"] * 5)
    for tr, te in participant_folds(pids, n_splits=4, seed=0):
        assert set(pids[tr]).isdisjoint(set(pids[te]))
