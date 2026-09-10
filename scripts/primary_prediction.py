"""Participant-level primary experiment (configs/primary_experiment_frozen.md): do first-cycle dynamics predict
second-challenge performance beyond context, baseline and first-cycle behaviour?

Inputs: data/features/matb_bins.parquet (wrist + behaviour, task clock), results/tables/recovery_endpoints.csv,
data/features/matb_eeg_bins_pXX.parquet (EEG bins, when present). Cutoff = end of recovery 1 (1,080 s): no feature uses later bins.
Outputs: results/tables/primary_participant_features.csv, primary_oof_predictions.csv, primary_model_comparison.json,
primary_secondary_hypotheses.json, primary_shortening.csv; figures figP1-figP4.
"""
import sys, json, glob, time
sys.path.insert(0, "src")
import numpy as np, pandas as pd
from scipy import stats
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from myndos.metrics import robust_reference, normalize, burden, recovery, first_sustained_departure
from myndos.modeling import nested_ridge_predict_fast as nested_ridge_predict, paired_bootstrap

SEED = 0; ALPHAS = (0.1, 1.0, 10.0, 100.0, 1000.0); N_PERM = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 500; TARGET_REL = 0.10
FLOOR = {"hr": 1.0, "eda": 0.02, "motion": 0.02, "temp": 0.05, "abs_err": 5.0}
df = pd.read_parquet("data/features/matb_bins.parquet")
R = pd.read_csv("results/tables/recovery_endpoints.csv")
Rmain = R[(R.bin_s == 10) & (R.reference == "A") & (R.band == 2.0) & (R.k == 3) & ((R.feature != "hr") | (R.hr_gate == 0.5))]


def refstats(x, feat):
    med, sc, fl = robust_reference(np.asarray(x, float))
    if np.isfinite(sc) and sc < FLOOR[feat]: sc = FLOOR[feat]
    return med, sc


def phys_features(g, feat, ch_win, rc_win, ref_win, prefix, cutoff_elapsed=None):
    """Response/burden/residual features of one physiological feature from bins inside explicit task-time windows.
    ch_win/rc_win/ref_win = (t_lo, t_hi] on the task clock; recovery bins after cutoff (task time) are dropped."""
    ref = g[(g.t_end > ref_win[0]) & (g.t_end <= ref_win[1])][feat]; med, sc = refstats(ref, feat)
    ch = g[(g.t_end > ch_win[0]) & (g.t_end <= ch_win[1])].sort_values("t_end"); rc = g[(g.t_end > rc_win[0]) & (g.t_end <= rc_win[1])].sort_values("t_end")
    zc = normalize(ch[feat].to_numpy(), med, sc); zr = normalize(rc[feat].to_numpy(), med, sc)
    out = {f"{prefix}_base": med, f"{prefix}_resp": float(np.nanmedian(ch[feat]) - med) if ch[feat].notna().any() else np.nan,
           f"{prefix}_burden_ch": burden(zc, 10.0), f"{prefix}_burden_rc": burden(zr, 10.0) if len(rc) else np.nan}
    if len(rc):
        t_rel = rc.t_end.to_numpy() - rc_win[0]; rec = recovery(zr, t_rel, band=2.0, k=3, excursion=True)
        out[f"{prefix}_resid_end"] = float(zr[np.isfinite(zr)][-1]) if np.isfinite(zr).any() else np.nan
        out[f"{prefix}_return"] = rec["return_time"] if rec["status"] == "returned" else (t_rel[-1] if t_rel.size else np.nan)
        out[f"{prefix}_censored"] = float(rec["status"] != "returned")
    return out


def behaviour_features(g, cutoff):
    b = g[g.condition == "working_baseline"]; base3 = b[b.elapsed > 180].abs_err
    f = {"base_err_last3": float(base3.mean()), "base_err_all": float(b.abs_err.mean()),
         "base_slope": float(np.polyfit(b.elapsed, b.abs_err, 1)[0] * 60) if b.abs_err.notna().sum() > 10 else np.nan}
    if cutoff >= 720:
        c1 = g[g.condition == "challenge_1"]; f["c1_err"] = float(c1.abs_err.mean()); f["c1_resp"] = f["c1_err"] - f["base_err_last3"]
        f["c1_err_last3"] = float(c1[c1.elapsed > 180].abs_err.mean())
    if cutoff > 720:
        r1 = g[(g.condition == "recovery_1") & (g.t_end <= cutoff)]; med = float(base3.median())
        f["r1_err"] = float(r1.abs_err.mean()); f["r1_excess"] = float(np.nansum(np.clip(r1.abs_err - med, 0, None)) * 10)
        ph = phys_features(g, "abs_err", (360, 720), (720, cutoff), (180, 360), "beh"); f["r1_resid_end"] = ph["beh_resid_end"]; f["r1_return"] = ph["beh_return"]; f["r1_censored"] = ph["beh_censored"]
    return f


def eeg_features(pid, cutoff):
    p = f"data/features/matb_eeg_bins_{pid}.parquet"
    if not glob.glob(p): return {}
    e = pd.read_parquet(p); e = e[e.eeg_ok] if "eeg_ok" in e else e
    out = {}
    for c, short in (("eeg_frontal_theta", "theta_f"), ("eeg_parietal_alpha", "alpha_p"), ("eeg_central_beta", "beta_c")):
        if c not in e or e[c].notna().sum() < 30: continue
        e2 = e.rename(columns={c: "x"}); e2["x"] = e2["x"].astype(float)
        ref = e2[(e2.condition == "working_baseline") & (e2.elapsed > 180)].x; med, sc, _ = robust_reference(ref.to_numpy()); sc = max(sc, 0.05) if np.isfinite(sc) else np.nan
        if cutoff >= 720:
            ch = e2[e2.condition == "challenge_1"]; out[f"{short}_resp"] = float(np.nanmedian(ch.x) - med) if ch.x.notna().any() else np.nan
        if cutoff > 720:
            rc = e2[(e2.condition == "recovery_1") & (e2.t_end_nominal <= cutoff)]; out[f"{short}_burden_rc"] = burden(normalize(rc.x.to_numpy(), med, sc), 10.0) if len(rc) else np.nan
    return out


def build(cutoff=1080, sham_shift=0, hr_gate=0.5, bins=None):
    rows = []
    for pid, g in (df if bins is None else bins).groupby("pid"):
        g = g[g.condition != "quiet_rest"].copy(); g["hr"] = np.where(g.ibi_cov >= hr_gate, g.hr_e4_raw, np.nan)
        f = {"pid": pid, **behaviour_features(g, cutoff)}
        s = sham_shift
        for feat in ("hr", "eda", "motion", "temp"):
            if cutoff >= 720:
                f.update(phys_features(g, feat, (360 + s, 720 + s), (720 + s, min(cutoff, 1080) + s) if cutoff > 720 else (720 + s, 720 + s), (180 + s, 360 + s), feat))
            else:
                f[f"{feat}_base"] = refstats(g[(g.t_end > 180) & (g.t_end <= 360)][feat], feat)[0]
        f.update(eeg_features(pid, cutoff))
        c2 = g[g.condition == "challenge_2"]; f["y_c2"] = float(c2.abs_err.mean()); f["y_c2_adj"] = f["y_c2"] - f["base_err_last3"]
        r2 = Rmain[(Rmain.pid == pid) & (Rmain.feature == "abs_err") & (Rmain.cycle == 2)]; f["y_r2_excess"] = float(r2.excess_integral_recovery.iloc[0]) if len(r2) else np.nan
        rows.append(f)
    return pd.DataFrame(rows).set_index("pid")


BLOCKS = {
    "B_baseline": ["base_err_last3", "base_err_all", "base_slope", "hr_base", "eda_base", "motion_base", "temp_base"],
    "C_behaviour": ["c1_err", "c1_resp", "r1_err", "r1_excess", "r1_resid_end", "r1_return", "r1_censored"],
    "D_peripheral": ["hr_resp", "hr_burden_ch", "hr_burden_rc", "hr_resid_end", "eda_resp", "eda_burden_ch", "eda_burden_rc", "eda_resid_end", "motion_resp"],
    "E_eeg": ["theta_f_resp", "alpha_p_resp", "beta_c_resp", "theta_f_burden_rc", "alpha_p_burden_rc", "beta_c_burden_rc"]}
MODELS = {"A_context": [], "B_baseline": BLOCKS["B_baseline"], "C_behaviour": BLOCKS["B_baseline"] + BLOCKS["C_behaviour"],
          "D_peripheral": BLOCKS["B_baseline"] + BLOCKS["C_behaviour"] + BLOCKS["D_peripheral"], "E_eeg": BLOCKS["B_baseline"] + BLOCKS["C_behaviour"] + BLOCKS["E_eeg"],
          "F_all": BLOCKS["B_baseline"] + BLOCKS["C_behaviour"] + BLOCKS["D_peripheral"] + BLOCKS["E_eeg"]}


def oof(F, cols, y_col, seed=SEED):
    y = F[y_col].to_numpy(float); pids = F.index.to_numpy()
    if not cols:  # model A: training-fold mean (LOO)
        return np.array([np.delete(y, i).mean() for i in range(y.size)])
    X = F[cols].to_numpy(float)
    return nested_ridge_predict(X, y, pids, n_outer=len(y), n_inner=5, alphas=ALPHAS, seed=seed)


def metrics(y, p):
    e = np.abs(y - p); return {"mae": float(e.mean()), "rmse": float(np.sqrt(np.mean((y - p) ** 2))), "spearman": float(stats.spearmanr(y, p).statistic), "r2_oof": float(1 - np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2))}


def compare(F, name, cols, ref_name, ref_cols, y_col, n_perm=0, jackknife=True, imputed=False):
    """Nested comparison. Matched subset (default): participants with complete features for BOTH models.
    imputed=True: all participants with a target; NaN features are median-imputed inside each training fold."""
    need = [c for c in set(cols + ref_cols) if c in F]; missing = [c for c in set(cols + ref_cols) if c not in F]
    sub = F.dropna(subset=[y_col]) if imputed else (F.dropna(subset=need + [y_col]) if need else F.dropna(subset=[y_col]))
    if imputed:
        keep_feat = [c for c in need if F[c].notna().sum() >= 10]; cols = [c for c in cols if c in keep_feat]; ref_cols = [c for c in ref_cols if c in keep_feat]
    if missing or len(sub) < 10:
        return {"model": name, "reference": ref_name, "status": f"not run (missing features {missing} or n={len(sub)})", "n": int(len(sub))}
    y = sub[y_col].to_numpy(float); p = oof(sub, cols, y_col); pr = oof(sub, ref_cols, y_col)
    e, er = np.abs(y - p), np.abs(y - pr); d = pd.Series(e - er, index=sub.index)
    out = {"model": name, "reference": ref_name, "target": y_col, "n": int(len(sub)), "participants": sub.index.tolist(), "features": cols, **{f"model_{k}": v for k, v in metrics(y, p).items()},
           **{f"ref_{k}": v for k, v in metrics(y, pr).items()}, "mae_diff_vs_ref": float(d.mean()), "rel_mae_change_vs_ref": float(d.mean() / er.mean()),
           "paired_bootstrap_mae_diff": paired_bootstrap(d, seed=SEED), "meets_frozen_target_10pct": bool(d.mean() / er.mean() <= -TARGET_REL and paired_bootstrap(d, seed=SEED)["ci_high"] < 0),
           "oof_pred": dict(zip(sub.index, np.round(p, 2))), "oof_ref_pred": dict(zip(sub.index, np.round(pr, 2)))}
    if jackknife:
        jk = []
        for pid in sub.index:
            s2 = sub.drop(index=pid); y2 = s2[y_col].to_numpy(float); jk.append(float(np.mean(np.abs(y2 - oof(s2, cols, y_col)) - np.abs(y2 - oof(s2, ref_cols, y_col)))))
        out["jackknife_mae_diff_range"] = [float(min(jk)), float(max(jk))]; out["jackknife_most_influential"] = str(sub.index[int(np.argmax(np.abs(np.array(jk) - d.mean())))])
    if n_perm:
        rng = np.random.default_rng(SEED); obs = d.mean(); null = []
        for i in range(n_perm):
            s2 = sub.copy(); s2[y_col] = rng.permutation(y); y2 = s2[y_col].to_numpy(float)
            null.append(float(np.mean(np.abs(y2 - oof(s2, cols, y_col, seed=i)) - np.abs(y2 - oof(s2, ref_cols, y_col, seed=i)))))
        null = np.array(null); out["permutation"] = {"n_perm": n_perm, "observed_mae_diff": float(obs), "p_value_one_sided_improvement": float((np.sum(null <= obs) + 1) / (n_perm + 1)), "null_mean": float(null.mean()), "null_sd": float(null.std())}
    return out


def main():
    t0 = time.time()
    F = build(); F.to_csv("results/tables/primary_participant_features.csv")
    res = {"seed": SEED, "n_participants": int(len(F)), "frozen_plan": "configs/primary_experiment_frozen.md", "target_primary": "y_c2 = mean abs RESMAN target error over challenge 2 (fuel units)",
           "feature_availability": {c: int(F[c].notna().sum()) for c in sum(BLOCKS.values(), []) if c in F}, "eeg_participants_available": int(F.get("theta_f_resp", pd.Series(dtype=float)).notna().sum())}
    # ---- nested ladder on the primary target, each vs the model one step below and vs C
    ladder = []
    for name, cols in MODELS.items():
        if name == "A_context": continue
        prev = list(MODELS)[list(MODELS).index(name) - 1]
        ladder.append(compare(F, name, cols, "A_context" if prev == "A_context" else prev, MODELS[prev], "y_c2", n_perm=0, jackknife=False))
    res["ladder_vs_previous_model"] = ladder
    res["ladder_all_participants_imputed"] = [compare(F, n, MODELS[n], "A_context" if i == 0 else list(MODELS)[i], MODELS[list(MODELS)[i]], "y_c2", imputed=True, jackknife=False) for i, n in enumerate(list(MODELS)[1:])]
    res["primary_vs_C_all_participants_imputed"] = {n: compare(F, n, MODELS[n], "C_behaviour", MODELS["C_behaviour"], "y_c2", imputed=True, jackknife=True) for n in ("D_peripheral", "E_eeg", "F_all")}
    key = {}
    for name in ("D_peripheral", "E_eeg", "F_all"):
        key[name] = compare(F, name, MODELS[name], "C_behaviour", MODELS["C_behaviour"], "y_c2", n_perm=N_PERM, jackknife=True)
    res["primary_vs_C"] = key
    res["A_vs_C"] = compare(F, "C_behaviour", MODELS["C_behaviour"], "A_context", [], "y_c2"); res["B_vs_C"] = compare(F, "C_behaviour", MODELS["C_behaviour"], "B_baseline", MODELS["B_baseline"], "y_c2")
    # ---- secondary targets
    res["secondary_targets"] = {y: {n: compare(F, n, MODELS[n], "C_behaviour", MODELS["C_behaviour"], y) for n in ("D_peripheral", "F_all")} for y in ("y_c2_adj", "y_r2_excess")}
    # ---- missingness: all 35 with imputation + indicator, and indicator-only control
    F2 = F.copy(); F2["hr_missing"] = F2.hr_resp.isna().astype(float)
    res["missingness"] = {"n_hr_missing": int(F2.hr_missing.sum()), "hr_missing_participants": F2.index[F2.hr_missing == 1].tolist(),
                          "D_imputed_all35_vs_C": compare(F2.assign(**{c: F2[c] for c in BLOCKS["D_peripheral"]}), "D_peripheral_imputed", MODELS["C_behaviour"] + ["hr_missing"] + BLOCKS["D_peripheral"], "C_behaviour", MODELS["C_behaviour"], "y_c2") if False else None}
    # imputation happens inside folds only if NaNs are passed through; compare() drops NaN rows, so build an explicit variant
    def compare_imputed(name, cols, ref_cols, y_col):
        sub = F2.dropna(subset=[y_col]); y = sub[y_col].to_numpy(float); p = oof(sub, cols, y_col); pr = oof(sub, ref_cols, y_col); d = pd.Series(np.abs(y - p) - np.abs(y - pr), index=sub.index)
        return {"model": name, "n": int(len(sub)), "model_mae": float(np.abs(y - p).mean()), "ref_mae": float(np.abs(y - pr).mean()), "rel_mae_change_vs_ref": float(d.mean() / np.abs(y - pr).mean()), "paired_bootstrap_mae_diff": paired_bootstrap(d, seed=SEED)}
    res["missingness"]["D_imputed_all_vs_C"] = compare_imputed("D_peripheral_imputed_plus_indicator", MODELS["C_behaviour"] + ["hr_missing"] + BLOCKS["D_peripheral"], MODELS["C_behaviour"], "y_c2")
    res["missingness"]["indicator_only_vs_C"] = compare_imputed("C_plus_hr_missing_indicator", MODELS["C_behaviour"] + ["hr_missing"], MODELS["C_behaviour"], "y_c2")
    # ---- negative controls: sham segmentation (+180 s), strict/permissive QC
    Fs = build(sham_shift=180); Fs = Fs.rename(columns={c: c for c in Fs})
    res["controls"] = {"sham_shift_180s_D_vs_C": compare(Fs, "D_peripheral_sham", MODELS["D_peripheral"], "C_behaviour", MODELS["C_behaviour"], "y_c2"),
                       "strict_qc_hr_gate_0.7": compare(build(hr_gate=0.7), "D_peripheral_strict", MODELS["D_peripheral"], "C_behaviour", MODELS["C_behaviour"], "y_c2"),
                       "permissive_qc_hr_gate_0.3": compare(build(hr_gate=0.3), "D_peripheral_permissive", MODELS["D_peripheral"], "C_behaviour", MODELS["C_behaviour"], "y_c2")}
    # ---- ablation on the matched complete cohort (identical LOO folds by construction: same participants, same seed)
    need = [c for c in MODELS["F_all"] if c in F]; Fm = F.dropna(subset=need + ["y_c2"])
    abl = {"n_matched": int(len(Fm)), "participants": Fm.index.tolist()}
    if len(Fm) >= 10:
        y = Fm.y_c2.to_numpy(float); preds = {n: oof(Fm, [c for c in cols if c in Fm], "y_c2") for n, cols in MODELS.items()}
        preds["C_plus_EEG_only_no_peripheral"] = preds["E_eeg"]; preds["C_plus_peripheral_only"] = preds["D_peripheral"]
        abl["mae"] = {n: float(np.abs(y - p).mean()) for n, p in preds.items()}; abl["spearman"] = {n: float(stats.spearmanr(y, p).statistic) for n, p in preds.items()}
        abl["paired_vs_C"] = {n: paired_bootstrap(pd.Series(np.abs(y - p) - np.abs(y - preds["C_behaviour"]), index=Fm.index), seed=SEED) for n, p in preds.items() if n != "C_behaviour"}
        pd.DataFrame({**{"y_c2": y}, **preds}, index=Fm.index).to_csv("results/tables/primary_oof_predictions.csv")
    res["ablation_matched_cohort"] = abl
    # ---- assessment shortening: cutoffs; behaviour-only vs + peripheral (+ EEG) with features restricted to bins before the cutoff
    short = []
    for cutoff in (360, 720, 780, 900, 1080):
        Fc = build(cutoff=cutoff); beh = [c for c in MODELS["C_behaviour"] if c in Fc and Fc[c].notna().sum() >= 10]
        per = beh + [c for c in BLOCKS["D_peripheral"] if c in Fc and Fc[c].notna().sum() >= 10]; eeg = [c for c in BLOCKS["E_eeg"] if c in Fc and Fc[c].notna().sum() >= 10]
        sub = Fc.dropna(subset=list(set(per + eeg)) + ["y_c2"]) if (per + eeg) else Fc
        y = sub.y_c2.to_numpy(float); row = {"cutoff_s": cutoff, "n": int(len(sub)), "n_features_behaviour": len(beh), "n_features_peripheral_added": len(per) - len(beh), "n_features_eeg_added": len(eeg)}
        for lab, cols in (("behaviour", beh), ("behaviour_plus_peripheral", per), ("behaviour_plus_peripheral_plus_eeg", per + eeg)):
            p = oof(sub, cols, "y_c2"); row[f"mae_{lab}"] = float(np.abs(y - p).mean()); row[f"spearman_{lab}"] = float(stats.spearmanr(y, p).statistic) if len(set(p)) > 1 else np.nan
            if lab != "behaviour":
                bb = paired_bootstrap(pd.Series(np.abs(y - p) - np.abs(y - oof(sub, beh, "y_c2")), index=sub.index), seed=SEED); row[f"ci_low_{lab}_vs_behaviour"] = bb["ci_low"]; row[f"ci_high_{lab}_vs_behaviour"] = bb["ci_high"]
        short.append(row)
    S = pd.DataFrame(short); S.to_csv("results/tables/primary_shortening.csv", index=False); res["shortening"] = short
    # ---- secondary hypotheses
    sec = {}
    def partial_spearman(x, y, covs):
        d = pd.concat([x, y] + covs, axis=1).dropna(); Xc = np.column_stack([np.ones(len(d))] + [d.iloc[:, 2 + i] for i in range(len(covs))])
        rx = d.iloc[:, 0] - Xc @ np.linalg.lstsq(Xc, d.iloc[:, 0], rcond=None)[0]; ry = d.iloc[:, 1] - Xc @ np.linalg.lstsq(Xc, d.iloc[:, 1], rcond=None)[0]
        r = stats.spearmanr(rx, ry); return {"n": int(len(d)), "partial_rho": float(r.statistic), "p": float(r.pvalue)}
    covs = [F.base_err_last3, F.c1_err]
    sec["A_physiology_at_equivalent_performance"] = {"controls": ["base_err_last3", "c1_err"], **{f"{c}_vs_y_c2": partial_spearman(F[c], F.y_c2, covs) for c in ("hr_resp", "eda_resp", "hr_burden_ch", "eda_burden_ch") + tuple(c for c in ("theta_f_resp", "alpha_p_resp") if c in F)},
                                                     **{f"{c}_vs_y_r2_excess": partial_spearman(F[c], F.y_r2_excess, covs) for c in ("hr_resp", "eda_resp")}}
    ter = pd.qcut(F.c1_err, 3, labels=["low", "mid", "high"]); sec["A_within_performance_tertile_spearman"] = {t: {c: float(stats.spearmanr(F.loc[ter == t, c], F.loc[ter == t, "y_c2"], nan_policy="omit").statistic) for c in ("hr_resp", "eda_resp")} for t in ("low", "mid", "high")}
    # B: cross-system recovery timing (cycle 1)
    tim = {}
    for feat in ("abs_err", "hr", "eda"):
        m = Rmain[(Rmain.feature == feat) & (Rmain.cycle == 1)].set_index("pid"); tim[feat] = {"returned": int((m.status == "returned").sum()), "censored": int(m.censored.sum()), "not_estimable": int((m.status == "not_estimable").sum()), "return_median_s": float(m.loc[m.status == "returned", "return_time"].median()) if (m.status == "returned").any() else np.nan}
    eegm = pd.read_csv("results/tables/matb_eeg_participant_metrics.csv") if glob.glob("results/tables/matb_eeg_participant_metrics.csv") else None
    if eegm is not None:
        for feat in ("eeg_frontal_theta", "eeg_parietal_alpha"):
            m = eegm[(eegm.feature == feat) & (eegm.cycle == 1)]; tim[feat] = {"returned": int((m["status_b2.0"] == "returned").sum()), "censored": int((m["status_b2.0"] == "censored").sum()), "not_estimable": int((m["status_b2.0"] == "not_estimable").sum()), "ambiguous": int((m["status_b2.0"] == "ambiguous_timing").sum()), "return_median_s": float(m.loc[m["status_b2.0"] == "returned", "return_time_b2.0"].median()) if (m["status_b2.0"] == "returned").any() else np.nan}
    pair = {}
    for a, b in (("abs_err", "hr"), ("abs_err", "eda"), ("hr", "eda")):
        ma = Rmain[(Rmain.feature == a) & (Rmain.cycle == 1) & (Rmain.status == "returned")].set_index("pid").return_time; mb = Rmain[(Rmain.feature == b) & (Rmain.cycle == 1) & (Rmain.status == "returned")].set_index("pid").return_time
        j = pd.concat([ma, mb], axis=1, join="inner"); pair[f"{a}_vs_{b}"] = {"n_both_returned": int(len(j)), "spearman": float(stats.spearmanr(j.iloc[:, 0], j.iloc[:, 1]).statistic) if len(j) >= 5 else np.nan}
    timing_cols = ["hr_return", "hr_censored", "eda_return", "eda_censored"]
    sec["B_cross_system_recovery_timing"] = {"cycle1_by_modality": tim, "pairwise_return_time_spearman_both_returned": pair, "C_plus_timing_vs_C": compare(F, "C_plus_physio_timing", MODELS["C_behaviour"] + timing_cols, "C_behaviour", MODELS["C_behaviour"], "y_c2"),
                                             "note": "sensor lags: E4 HR is a vendor 10-s running estimate; EDA slow (seconds); behaviour snapshot every 10 s; EEG zero-phase. Differences < 20 s are within measurement lag."}
    # C: carryover
    sec["C_carryover"] = {"controls": ["c1_err"], **{f"{c}_vs_y_c2": partial_spearman(F[c], F.y_c2, [F.c1_err]) for c in ("r1_resid_end", "r1_excess", "hr_resid_end", "eda_resid_end") + tuple(c for c in ("theta_f_burden_rc", "alpha_p_burden_rc") if c in F)},
                          "C_plus_physio_residuals_vs_C": compare(F, "C_plus_physio_residuals", MODELS["C_behaviour"] + ["hr_resid_end", "eda_resid_end", "hr_burden_rc", "eda_burden_rc"], "C_behaviour", MODELS["C_behaviour"], "y_c2"),
                          "note": "two sequential cycles in fixed order; carryover is confounded with fatigue, practice and block scripts; no test-retest reliability is implied"}
    json.dump(sec, open("results/tables/primary_secondary_hypotheses.json", "w"), indent=2, default=float)
    res["runtime_s"] = time.time() - t0
    json.dump(res, open("results/tables/primary_model_comparison.json", "w"), indent=2, default=float)
    # ---- figures
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    for ax, name in zip(axes, ("C_behaviour", "F_all" if key["F_all"].get("status", "run") == "run" or "oof_pred" in key["F_all"] else "D_peripheral")):
        k = key.get(name) or res["A_vs_C"]; pr = k["oof_pred"] if name != "C_behaviour" else res["A_vs_C"]["oof_pred"]
        yy = F.loc[list(pr), "y_c2"]; pp = np.array(list(pr.values()))
        ax.scatter(pp, yy, s=22, color="#1f4e79"); lim = [0, max(yy.max(), pp.max()) * 1.05]; ax.plot(lim, lim, "k:", lw=0.8)
        ax.set_xlabel("out-of-fold prediction (fuel units)"); ax.set_ylabel("observed challenge-2 mean abs error"); ax.set_title(f"{name}: n={len(yy)}, MAE={np.abs(yy - pp).mean():.0f}, rho={stats.spearmanr(yy, pp).statistic:.2f}", fontsize=9)
    fig.suptitle("PRIMARY MATB-II: predicted vs observed second-challenge performance (leave-one-participant-out, nested ridge)", fontsize=9); fig.tight_layout(); fig.savefig("results/figures/figP1_pred_vs_observed.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 4.4)); names = ["A_context", "B_baseline", "C_behaviour", "D_peripheral", "E_eeg", "F_all"]
    if "mae" in abl:
        vals = [abl["mae"].get(n, np.nan) for n in names]; ax.bar(range(len(names)), vals, color=["#7f7f7f", "#7f7f7f", "#1f4e79", "#dd8452", "#8172b2", "#c44e52"])
        for i, n in enumerate(names):
            b = abl["paired_vs_C"].get(n)
            if b: ax.text(i, vals[i], f"d={b['mean']:+.0f}\n[{b['ci_low']:+.0f},{b['ci_high']:+.0f}]", ha="center", va="bottom", fontsize=7)
        ax.set_xticks(range(len(names))); ax.set_xticklabels(names, fontsize=8); ax.set_ylabel("held-out MAE (fuel units)"); ax.set_title(f"Nested models on the matched complete-data cohort (n={abl['n_matched']}); paired bootstrap difference vs C", fontsize=9)
    fig.tight_layout(); fig.savefig("results/figures/figP2_model_comparison_and_ablation.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for lab, col in (("behaviour", "#1f4e79"), ("behaviour_plus_peripheral", "#dd8452"), ("behaviour_plus_peripheral_plus_eeg", "#c44e52")):
        if f"mae_{lab}" in S: ax.plot(S.cutoff_s, S[f"mae_{lab}"], marker="o", color=col, label=lab)
    for x in (360, 720, 1080): ax.axvline(x, color="k", ls=":", lw=0.7)
    ax.set_xlabel("observation cutoff (s of task time; 360 = end of baseline, 720 = end of challenge 1, 1080 = end of recovery 1)"); ax.set_ylabel("held-out MAE of challenge-2 error"); ax.legend(fontsize=8)
    ax.set_title("Assessment shortening: prediction quality vs observation time (features restricted to bins before the cutoff)", fontsize=9); fig.tight_layout(); fig.savefig("results/figures/figP3_shortening_curve.png", dpi=150); plt.close(fig)
    # print
    print(f"n={len(F)}; EEG available for {res['eeg_participants_available']}; runtime {res['runtime_s']:.0f}s")
    for n, k in key.items():
        if "model_mae" in k: print(f"{n}: n={k['n']} MAE {k['model_mae']:.1f} vs C {k['ref_mae']:.1f} rel {k['rel_mae_change_vs_ref']:+.1%} CI[{k['paired_bootstrap_mae_diff']['ci_low']:+.1f},{k['paired_bootstrap_mae_diff']['ci_high']:+.1f}] perm p={k.get('permutation', {}).get('p_value_one_sided_improvement')} rho {k['model_spearman']:.2f} vs {k['ref_spearman']:.2f} jackknife {k.get('jackknife_mae_diff_range')} target_met={k['meets_frozen_target_10pct']}")
        else: print(n, k)
    print("A vs C:", {k: res["A_vs_C"][k] for k in ("n", "model_mae", "ref_mae", "rel_mae_change_vs_ref")}); print("B vs C:", {k: res["B_vs_C"][k] for k in ("n", "model_mae", "ref_mae", "rel_mae_change_vs_ref")})
    print("ladder all-35 imputed:", [(x["model"], x["n"], round(x["model_mae"]), round(x["ref_mae"]), round(x["rel_mae_change_vs_ref"], 3)) for x in res["ladder_all_participants_imputed"]])
    print("vs C all-35 imputed:", {n: (x["n"], round(x["model_mae"]), round(x["ref_mae"]), round(x["rel_mae_change_vs_ref"], 3), round(x["paired_bootstrap_mae_diff"]["ci_low"]), round(x["paired_bootstrap_mae_diff"]["ci_high"])) for n, x in res["primary_vs_C_all_participants_imputed"].items()})
    print("controls:", {k: (v.get("rel_mae_change_vs_ref"), v.get("n")) for k, v in res["controls"].items()}); print("missingness:", {k: (v.get("rel_mae_change_vs_ref"), v.get("n")) for k, v in res["missingness"].items() if isinstance(v, dict)})
    print("ablation:", abl.get("mae")); print(S.round(1).to_string())
    print("secondary A:", json.dumps(sec["A_physiology_at_equivalent_performance"], default=float)); print("secondary B:", json.dumps(sec["B_cross_system_recovery_timing"]["cycle1_by_modality"], default=float), sec["B_cross_system_recovery_timing"]["pairwise_return_time_spearman_both_returned"], {k: sec["B_cross_system_recovery_timing"]["C_plus_timing_vs_C"].get(k) for k in ("rel_mae_change_vs_ref", "n")})
    print("secondary C:", json.dumps({k: v for k, v in sec["C_carryover"].items() if k.endswith("vs_y_c2")}, default=float), {k: sec["C_carryover"]["C_plus_physio_residuals_vs_C"].get(k) for k in ("rel_mae_change_vs_ref", "n")})


if __name__ == "__main__":
    main()
