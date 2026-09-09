"""Recovery-endpoint validity and sensitivity on the PRIMARY dataset (participant x cycle x feature).

Reads data/features/matb_bins.parquet (10-s bins, task clock) and writes
  results/tables/recovery_endpoints.csv      one row per participant x cycle x feature x definition variant
  results/tables/recovery_validity.json      comparability checks + sensitivity summaries
  results/figures/figR1_individual_trajectories.png, figR2_recovery_distributions.png
Endpoints: response magnitude (challenge median - reference median), integrated excess over the recovery window (positive part,
raw units x s), |z| burden, time to sustained return (right-censored), residual at 360 s, recovery slope (z per minute over the
first 180 s, >= 12 valid bins), exponential time constant (accepted only if R^2 >= 0.5, tau < 720 s, positive decay amplitude).
Sensitivity grid: reference A/B, band 1.5/2/2.5, k = 2/3/4, bin width 10/30 s, HR coverage gate 0.3/0.5/0.7.
No smoothing or overlapping windows are used anywhere (10-s snapshots for behaviour; 10-s bins for physiology).
"""
import sys, json, itertools
sys.path.insert(0, "src")
import numpy as np, pandas as pd
from scipy import stats, optimize
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from myndos.metrics import robust_reference, normalize, first_sustained_departure, recovery, burden

FEATS = ["abs_err", "hr", "eda", "motion"]
FLOOR = {"hr": 1.0, "eda": 0.02, "temp": 0.05, "motion": 0.02, "abs_err": 5.0}
df = pd.read_parquet("data/features/matb_bins.parquet")


def ref_stats(x, feat):
    med, sc, fl = robust_reference(np.asarray(x, float))
    if np.isfinite(sc) and sc < FLOOR[feat]: sc, fl = FLOOR[feat], True
    return med, sc, fl


def rebin(g, width):
    """Aggregate 10-s bins into non-overlapping ``width``-s bins inside each block (mean of available bins)."""
    if width == 10: return g
    g = g.copy(); g["k"] = ((g.elapsed - 1e-9) // width).astype(int)
    out = g.groupby(["pid", "condition", "k"], as_index=False).agg({c: "mean" for c in FEATS + ["hr_e4_raw", "ibi_cov"]} | {"elapsed": "max", "t_end": "max", "cycle": "first"})
    return out


def exp_fit(t, x):
    """x(t) = a + b*exp(-t/tau) on recovery bins; returns (tau, r2, a, b) or NaNs with a reason."""
    m = np.isfinite(x); t, x = t[m], x[m]
    if x.size < 12: return np.nan, np.nan, np.nan, np.nan, "insufficient bins"
    try:
        popt, _ = optimize.curve_fit(lambda tt, a, b, tau: a + b * np.exp(-tt / tau), t, x, p0=[x[-6:].mean(), x[:3].mean() - x[-6:].mean(), 60.0], bounds=([-np.inf, -np.inf, 5.0], [np.inf, np.inf, 2000.0]), maxfev=20000)
    except Exception as e:
        return np.nan, np.nan, np.nan, np.nan, f"fit failed: {type(e).__name__}"
    a, b, tau = popt; pred = a + b * np.exp(-t / tau); r2 = 1 - np.sum((x - pred) ** 2) / max(np.sum((x - x.mean()) ** 2), 1e-12)
    ok = r2 >= 0.5 and tau < 720 and b > 0
    return (tau if ok else np.nan), r2, a, b, ("accepted" if ok else f"rejected (r2={r2:.2f}, tau={tau:.0f}, b={b:.2f})")


rows = []
for pid, g0 in df.groupby("pid"):
    for width in (10, 30):
        g = rebin(g0, width)
        for gate in (0.3, 0.5, 0.7):
            gg = g.copy(); gg["hr"] = np.where(gg.ibi_cov >= gate, gg.hr_e4_raw, np.nan)
            for feat in FEATS:
                if feat != "hr" and gate != 0.5: continue
                base = gg[gg.condition == "working_baseline"]
                for refname, ref in (("A", base[base.elapsed > 180]), ("B", base)):
                    med, sc, fl = ref_stats(ref[feat], feat)
                    for cyc in (1, 2):
                        ch = gg[gg.condition == f"challenge_{cyc}"].sort_values("elapsed"); rc = gg[gg.condition == f"recovery_{cyc}"].sort_values("elapsed")
                        zc = normalize(ch[feat].to_numpy(), med, sc); zr = normalize(rc[feat].to_numpy(), med, sc)
                        base_row = {"pid": pid, "feature": feat, "cycle": cyc, "bin_s": width, "hr_gate": gate if feat == "hr" else np.nan, "reference": refname,
                                    "ref_median": med, "ref_scale": sc, "scale_flag": fl, "n_ch_valid": int(np.isfinite(zc).sum()), "n_rc_valid": int(np.isfinite(zr).sum()),
                                    "resp_magnitude": float(np.nanmedian(ch[feat]) - med) if ch[feat].notna().any() else np.nan,
                                    "excess_integral_recovery": float(np.nansum(np.clip(rc[feat].to_numpy() - med, 0, None)) * width) if rc[feat].notna().any() else np.nan,
                                    "abs_z_burden_challenge": burden(zc, width), "abs_z_burden_recovery": burden(zr, width),
                                    "residual_360": float(zr[-1]) if zr.size and np.isfinite(zr[-1]) else np.nan}
                        # slope over the first 180 s of recovery (z per minute)
                        m180 = (rc.elapsed <= 180).to_numpy() & np.isfinite(zr)
                        base_row["slope_z_per_min_0_180"] = float(np.polyfit(rc.elapsed.to_numpy()[m180] / 60.0, zr[m180], 1)[0]) if m180.sum() >= (12 if width == 10 else 4) else np.nan
                        tau, r2, a, b, why = exp_fit(rc.elapsed.to_numpy(), rc[feat].to_numpy()) if width == 10 else (np.nan, np.nan, np.nan, np.nan, "not fitted at 30 s")
                        base_row.update({"exp_tau_s": tau, "exp_r2": r2, "exp_note": why})
                        for band, k in itertools.product((1.5, 2.0, 2.5), (2, 3, 4)):
                            td = first_sustained_departure(zc, ch.elapsed.to_numpy(), band=band, k=k)
                            rec = recovery(zr, rc.elapsed.to_numpy(), band=band, k=k, excursion=np.isfinite(td))
                            rows.append({**base_row, "band": band, "k": k, "t_depart": td, "return_time": rec["return_time"], "status": rec["status"],
                                         "censored": rec["status"] == "censored", "observed_recovery_s": rec["observed_duration"]})
R = pd.DataFrame(rows); R.to_csv("results/tables/recovery_endpoints.csv", index=False)
main = R[(R.bin_s == 10) & (R.reference == "A") & (R.band == 2.0) & (R.k == 3) & ((R.feature != "hr") | (R.hr_gate == 0.5))]

# ---------------- comparability checks (behaviour) ----------------
V = {"protocol": "RESMAN in every block; challenge = RESMAN + COMMS; fixed order; no counterbalancing; recovery = removal of COMMS only (README)."}
b = df[df.condition == "working_baseline"]
V["baseline_error_by_minute_median"] = b.groupby((b.elapsed - 1) // 60).abs_err.median().round(1).tolist()
V["baseline_error_trend"] = {"n_participants_with_positive_slope": int(sum(np.polyfit(g.elapsed, g.abs_err, 1)[0] > 0 for _, g in b.groupby("pid") if g.abs_err.notna().sum() > 10)),
                             "median_slope_units_per_min": float(np.median([np.polyfit(g.elapsed, g.abs_err, 1)[0] * 60 for _, g in b.groupby("pid") if g.abs_err.notna().sum() > 10]))}
for cond in ["recovery_1", "recovery_2"]:
    r = df[df.condition == cond]; V[f"{cond}_error_by_minute_median"] = r.groupby((r.elapsed - 1) // 60).abs_err.median().round(1).tolist()
end_base = b[b.elapsed > 180].groupby("pid").abs_err.mean(); rows_c = {}
for cond in ["recovery_1", "recovery_2"]:
    r = df[(df.condition == cond) & (df.elapsed > 180)].groupby("pid").abs_err.mean(); d = (r - end_base).dropna()
    w = stats.wilcoxon(d) if d.abs().sum() > 0 else None
    rows_c[cond] = {"last3min_minus_end_baseline_mean": float(d.mean()), "median": float(d.median()), "wilcoxon_p": float(w.pvalue) if w else np.nan, "n": int(d.size),
                    "fraction_within_end_baseline_band_pm2": float((main[(main.feature == "abs_err") & (main.cycle == int(cond[-1]))].residual_360.abs() <= 2).mean())}
V["end_of_recovery_vs_end_of_baseline"] = rows_c
c1 = df[df.condition == "challenge_1"].groupby("pid").abs_err.mean(); c2 = df[df.condition == "challenge_2"].groupby("pid").abs_err.mean()
V["challenge2_vs_challenge1"] = {"mean_diff": float((c2 - c1).mean()), "median_diff": float((c2 - c1).median()), "wilcoxon_p": float(stats.wilcoxon(c2 - c1).pvalue), "spearman_rho": float(stats.spearmanr(c1, c2).statistic),
                                 "note": "fixed order: any difference confounds fatigue, practice, carryover and (unverifiable) block-specific pump-failure scripts"}
V["smoothing_and_lag"] = "behaviour: raw 10-s snapshots, no smoothing/overlap; E4 HR: vendor 10-s running estimate (lag <= 10 s, not corrected); EDA/TEMP/ACC: per-bin median/mean of raw samples; EEG: zero-phase filtering (no lag), Welch inside the bin."
V["censoring_rule"] = "no return within the 360-s recovery block -> right-censored (status 'censored'); observed_recovery_s = block length; never treated as a recovery time."

# ---------------- sensitivity summaries ----------------
def summarize(sub):
    out = {}
    for (feat, cyc), g in sub.groupby(["feature", "cycle"]):
        rt = g.loc[g.status == "returned", "return_time"]
        out[f"{feat}_c{cyc}"] = {"n": int(len(g)), "returned": int((g.status == "returned").sum()), "censored": int(g.censored.sum()), "not_estimable": int((g.status == "not_estimable").sum()),
                                 "return_median_s": float(rt.median()) if rt.size else np.nan, "excess_integral_median": float(g.excess_integral_recovery.median()), "residual_360_median": float(g.residual_360.median()),
                                 "slope_median": float(g.slope_z_per_min_0_180.median()), "tau_accepted": int(g.exp_tau_s.notna().sum()), "tau_median_s": float(g.exp_tau_s.median()) if g.exp_tau_s.notna().any() else np.nan}
    return out
V["primary_definition"] = summarize(main)
sens = {}
for name, sub in [("reference_B", R[(R.bin_s == 10) & (R.reference == "B") & (R.band == 2.0) & (R.k == 3) & ((R.feature != "hr") | (R.hr_gate == 0.5))]),
                  ("band_1.5", R[(R.bin_s == 10) & (R.reference == "A") & (R.band == 1.5) & (R.k == 3) & ((R.feature != "hr") | (R.hr_gate == 0.5))]),
                  ("band_2.5", R[(R.bin_s == 10) & (R.reference == "A") & (R.band == 2.5) & (R.k == 3) & ((R.feature != "hr") | (R.hr_gate == 0.5))]),
                  ("k_2", R[(R.bin_s == 10) & (R.reference == "A") & (R.band == 2.0) & (R.k == 2) & ((R.feature != "hr") | (R.hr_gate == 0.5))]),
                  ("k_4", R[(R.bin_s == 10) & (R.reference == "A") & (R.band == 2.0) & (R.k == 4) & ((R.feature != "hr") | (R.hr_gate == 0.5))]),
                  ("bin_30s", R[(R.bin_s == 30) & (R.reference == "A") & (R.band == 2.0) & (R.k == 3) & ((R.feature != "hr") | (R.hr_gate == 0.5))]),
                  ("hr_gate_0.3", R[(R.bin_s == 10) & (R.reference == "A") & (R.band == 2.0) & (R.k == 3) & (R.feature == "hr") & (R.hr_gate == 0.3)]),
                  ("hr_gate_0.7", R[(R.bin_s == 10) & (R.reference == "A") & (R.band == 2.0) & (R.k == 3) & (R.feature == "hr") & (R.hr_gate == 0.7)])]:
    sens[name] = {k: {kk: v[kk] for kk in ("returned", "censored", "not_estimable", "return_median_s")} for k, v in summarize(sub).items()}
V["sensitivity"] = sens
# rank stability of the participant ordering on the primary endpoint across definitions (Spearman vs primary)
stab = {}
p_main = main[(main.feature == "abs_err") & (main.cycle == 1)].set_index("pid")
for name, sub in [("reference_B", R[(R.bin_s == 10) & (R.reference == "B") & (R.band == 2.0) & (R.k == 3) & (R.feature == "abs_err") & (R.cycle == 1)]),
                  ("bin_30s", R[(R.bin_s == 30) & (R.reference == "A") & (R.band == 2.0) & (R.k == 3) & (R.feature == "abs_err") & (R.cycle == 1)])]:
    s = sub.set_index("pid").reindex(p_main.index)
    stab[name] = {"excess_integral_spearman": float(stats.spearmanr(p_main.excess_integral_recovery, s.excess_integral_recovery, nan_policy="omit").statistic),
                  "residual_360_spearman": float(stats.spearmanr(p_main.residual_360, s.residual_360, nan_policy="omit").statistic)}
V["rank_stability_vs_primary_definition"] = stab
json.dump(V, open("results/tables/recovery_validity.json", "w"), indent=2, default=float)

# ---------------- figures ----------------
fig, axes = plt.subplots(2, 2, figsize=(14, 8))
for j, feat in enumerate(["abs_err", "hr"]):
    for i, cyc in enumerate((1, 2)):
        ax = axes[i, j]; win = df[df.condition.isin([f"challenge_{cyc}", f"recovery_{cyc}"])]
        for pid, g in win.groupby("pid"):
            g = g.sort_values("t_end"); ax.plot(g.t_end - (360 if cyc == 1 else 1080) - 360, g[feat], color="#1f4e79", alpha=0.18, lw=0.8)
        med = win.groupby("t_end")[feat].median(); ax.plot(med.index - (360 if cyc == 1 else 1080) - 360, med.values, color="#c44e52", lw=2, label="cohort median")
        eb = df[(df.condition == "working_baseline") & (df.elapsed > 180)][feat].median(); ax.axhline(eb, color="#4d9221", lw=1, ls="--", label="cohort end-of-baseline median")
        ax.axvspan(-360, 0, color="#f4c7c3", alpha=0.4, lw=0); ax.set_title(f"{feat}, cycle {cyc}: raw 10-s values, every participant + median", fontsize=9)
        ax.set_xlabel("seconds from demand decrease (challenge shaded)"); ax.legend(fontsize=7)
        if feat == "abs_err": ax.set_ylim(0, 1500)
fig.suptitle("PRIMARY MATB-II: minimally processed individual trajectories (no smoothing) around each challenge -> recovery transition", fontsize=10)
fig.tight_layout(); fig.savefig("results/figures/figR1_individual_trajectories.png", dpi=150); plt.close(fig)

fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
for ax, (feat, title) in zip(axes, [("abs_err", "behaviour (abs target error)"), ("hr", "heart rate (gated)"), ("eda", "EDA")]):
    for j, (name, sub) in enumerate([("primary A/2.0/k3", main), ("band 1.5", sens and R[(R.bin_s == 10) & (R.reference == "A") & (R.band == 1.5) & (R.k == 3) & ((R.feature != "hr") | (R.hr_gate == 0.5))]),
                                     ("band 2.5", R[(R.bin_s == 10) & (R.reference == "A") & (R.band == 2.5) & (R.k == 3) & ((R.feature != "hr") | (R.hr_gate == 0.5))]),
                                     ("k=2", R[(R.bin_s == 10) & (R.reference == "A") & (R.band == 2.0) & (R.k == 2) & ((R.feature != "hr") | (R.hr_gate == 0.5))]),
                                     ("ref B", R[(R.bin_s == 10) & (R.reference == "B") & (R.band == 2.0) & (R.k == 3) & ((R.feature != "hr") | (R.hr_gate == 0.5))])]):
        m = sub[(sub.feature == feat) & (sub.cycle == 1)]; rng = np.random.default_rng(j)
        ret = m[m.status == "returned"]; cen = m[m.status == "censored"]; ne = m[m.status == "not_estimable"]
        ax.scatter(j + rng.uniform(-.2, .2, len(ret)), ret.return_time, s=14, color="#1f4e79"); ax.scatter(j + rng.uniform(-.2, .2, len(cen)), np.full(len(cen), 380), s=16, marker="^", color="#c44e52")
        ax.text(j, 400, f"{len(ret)}/{len(cen)}/{len(ne)}", ha="center", fontsize=7)
    ax.set_xticks(range(5)); ax.set_xticklabels(["primary", "band 1.5", "band 2.5", "k=2", "ref B"], fontsize=8); ax.set_ylim(0, 430); ax.set_title(f"{title}, cycle 1: return time by definition\n(text = returned/censored/not estimable; triangles = right-censored at 360 s)", fontsize=8)
axes[0].set_ylabel("time to sustained return (s)")
fig.tight_layout(); fig.savefig("results/figures/figR2_recovery_distributions.png", dpi=150); plt.close(fig)
print(json.dumps({k: V[k] for k in ["baseline_error_by_minute_median", "baseline_error_trend", "end_of_recovery_vs_end_of_baseline", "challenge2_vs_challenge1", "rank_stability_vs_primary_definition"]}, indent=1, default=float))
print(pd.DataFrame(V["primary_definition"]).T.round(2).to_string())
print("sensitivity (returned/censored):"); print(pd.DataFrame({n: {k: f"{v['returned']}/{v['censored']}" for k, v in s.items()} for n, s in sens.items()}).to_string())
