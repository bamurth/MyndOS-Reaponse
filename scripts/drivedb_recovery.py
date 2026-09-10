"""External transfer test (physiology only): ECG-derived HR and hand-GSR recovery in the final rest of PhysioNet drivedb 1.0.0
(Healey & Picard). Frozen endpoint (REPLICATION_AND_ROADMAP.md, written before this script was run):
reference = minutes 5-15 of the recording (the protocol starts every drive with a 15-min rest); challenge = the last 15 min of
driving before the final-rest marker; recovery = the final rest (up to 15 min). HR from ECG R-peaks (myndos.signal, beat-quality
screened), hand GSR median per 10-s bin; band +-2 robust units, k = 3, right-censoring. Eligible record = has a marker in its
last 20 min that is followed by >= 10 min of recording (the final rest) and at least 20 min of recording before that marker.
Outputs results/tables/drivedb_recovery.csv, results/tables/drivedb_recovery.json, results/figures/figX1_drivedb_recovery.png
"""
import json, numpy as np, pandas as pd, wfdb
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import sys; sys.path.insert(0, "src")
from myndos.signal import detect_r_peaks, rr_quality, beat_features
from myndos.metrics import robust_reference, normalize, first_sustained_departure, recovery, burden

BIN = 10.0
def markers(rec):
    if "marker" not in rec.sig_name: return np.array([])
    i = rec.sig_name.index("marker"); m = np.asarray(rec.e_p_signal[i], float); fs = rec.fs * rec.samps_per_frame[i]
    dev = m - np.median(m); on = np.abs(dev) > 0.5 * np.max(np.abs(dev)); e = np.flatnonzero(np.diff(on.astype(int)) == 1) / fs
    return e[np.concatenate([[True], np.diff(e) > 5.0])] if e.size else e

rows, series = [], {}
for r in open("data/raw/drivedb/RECORDS").read().split():
    rec = wfdb.rdrecord(f"data/raw/drivedb/{r}", smooth_frames=False); dur = rec.sig_len / rec.fs; mk = markers(rec)
    late = mk[(mk > dur - 20 * 60) & (dur - mk >= 10 * 60) & (mk >= 20 * 60)]
    if late.size == 0 or "ECG" not in rec.sig_name:
        rows.append({"record": r, "duration_min": dur / 60, "eligible": False, "reason": "no final-rest marker meeting the rule" if "ECG" in rec.sig_name else "no ECG"}); continue
    t_rest = float(late[0]); i = rec.sig_name.index("ECG"); ecg = np.asarray(rec.e_p_signal[i], float); fs_e = rec.fs * rec.samps_per_frame[i]
    pk = detect_r_peaks(ecg, fs_e); rt, rr, ok = rr_quality(pk, fs_e)
    g = None
    if "hand GSR" in rec.sig_name:
        j = rec.sig_name.index("hand GSR"); g = np.asarray(rec.e_p_signal[j], float); fs_g = rec.fs * rec.samps_per_frame[j]; tg = np.arange(g.size) / fs_g
    segs = [(300.0, 900.0, "reference_rest"), (t_rest - 900.0, t_rest, "driving_last15"), (t_rest, min(t_rest + 900.0, dur), "final_rest")]
    bins = []
    for s, e, lab in segs:
        te = s + BIN
        while te <= e + 1e-9:
            f = beat_features(rt, rr, ok, te - BIN, te); hr = f["hr"] if f["hr_valid"] else np.nan
            gs = float(np.nanmedian(g[(tg >= te - BIN) & (tg < te)])) if g is not None else np.nan
            bins.append({"record": r, "condition": lab, "t_end": te, "elapsed": te - s, "hr": hr, "gsr": gs, "beat_cov": f["coverage"]}); te += BIN
    B = pd.DataFrame(bins); series[r] = B
    row = {"record": r, "duration_min": dur / 60, "eligible": True, "final_rest_onset_min": t_rest / 60, "final_rest_len_min": (min(t_rest + 900, dur) - t_rest) / 60,
           "hr_valid_bin_fraction": float(B.hr.notna().mean()), "n_markers": int(mk.size)}
    for feat in ("hr", "gsr"):
        ref = B[B.condition == "reference_rest"][feat]; med, sc, fl = robust_reference(ref.to_numpy())
        if feat == "hr" and np.isfinite(sc): sc = max(sc, 1.0)
        if feat == "gsr" and np.isfinite(sc): sc = max(sc, 0.02)
        ch = B[B.condition == "driving_last15"]; rc = B[B.condition == "final_rest"]
        zc = normalize(ch[feat].to_numpy(), med, sc); zr = normalize(rc[feat].to_numpy(), med, sc)
        td = first_sustained_departure(zc, ch.elapsed.to_numpy(), band=2.0, k=3); rec_ = recovery(zr, rc.elapsed.to_numpy(), band=2.0, k=3, excursion=np.isfinite(td))
        row.update({f"{feat}_ref_median": med, f"{feat}_ref_scale": sc, f"{feat}_scale_flag": fl, f"{feat}_resp": float(np.nanmedian(ch[feat]) - med) if ch[feat].notna().any() else np.nan,
                    f"{feat}_resp_z": float(np.nanmedian(zc)) if np.isfinite(zc).any() else np.nan, f"{feat}_burden_drive": burden(zc, BIN), f"{feat}_t_depart": td,
                    f"{feat}_return_time": rec_["return_time"], f"{feat}_status": rec_["status"], f"{feat}_residual_60": rec_["residual_60"], f"{feat}_residual_180": rec_["residual_180"], f"{feat}_residual_360": rec_["residual_360"],
                    f"{feat}_residual_end": float(zr[np.isfinite(zr)][-1]) if np.isfinite(zr).any() else np.nan})
    rows.append(row)
D = pd.DataFrame(rows); D.to_csv("results/tables/drivedb_recovery.csv", index=False)
E = D[D.eligible == True]
S = {"dataset": "drivedb 1.0.0 (PhysioNet AWS mirror; 37/37 SHA256 OK)", "n_records": int(len(D)), "n_eligible": int(len(E)), "eligible_records": E.record.tolist(),
     "ineligible": D[D.eligible == False][["record", "reason"]].to_dict("records"), "frozen_endpoint": "see docstring / REPLICATION_AND_ROADMAP.md",
     "hr": {"resp_bpm_median": float(E.hr_resp.median()), "resp_bpm_iqr": [float(E.hr_resp.quantile(.25)), float(E.hr_resp.quantile(.75))], "departed": int(np.isfinite(E.hr_t_depart).sum()), "status": E.hr_status.value_counts().to_dict(),
            "return_time_median_s": float(E.loc[E.hr_status == "returned", "hr_return_time"].median()) if (E.hr_status == "returned").any() else np.nan, "residual_360_median_z": float(E.hr_residual_360.median()), "residual_end_median_z": float(E.hr_residual_end.median()), "hr_valid_bin_fraction_median": float(E.hr_valid_bin_fraction.median())},
     "gsr": {"resp_median": float(E.gsr_resp.median()), "departed": int(np.isfinite(E.gsr_t_depart).sum()), "status": E.gsr_status.value_counts().to_dict(), "return_time_median_s": float(E.loc[E.gsr_status == "returned", "gsr_return_time"].median()) if (E.gsr_status == "returned").any() else np.nan, "residual_end_median_z": float(E.gsr_residual_end.median())},
     "interpretation_limits": "no task performance; segment boundaries from a marker channel that is complete in only a minority of records; reference rest = minutes 5-15 by protocol (not marker-verified); transfer-to-another-task evidence for the recovery methodology only"}
json.dump(S, open("results/tables/drivedb_recovery.json", "w"), indent=2, default=float)
fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
for ax, feat, lab in ((axes[0], "hr", "HR from ECG (bpm)"), (axes[1], "gsr", "hand skin conductance (raw units)")):
    for r, B in series.items():
        ref = B[B.condition == "reference_rest"][feat]; med, sc, _ = robust_reference(ref.to_numpy()); sc = max(sc, 1.0 if feat == "hr" else 0.02) if np.isfinite(sc) else np.nan
        w = B[B.condition.isin(["driving_last15", "final_rest"])]; t0 = w[w.condition == "final_rest"].t_end.min() - BIN
        ax.plot(w.t_end - t0, normalize(w[feat].to_numpy(), med, sc), lw=0.9, alpha=0.8, label=r)
    ax.axvspan(-900, 0, color="#f4c7c3", alpha=0.4, lw=0); ax.axhspan(-2, 2, color="#a6d96a", alpha=0.2, lw=0); ax.set_xlabel("seconds from end of driving (final rest starts at 0)"); ax.set_ylabel(f"{lab}, robust units vs initial rest"); ax.legend(fontsize=6, ncol=2)
fig.suptitle(f"drivedb transfer test (N = {len(E)} eligible records): last 15 min of driving -> final rest. Same estimators as the MATB-II analysis; ECG-derived HR.", fontsize=9)
fig.tight_layout(); fig.savefig("results/figures/figX1_drivedb_recovery.png", dpi=150); plt.close(fig)
print(json.dumps(S, indent=1, default=float)); print(E[["record", "final_rest_onset_min", "hr_valid_bin_fraction", "hr_resp", "hr_resp_z", "hr_t_depart", "hr_status", "hr_return_time", "hr_residual_360", "hr_residual_end", "gsr_resp_z", "gsr_status", "gsr_return_time"]].round(2).to_string())
