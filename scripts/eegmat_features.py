"""EEGMAT: per-file audit + per-10-s-bin features (HR, RMSSD on 30-s windows, EEG log band power).

Baseline (_1) and task (_2) are separate recordings: bins are computed within each file and
NEVER concatenated into a continuous experiment. Outputs data/features/eegmat_bins.parquet and
results/audit/eegmat_qc.csv.
"""
import sys, os, json
sys.path.insert(0, "src")
import numpy as np, pandas as pd
from myndos.io_eegmat import subjects, load_edf, ROOT
from myndos.signal import detect_r_peaks, rr_quality, beat_features, eeg_preprocess, eeg_bin_features, channel_groups
from myndos.binning import make_bins

BIN = 10.0
rows, qc = [], []
for sid in subjects():
    for tag, cond in (("1", "baseline"), ("2", "task")):
        path = f"{ROOT}/{sid}_{tag}.edf"
        d = load_edf(path)
        fs = d["fs"]; ecg = d["ecg"]; eeg = eeg_preprocess(d["eeg"], fs, notch=50.0)
        groups = channel_groups(d["eeg_names"])
        peaks = detect_r_peaks(ecg, fs)
        rt, rr, valid = rr_quality(peaks, fs)
        whole = beat_features(rt, rr, valid, 0, d["duration_s"], min_valid_hrv=20)
        # ECG amplitude sanity: R-peak amplitude relative to noise
        bp_amp = float(np.median(np.abs(ecg[peaks]))) if peaks.size else np.nan
        qc.append({"subject": sid, "file": os.path.basename(path), "condition": cond, "fs": fs,
                   "duration_s": d["duration_s"], "eeg_units": d["eeg_units"], "ecg_units": d["ecg_units"],
                   "n_beats": whole["n_beats"], "n_valid_rr": whole["n_valid"], "beat_coverage": whole["coverage"],
                   "hr_whole": whole["hr"], "rmssd_whole": whole["rmssd"], "r_amp_mV": bp_amp,
                   "ecg_std_mV": float(np.std(ecg)), "eeg_std_uV_median": float(np.median(np.std(eeg, axis=1)))})
        bins = make_bins([(0.0, d["duration_s"], cond)], width=BIN)
        for _, b in bins.iterrows():
            f = beat_features(rt, rr, valid, b.t_start, b.t_end)
            # RMSSD on a trailing 30-s window ending at this bin (within file)
            f30 = beat_features(rt, rr, valid, max(0.0, b.t_end - 30.0), b.t_end) if b.t_end >= 30 else {"rmssd": np.nan, "hrv_valid": False}
            e = eeg_bin_features(eeg, fs, d["eeg_names"], b.t_start, b.t_end, groups)
            rows.append({"pid": sid, "file": os.path.basename(path), "condition": cond, "t_start": b.t_start,
                         "t_end": b.t_end, "elapsed": b.elapsed, "hr": f["hr"], "hr_valid": f["hr_valid"],
                         "n_valid_rr": f["n_valid"], "beat_coverage": f["coverage"], "rmssd30": f30["rmssd"],
                         "hrv_valid": f30["hrv_valid"], **e})
df = pd.DataFrame(rows); df.to_parquet("data/features/eegmat_bins.parquet")
q = pd.DataFrame(qc); q.to_csv("results/audit/eegmat_qc.csv", index=False)
print(df.shape); print(q[["condition", "duration_s", "n_beats", "beat_coverage", "hr_whole", "rmssd_whole", "r_amp_mV"]].groupby("condition").describe().T.to_string())
print("bins eeg_ok frac", df.eeg_ok.mean(), "hr_valid frac", df.hr_valid.mean())
