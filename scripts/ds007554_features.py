"""ds007554: per-10-s-bin features for every file.

Clocks: EEG + events on the EEG clock (declared). ECG/button on the Delsys clock. For files whose
push-button/target event matching passed the frozen acceptance rule, ECG and behavior are placed on the
EEG clock with the inferred offset (clock_source='event_matched'); for all other files ECG is binned on
the Delsys clock with the *nominal* segment boundaries (clock_source='declared_unverified') and is used
only for file-level summaries. Segments on the EEG clock: rest 0-25 s (first 5 s discarded), task 25-205 s,
post 205-216 s. Outputs data/features/ds007554_bins.parquet and results/audit/ds007554_eeg_qc.csv.
"""
import sys, os, json, time
sys.path.insert(0, "src")
import numpy as np, pandas as pd
from myndos.io_ds007554 import index_files, load_eeg, load_events, load_physio, button_onsets, BUTTON_TASKS
from myndos.signal import detect_r_peaks, rr_quality, beat_features, eeg_preprocess, eeg_bin_features, channel_groups
from myndos.binning import make_bins

BIN = 10.0; REST = (0.0, 25.0); TASK = (25.0, 205.0); POST = (205.0, 216.0)
idx = index_files()
align = pd.read_csv("results/audit/ds007554_button_alignment.csv")
acc = {(r.sub, r.ses, r.task): r.best_shift_s for r in align.itertuples() if r.accepted}
rows, qc = [], []
t0 = time.time()
for i, r in enumerate(idx.itertuples()):
    d = load_eeg(r.eeg); fs = d["fs"]
    eeg = eeg_preprocess(d["eeg"], fs, notch=50.0); groups = channel_groups(d["eeg_names"])
    dur = min(d["duration_s"], POST[1])
    segs = [(REST[0], REST[1], "rest"), (TASK[0], TASK[1], "task"), (POST[0], dur, "post")]
    bins = pd.concat([make_bins([segs[0]], BIN, margin_start=5.0), make_bins(segs[1:], BIN)], ignore_index=True)
    ev = load_events(r.events) if r.events_exists else None
    key = (r.sub, r.ses, r.task); shift = acc.get(key, np.nan); matched = key in acc
    # ECG on its own (Delsys) clock; converted to EEG clock when matched: t_eeg = t_delsys - shift
    have_ecg = r.ecg_exists
    if have_ecg:
        ecg, efs, _ = load_physio(r.ecg)
        peaks = detect_r_peaks(ecg, efs); rt, rr, valid = rr_quality(peaks, efs)
        if matched:
            rt = rt - shift
        whole = beat_features(rt, rr, valid, 0, len(ecg) / efs)
    else:
        rt = rr = valid = np.array([]); whole = {"n_beats": 0, "n_valid": 0, "coverage": np.nan, "hr": np.nan, "rmssd": np.nan}
    # behaviour (button tasks with accepted alignment): presses on EEG clock
    press = None
    if matched and r.button_exists and ev is not None:
        sig, bfs, _ = load_physio(r.button); press = button_onsets(sig, bfs) - shift
        tg = ev[ev.trial_type == "target"].onset.values; nt = ev[ev.trial_type == "trigger"].onset.values
    n_ok = 0
    for _, b in bins.iterrows():
        e = eeg_bin_features(eeg, fs, d["eeg_names"], b.t_start, b.t_end, groups); n_ok += e["eeg_ok"]
        row = {"pid": r.sub, "ses": r.ses, "task": r.task, "file": f"{r.sub}_{r.ses}_{r.task}", "condition": b.condition,
               "t_start": b.t_start, "t_end": b.t_end, "elapsed": b.elapsed, "clock_source": "event_matched" if matched else "declared_unverified",
               "delsys_shift_s": shift, **e}
        if have_ecg:
            f = beat_features(rt, rr, valid, b.t_start, b.t_end)
            f30 = beat_features(rt, rr, valid, b.t_end - 30.0, b.t_end)
            row.update({"hr": f["hr"] if f["hr_valid"] else np.nan, "n_valid_rr": f["n_valid"], "beat_coverage": f["coverage"],
                        "rmssd30": f30["rmssd"] if f30["hrv_valid"] else np.nan})
        else:
            row.update({"hr": np.nan, "n_valid_rr": 0, "beat_coverage": np.nan, "rmssd30": np.nan})
        if press is not None:
            tm = (tg >= b.t_start) & (tg < b.t_end); nm = (nt >= b.t_start) & (nt < b.t_end)
            hits, rts = 0, []
            for o in tg[tm]:
                p = press[(press >= o) & (press < o + 1.5)]
                if p.size: hits += 1; rts.append(p[0] - o)
            pm = (press >= b.t_start) & (press < b.t_end)
            fa = sum(1 for p in press[pm] if not np.any((p - tg >= 0) & (p - tg < 1.5)))
            n_ev = int(tm.sum() + nm.sum())
            row.update({"n_targets": int(tm.sum()), "n_events": n_ev, "hits": hits, "misses": int(tm.sum()) - hits, "false_alarms": fa,
                        "error_rate": ((int(tm.sum()) - hits) + fa) / n_ev if n_ev > 0 else np.nan,
                        "rt_mean": float(np.mean(rts)) if rts else np.nan})
        rows.append(row)
    qc.append({"sub": r.sub, "ses": r.ses, "task": r.task, "eeg_fs": fs, "n_bins": len(bins), "eeg_ok_bins": n_ok,
               "eeg_std_uV_median": float(np.median(np.std(eeg, axis=1))), "ecg_beats": whole["n_beats"], "ecg_coverage": whole["coverage"],
               "hr_file": whole["hr"], "rmssd_file": whole["rmssd"], "clock_source": "event_matched" if matched else "declared_unverified"})
    if i % 50 == 0: print(i, len(idx), f"{time.time()-t0:.0f}s", flush=True)
df = pd.DataFrame(rows); df.to_parquet("data/features/ds007554_bins.parquet")
Q = pd.DataFrame(qc); Q.to_csv("results/audit/ds007554_eeg_qc.csv", index=False)
print(df.shape, "eeg_ok frac", df.eeg_ok.mean(), "hr valid frac", df.hr.notna().mean())
print(Q.groupby("task")[["eeg_ok_bins", "ecg_coverage", "hr_file"]].median())
