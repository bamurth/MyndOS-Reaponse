"""EEGMAT participant-level before/during metrics, associations with counting performance,
held-out classification, and Figure E1. Baseline and task are separate recordings; the matched
comparison uses the LAST 60 s of the baseline file vs the 60-s task file (sensitivity: full baseline).
"""
import sys, json
sys.path.insert(0, "src")
import numpy as np, pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score
from myndos.io_eegmat import subject_info
from myndos.modeling import participant_folds, paired_bootstrap
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

SEED = 0
df = pd.read_parquet("data/features/eegmat_bins.parquet")
qc = pd.read_csv("results/audit/eegmat_qc.csv")
info = subject_info().rename(columns={"Subject": "pid"})
feat_cols = ["hr", "rmssd30"] + [c for c in df.columns if c.startswith("eeg_") and c not in ("eeg_ok", "eeg_bad_ch_frac")]
# QC exclusion rules (frozen): ECG usable if whole-file beat coverage >= 0.8 in BOTH files; else cardiac NaN
cov = qc.pivot(index="subject", columns="condition", values="beat_coverage")
ecg_ok = (cov["baseline"] >= 0.8) & (cov["task"] >= 0.8)
excl = {"cardiac_excluded_subjects": sorted(cov.index[~ecg_ok].tolist()),
        "rule": "whole-file valid-beat coverage >= 0.8 in both recordings"}
df.loc[df.pid.isin(excl["cardiac_excluded_subjects"]), ["hr", "rmssd30"]] = np.nan
df.loc[~df.hr_valid, "hr"] = np.nan
df.loc[~df.hrv_valid, "rmssd30"] = np.nan

def matched(g, cond, last_s=60.0):
    g = g[g.condition == cond]
    if cond == "baseline":
        g = g[g.t_end > g.t_end.max() - last_s + 1e-9]
    return g

rows = []
for pid, g in df.groupby("pid"):
    r = {"pid": pid}
    b = matched(g, "baseline"); t = matched(g, "task"); bfull = g[g.condition == "baseline"]
    r["n_bins_baseline_last60"] = len(b); r["n_bins_task"] = len(t)
    for c in feat_cols:
        r[f"{c}_baseline"] = np.nanmedian(b[c]) if np.isfinite(b[c]).any() else np.nan
        r[f"{c}_task"] = np.nanmedian(t[c]) if np.isfinite(t[c]).any() else np.nan
        r[f"{c}_delta"] = r[f"{c}_task"] - r[f"{c}_baseline"]
        r[f"{c}_delta_fullbaseline"] = r[f"{c}_task"] - (np.nanmedian(bfull[c]) if np.isfinite(bfull[c]).any() else np.nan)
    rows.append(r)
P = pd.DataFrame(rows).merge(info, on="pid", how="left")
P.to_csv("results/tables/eegmat_participant_metrics.csv", index=False)

summary = {"n_subjects": int(P.pid.nunique()), "exclusions": excl, "paired_deltas": {}, "associations": {}}
for c in feat_cols:
    d = P[f"{c}_delta"].dropna()
    if len(d) < 5: continue
    bs = paired_bootstrap(d, seed=SEED)
    w = stats.wilcoxon(d) if (d != 0).any() else None
    summary["paired_deltas"][c] = {"n": int(len(d)), "median_delta": float(d.median()), "mean_delta": bs["mean"],
                                   "ci95": [bs["ci_low"], bs["ci_high"]], "wilcoxon_p": float(w.pvalue) if w else None,
                                   "frac_positive": float((d > 0).mean()),
                                   "mean_delta_fullbaseline": float(P[f"{c}_delta_fullbaseline"].mean())}
    # association of the change with counting performance (number of subtractions per 4 min)
    m = P[[f"{c}_delta", "Number of subtractions"]].dropna()
    rho = stats.spearmanr(m.iloc[:, 0], m.iloc[:, 1])
    summary["associations"][c] = {"n": int(len(m)), "spearman_rho_vs_subtractions": float(rho.statistic), "p": float(rho.pvalue)}

# Held-out (participant-grouped) classification of baseline vs task from single 10-s bins
def cv_auc(cols, name):
    d = df.dropna(subset=cols, how="all").copy()
    X = d[cols].to_numpy(float); y = (d.condition == "task").astype(int).to_numpy(); pids = d.pid.to_numpy()
    pred = np.full(len(y), np.nan)
    for tr, te in participant_folds(pids, 12, SEED):
        m = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)).fit(X[tr], y[tr])
        pred[te] = m.predict_proba(X[te])[:, 1]
    per = pd.DataFrame({"y": y, "p": pred, "pid": pids}).groupby("pid").apply(lambda g: roc_auc_score(g.y, g.p) if g.y.nunique() == 2 else np.nan, include_groups=False)
    return {"pooled_auc": float(roc_auc_score(y, pred)), "participant_mean_auc": float(per.mean()),
            "participant_auc_ci95": paired_bootstrap(per - 0.5, seed=SEED), "n_bins": int(len(y)), "n_participants": int(len(per))}
eeg_cols = [c for c in feat_cols if c.startswith("eeg_")]
summary["heldout_state_classification_baseline_vs_task"] = {
    "cardiac_only": cv_auc(["hr", "rmssd30"], "cardiac"), "eeg_only": cv_auc(eeg_cols, "eeg"), "cardiac_plus_eeg": cv_auc(["hr", "rmssd30"] + eeg_cols, "both"),
    "note": "single 10-s bins; positive class = arithmetic file; participant-grouped 12-fold; participant AUC CI is a bootstrap over participants of AUC-0.5"}

# Held-out prediction of counting performance from physiological change (exploratory, N=36)
def cv_perf(cols):
    d = P.dropna(subset=["Number of subtractions"]).copy()
    X = d[[f"{c}_delta" for c in cols]].to_numpy(float); y = d["Number of subtractions"].to_numpy(float); pids = d.pid.to_numpy()
    pred = np.full(len(y), np.nan)
    for tr, te in participant_folds(pids, len(pids), SEED):  # leave-one-participant-out
        m = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=10.0)).fit(X[tr], y[tr])
        pred[te] = m.predict(X[te])
    base = np.array([np.mean(np.delete(y, i)) for i in range(len(y))])
    return {"n": int(len(y)), "mae_model": float(np.mean(np.abs(pred - y))), "mae_mean_baseline": float(np.mean(np.abs(base - y))),
            "spearman_pred_vs_true": float(stats.spearmanr(pred, y).statistic)}
summary["heldout_performance_from_physiological_change"] = {"cardiac": cv_perf(["hr", "rmssd30"]), "eeg": cv_perf(eeg_cols),
    "both": cv_perf(["hr", "rmssd30"] + eeg_cols), "note": "leave-one-participant-out ridge (alpha fixed at 10, not tuned); exploratory at N=36"}
json.dump(summary, open("results/tables/eegmat_summary.json", "w"), indent=2, default=float)

# ---- Figure E1: cohort per-bin trajectories, baseline (last 60 s) and task (60 s), physical units
fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
panels = [("hr", "Heart rate (bpm, ECG)"), ("eeg_frontal_theta", "Frontal log10 theta power (uV^2)"), ("eeg_parietal_alpha", "Parietal log10 alpha power (uV^2)")]
for ax, (c, lab) in zip(axes, panels):
    for cond, off, color in (("baseline", -60, "#4c72b0"), ("task", 0, "#c44e52")):
        g = matched(df, cond) if cond == "baseline" else df[df.condition == "task"]
        g = g.copy(); g["rel"] = g.t_end - (g.groupby("pid").t_end.transform("max") if cond == "baseline" else 0) + (0 if cond == "baseline" else 0)
        g["rel"] = (g.t_end - g.groupby("pid").t_end.transform("max")) if cond == "baseline" else g.t_end
        for pid, gg in g.groupby("pid"):
            ax.plot(gg.rel, gg[c], color=color, alpha=0.12, lw=0.8)
        med = g.groupby("rel")[c].median(); q1 = g.groupby("rel")[c].quantile(.25); q3 = g.groupby("rel")[c].quantile(.75)
        ax.plot(med.index, med.values, color=color, lw=2.2, label=f"{cond} median")
        ax.fill_between(med.index, q1.values, q3.values, color=color, alpha=0.2)
    ax.axvline(0, color="k", ls="--", lw=1); ax.set_xlabel("seconds (baseline file end = 0 | task file start = 0)"); ax.set_title(lab, fontsize=10)
axes[0].legend(fontsize=8)
fig.suptitle(f"EEGMAT: separate baseline and arithmetic recordings, N={P.pid.nunique()} (thin lines = participants). Not a continuous transition.", fontsize=10)
fig.tight_layout(); fig.savefig("results/figures/figE1_eegmat_before_during.png", dpi=150)
print(json.dumps(summary, indent=1, default=float)[:6000])
