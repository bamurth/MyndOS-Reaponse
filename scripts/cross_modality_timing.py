"""Figure R3: cross-modality recovery timing (cycle 1) on the PRIMARY dataset, with censoring and not-estimable states shown.
Inputs: results/tables/recovery_endpoints.csv (behaviour, HR, EDA; primary definition), results/tables/matb_eeg_participant_metrics.csv.
Output: results/figures/figR3_cross_modality_timing.png, results/tables/cross_modality_timing.csv
"""
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
R = pd.read_csv("results/tables/recovery_endpoints.csv")
m = R[(R.bin_s == 10) & (R.reference == "A") & (R.band == 2.0) & (R.k == 3) & ((R.feature != "hr") | (R.hr_gate == 0.5)) & (R.cycle == 1)]
rows = []
for feat, lab in (("abs_err", "behaviour (target error)"), ("hr", "heart rate (wrist, gated)"), ("eda", "EDA (wrist)"), ("motion", "motion (wrist)")):
    g = m[m.feature == feat].set_index("pid")
    for pid, r in g.iterrows(): rows.append({"pid": pid, "modality": lab, "t_depart_s": r.t_depart, "return_time_s": r.return_time, "status": r.status})
E = pd.read_csv("results/tables/matb_eeg_participant_metrics.csv")
for feat, lab in (("eeg_frontal_theta", "EEG frontal theta"), ("eeg_parietal_alpha", "EEG parietal alpha"), ("eeg_central_beta", "EEG central beta")):
    g = E[(E.feature == feat) & (E.cycle == 1)]
    for _, r in g.iterrows(): rows.append({"pid": r.pid, "modality": lab, "t_depart_s": r["t_depart_b2.0"], "return_time_s": r["return_time_b2.0"], "status": r["status_b2.0"]})
T = pd.DataFrame(rows); T.to_csv("results/tables/cross_modality_timing.csv", index=False)
order = ["behaviour (target error)", "heart rate (wrist, gated)", "EDA (wrist)", "motion (wrist)", "EEG frontal theta", "EEG parietal alpha", "EEG central beta"]
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
for ax, col, title in ((axes[0], "t_depart_s", "first sustained departure after demand INCREASE (s)"), (axes[1], "return_time_s", "sustained return after demand DECREASE (s)")):
    for j, mod in enumerate(order):
        g = T[T.modality == mod]; rng = np.random.default_rng(j); v = g[col]
        ok = v.notna(); ax.scatter(j + rng.uniform(-.22, .22, ok.sum()), v[ok], s=14, color="#1f4e79", alpha=.8)
        if col == "return_time_s":
            cen = g.status == "censored"; ne = g.status == "not_estimable"; amb = g.status == "ambiguous_timing"
            ax.scatter(j + rng.uniform(-.22, .22, cen.sum()), np.full(cen.sum(), 380), s=16, marker="^", color="#c44e52")
            ax.text(j, 405, f"ret {ok.sum()}\ncens {cen.sum()}\nn.e. {ne.sum()}\namb {amb.sum()}", ha="center", fontsize=6.5)
        else:
            ax.text(j, 375, f"departed {ok.sum()}/{len(g)}", ha="center", fontsize=6.5)
        if ok.sum(): ax.hlines(v[ok].median(), j - .3, j + .3, color="#c44e52", lw=2)
    ax.set_xticks(range(len(order))); ax.set_xticklabels(order, rotation=25, ha="right", fontsize=7); ax.set_ylim(0, 440); ax.set_title(title, fontsize=9)
axes[0].set_ylabel("seconds (band +-2 robust units of the final 3 min of baseline; 3 consecutive valid 10-s bins)")
fig.suptitle("PRIMARY MATB-II, cycle 1, N = 35 per modality: cross-system timing. Red bar = median among estimable; triangles = right-censored at 360 s.\nSensor lags not corrected: wrist HR is a vendor ~10-s running estimate, EDA responds over seconds, behaviour is a 10-s snapshot, EEG is zero-phase filtered. Differences < 20 s are within lag.", fontsize=8)
fig.tight_layout(); fig.savefig("results/figures/figR3_cross_modality_timing.png", dpi=150); plt.close(fig)
print(T.groupby("modality").status.value_counts().unstack(fill_value=0).reindex(order).to_string()); print(T.groupby("modality")[["t_depart_s", "return_time_s"]].median().reindex(order).round(0).to_string())
