"""ds007554 descriptives (demand response on the EEG clock), cardiac/behaviour on event-matched files,
within-person association with cognitive-load ratings, and the held-out added-value prediction test.
Frozen parameters: 10-s bins, band +-2 robust units (sens. 1.5/2.5), k=3 bins, session-pooled rest reference.
"""
import sys, json
sys.path.insert(0, "src")
import numpy as np, pandas as pd
from scipy import stats
from myndos.metrics import robust_reference, normalize, first_sustained_departure, burden, response_magnitude
from myndos.modeling import make_targets, nested_ridge_predict, participant_mae, paired_bootstrap, shuffle_physiology_across_participants, temporal_shift_within_person
from myndos.io_ds007554 import phenotype, LOAD_COLS, TASK_DEMAND_RANK

SEED = 0
df = pd.read_parquet("data/features/ds007554_bins.parquet")
part, load, kss = phenotype()
eeg_cols = [c for c in df.columns if c.startswith("eeg_") and c not in ("eeg_ok", "eeg_bad_ch_frac")]
key_feats = ["eeg_frontal_theta", "eeg_parietal_alpha", "eeg_occipital_alpha", "eeg_central_beta"]
df.loc[~df.eeg_ok, eeg_cols] = np.nan
matched = df.clock_source == "event_matched"
out = {"seed": SEED, "n_files": int(df.file.nunique()), "n_participants": int(df.pid.nunique()),
       "n_event_matched_files": int(df[matched].file.nunique()), "n_event_matched_participants": int(df[matched].pid.nunique()),
       "recovery": "NOT ESTIMABLE on ds007554: each file ends ~11 s after the task (one 10-s post bin). No recovery metric is reported.",
       "cross_device_pairing": "ECG/behaviour placed on the EEG clock only for event-matched files (see results/audit/ds007554_button_alignment.csv); all other ECG is file-level only."}

# ---------------- A. Demand response, EEG clock, session-pooled rest reference ------------------
rows = []
for (pid, ses), g in df.groupby(["pid", "ses"]):
    rest = g[g.condition == "rest"]
    refs = {c: robust_reference(rest[c].to_numpy()) for c in key_feats + ["hr"]}
    for f, gf in g.groupby("file"):
        task = gf.task.iloc[0]; t = gf[gf.condition == "task"].sort_values("t_end")
        r = {"pid": pid, "ses": ses, "task": task, "file": f, "demand_rank": TASK_DEMAND_RANK[task],
             "n_rest_bins_session": int(rest[key_feats[0]].notna().sum()), "n_task_bins_valid_eeg": int(t.eeg_ok.sum()),
             "clock_source": gf.clock_source.iloc[0]}
        own_rest = gf[gf.condition == "rest"]
        for c in key_feats + (["hr"] if gf.clock_source.iloc[0] == "event_matched" else []):
            med, sc, flag = refs[c]
            r[f"{c}_resp_phys"] = response_magnitude(t[c].to_numpy(), rest[c].to_numpy())
            r[f"{c}_resp_own_rest_phys"] = response_magnitude(t[c].to_numpy(), own_rest[c].to_numpy())
            z = normalize(t[c].to_numpy(), med, sc); r[f"{c}_scale_flag"] = flag
            r[f"{c}_resp_z"] = float(np.nanmedian(z)) if np.isfinite(z).any() else np.nan
            r[f"{c}_burden"] = burden(z, 10.0)
            for band in (1.5, 2.0, 2.5):
                r[f"{c}_t_depart_b{band}"] = first_sustained_departure(z, t.elapsed.to_numpy(), band=band, k=3)
            r[f"{c}_departed_b2"] = np.isfinite(r[f"{c}_t_depart_b2.0"])
        if gf.clock_source.iloc[0] == "event_matched" and "error_rate" in gf:
            r["error_rate_task"] = float(np.nanmean(t.error_rate)); r["rt_mean_task"] = float(np.nanmean(t.rt_mean))
            r["hits_task"] = float(np.nansum(t.hits)); r["n_targets_task"] = float(np.nansum(t.n_targets))
        # subjective load rating for this task/session
        col = f"sess-{ses[-2:]}_{LOAD_COLS[task]}"
        r["load_rating"] = float(load.loc[load.participant_id == pid, col].iloc[0]) if col in load and (load.participant_id == pid).any() else np.nan
        rows.append(r)
R = pd.DataFrame(rows); R.to_csv("results/tables/ds007554_file_metrics.csv", index=False)

def by_task(col):
    g = R.groupby("task")[col]
    return {t: {"n_files": int(v.notna().sum()), "n_participants": int(R.loc[v.notna().index, "pid"].nunique()) if v.notna().any() else 0,
                "median": float(v.median()), "q25": float(v.quantile(.25)), "q75": float(v.quantile(.75))} for t, v in g}
out["demand_response_by_task"] = {c: by_task(f"{c}_resp_phys") for c in key_feats}
out["demand_response_z_by_task"] = {c: by_task(f"{c}_resp_z") for c in key_feats}
out["departure_fraction_b2_by_task"] = {c: R.groupby("task")[f"{c}_departed_b2"].mean().round(3).to_dict() for c in key_feats}
out["departure_time_b2_median_s"] = {c: R.groupby("task")[f"{c}_t_depart_b2.0"].median().round(1).to_dict() for c in key_feats}
out["scale_flags_near_zero_mad"] = {c: int(R[f"{c}_scale_flag"].sum()) for c in key_feats}
# Cardiac on event-matched files (physical units, own-rest reference; N small)
m = R[R.clock_source == "event_matched"]
out["cardiac_event_matched"] = {"n_files": int(m.hr_resp_own_rest_phys.notna().sum()), "n_participants": int(m.loc[m.hr_resp_own_rest_phys.notna(), "pid"].nunique()),
                                "hr_task_minus_own_rest_bpm": paired_bootstrap(m.groupby("pid").hr_resp_own_rest_phys.mean(), seed=SEED)}
# file-level HR by task for ALL files with ECG (declared clock; file is 84% task time)
Q = pd.read_csv("results/audit/ds007554_eeg_qc.csv")
out["file_level_hr_by_task_all_files"] = Q.groupby("task").hr_file.agg(["count", "median"]).round(2).to_dict("index")
# within-person: does the response track the demand ordering / subjective load across tasks?
assoc = {}
for c in key_feats + ["hr"]:
    col = f"{c}_resp_z" if c != "hr" else "hr_resp_own_rest_phys"
    rhos_load, rhos_rank = [], []
    for pid, g in R.groupby("pid"):
        g = g.dropna(subset=[col])
        if g[col].notna().sum() >= 6:
            gl = g.dropna(subset=["load_rating"])
            if len(gl) >= 6 and gl.load_rating.nunique() > 1: rhos_load.append(stats.spearmanr(gl[col], gl.load_rating).statistic)
            rhos_rank.append(stats.spearmanr(g[col], g.demand_rank).statistic)
    assoc[c] = {"vs_subjective_load": paired_bootstrap(pd.Series(rhos_load), seed=SEED), "vs_declared_demand_rank": paired_bootstrap(pd.Series(rhos_rank), seed=SEED)}
out["within_person_spearman_response_vs_load"] = assoc

# ---------------- B. Held-out added-value prediction test (event-matched button files) -----------------
P = df[matched & (df.condition == "task")].copy().sort_values(["pid", "file", "t_end"])
P["error_rate"] = P["error_rate"].astype(float)
P["y"] = make_targets(P, horizon=30.0, value_col="error_rate")
g = P.groupby("file", sort=False)
P["perf_last30"] = g.error_rate.transform(lambda s: s.rolling(3, min_periods=1).mean())
P["perf_cum"] = g.error_rate.transform(lambda s: s.expanding().mean())
P["perf_slope"] = g.error_rate.transform(lambda s: s.rolling(6, min_periods=3).apply(lambda v: np.polyfit(np.arange(len(v)), v, 1)[0], raw=True))
P["hr_last30"] = g.hr.transform(lambda s: s.rolling(3, min_periods=1).mean())
P["hr_vs_rest"] = P.hr - P.file.map(df[matched & (df.condition == "rest")].groupby("file").hr.median())
for c in eeg_cols: P[f"{c}_m3"] = g[c].transform(lambda s: s.rolling(3, min_periods=1).mean())
P["task_nbackarith"] = (P.task == "nbackarithmetic").astype(float); P["ses_n"] = P.ses.str[-1].astype(float)
ctx = ["task_nbackarith", "ses_n", "elapsed", "perf_last30", "perf_cum", "perf_slope"]
periph = ["hr", "hr_last30", "rmssd30", "hr_vs_rest"]
eegf = eeg_cols + [f"{c}_m3" for c in eeg_cols]
D = P.dropna(subset=["y"]).copy()
n_pid = D.pid.nunique()
pred_out = {"n_rows": int(len(D)), "n_participants": int(n_pid), "n_files": int(D.file.nunique()), "horizon_s": 30, "target": "mean error rate (misses+false alarms per event) over the next 30 s, within task",
            "status": "run" if n_pid >= 20 else f"insufficient-N (n_participants={n_pid} < 20): exploratory only"}
if n_pid >= 8:
    y = D.y.to_numpy(); pids = D.pid.to_numpy()
    def run(cols, data=None, seed=SEED):
        X = (data if data is not None else D)[cols].to_numpy(float)
        return nested_ridge_predict(X, y, pids, n_outer=min(10, n_pid), n_inner=min(5, n_pid - 2), seed=seed)
    preds = {"persistence": D.perf_last30.to_numpy(), "condition_time_only": run(["task_nbackarith", "ses_n", "elapsed"]),
             "context_past_performance": run(ctx), "context_plus_peripheral": run(ctx + periph), "context_plus_peripheral_plus_eeg": run(ctx + periph + eegf)}
    S = shuffle_physiology_across_participants(D.assign(elapsed_bin=(D.elapsed // 30).astype(int)), periph + eegf, ["task", "elapsed_bin"], seed=SEED)
    preds["control_mismatched_physiology"] = run(ctx + periph + eegf, S)
    T = temporal_shift_within_person(D, periph + eegf, shift_bins=3)
    preds["control_temporal_shift_3bins"] = run(ctx + periph + eegf, T)
    maes = {k: participant_mae(y, v, pids) for k, v in preds.items()}
    ref = maes["context_past_performance"]
    pred_out["participant_weighted_mae"] = {k: {"mean": float(v.mean()), "sd": float(v.std())} for k, v in maes.items()}
    pred_out["paired_difference_vs_context_past_performance"] = {k: paired_bootstrap(v - ref, seed=SEED) for k, v in maes.items() if k != "context_past_performance"}
    pred_out["paired_difference_eeg_vs_peripheral"] = paired_bootstrap(maes["context_plus_peripheral_plus_eeg"] - maes["context_plus_peripheral"], seed=SEED)
    pred_out["target_sd"] = float(np.std(y)); pred_out["target_mean"] = float(np.mean(y))
    pd.DataFrame(maes).to_csv("results/tables/ds007554_prediction_participant_mae.csv")
out["prediction"] = pred_out
json.dump(out, open("results/tables/ds007554_summary.json", "w"), indent=2, default=float)
print(json.dumps({k: out[k] for k in ["n_files", "n_participants", "n_event_matched_files", "n_event_matched_participants", "scale_flags_near_zero_mad", "cardiac_event_matched", "file_level_hr_by_task_all_files"]}, indent=1, default=float))
print("demand response (physical) by task:"); print(pd.DataFrame({c: {t: v["median"] for t, v in out["demand_response_by_task"][c].items()} for c in key_feats}).round(3))
print("departure fraction b2:"); print(pd.DataFrame(out["departure_fraction_b2_by_task"]))
print("within-person rho:"); print(json.dumps(assoc, indent=1, default=float))
print("prediction:"); print(json.dumps(pred_out, indent=1, default=float))
