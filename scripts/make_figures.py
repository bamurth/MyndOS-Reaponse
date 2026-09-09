"""Four static figures from the tracked tables/features. Full cohorts, no hand-picked participants."""
import sys, json
sys.path.insert(0, "src")
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from myndos.io_ds007554 import TASKS

df = pd.read_parquet("data/features/ds007554_bins.parquet")
eeg_cols = [c for c in df.columns if c.startswith("eeg_") and c not in ("eeg_ok", "eeg_bad_ch_frac")]
df.loc[~df.eeg_ok, eeg_cols] = np.nan
R = pd.read_csv("results/tables/ds007554_file_metrics.csv")
S = json.load(open("results/tables/ds007554_summary.json"))
E = pd.read_csv("results/tables/eegmat_participant_metrics.csv")
ES = json.load(open("results/tables/eegmat_summary.json"))
groups = {"low demand (passive motor, motor imagery)": ["passivemotor", "motorimagery"], "motor (active motor)": ["activemotor"],
          "cognitive (arithmetic, 2-back)": ["mentalarithmetic", "nback"], "combined (2-back+arithmetic, full)": ["nbackarithmetic", "full"]}
colors = ["#7f7f7f", "#4c72b0", "#dd8452", "#c44e52"]
# time axis relative to task onset (25 s on the EEG clock)
df["rel"] = df.t_end - 25.0

# ---- Figure 1: event-aligned response on the EEG clock, cohort medians by demand group; HR on event-matched files
fig, axes = plt.subplots(1, 3, figsize=(14, 4))
for ax, (c, lab) in zip(axes[:2], [("eeg_parietal_alpha", "Parietal log10 alpha power (uV^2)"), ("eeg_frontal_theta", "Frontal log10 theta power (uV^2)")]):
    for (gname, tasks), col in zip(groups.items(), colors):
        g = df[df.task.isin(tasks)]
        med = g.groupby("rel")[c].median(); q1 = g.groupby("rel")[c].quantile(.25); q3 = g.groupby("rel")[c].quantile(.75)
        ax.plot(med.index, med.values, color=col, lw=2, label=f"{gname} (files={g.file.nunique()})")
        ax.fill_between(med.index, q1.values, q3.values, color=col, alpha=0.12)
    ax.axvspan(-25, 0, color="k", alpha=0.05); ax.axvline(0, color="k", ls="--", lw=1); ax.axvline(180, color="k", ls=":", lw=1)
    ax.set_xlabel("seconds from task onset (EEG clock)"); ax.set_title(lab, fontsize=10)
axes[0].legend(fontsize=7, loc="lower left")
m = df[df.clock_source == "event_matched"]
for pid, g in m.groupby("file"):
    axes[2].plot(g.rel, g.hr, color="#c44e52", alpha=0.15, lw=0.8)
med = m.groupby("rel").hr.median(); axes[2].plot(med.index, med.values, color="#c44e52", lw=2.2, label=f"median, event-matched files (n={m.file.nunique()}, participants={m.pid.nunique()})")
axes[2].axvspan(-25, 0, color="k", alpha=0.05); axes[2].axvline(0, color="k", ls="--", lw=1); axes[2].axvline(180, color="k", ls=":", lw=1)
axes[2].set_title("Heart rate (bpm, ECG) on the EEG clock via event-matched offset", fontsize=10); axes[2].legend(fontsize=7); axes[2].set_xlabel("seconds from task onset")
fig.suptitle(f"ds007554 (CMx7-MM): concurrent EEG and ECG around a 3-min task, all {df.file.nunique()} files, {df.pid.nunique()} participants; medians with IQR. Recovery not observable (files end 11 s after task).", fontsize=9)
fig.tight_layout(); fig.savefig("results/figures/fig1_event_aligned_response.png", dpi=150); plt.close(fig)

# ---- Figure 2: participant-level response timing including non-departures (censored); recovery not estimable
fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
for ax, c in zip(axes, ["eeg_parietal_alpha", "eeg_frontal_theta"]):
    piv = R.pivot_table(index="pid", columns="task", values=f"{c}_t_depart_b2.0", aggfunc="median")
    piv = piv.reindex(columns=[t for t in TASKS if t in piv.columns])
    for j, t in enumerate(piv.columns):
        v = piv[t]; dep = v.dropna(); nd = v[v.isna()]
        ax.scatter(np.full(len(dep), j) + np.random.default_rng(j).uniform(-.18, .18, len(dep)), dep.values, s=14, color="#4c72b0", alpha=.7)
        ax.scatter(np.full(len(nd), j) + np.random.default_rng(j + 9).uniform(-.18, .18, len(nd)), np.full(len(nd), 190), s=14, marker="^", color="#c44e52", alpha=.7)
        ax.text(j, 196, f"{len(nd)}/{len(v)}\nno dep.", ha="center", fontsize=7)
    ax.set_xticks(range(len(piv.columns))); ax.set_xticklabels(piv.columns, rotation=30, fontsize=8); ax.set_ylim(0, 210)
    ax.axhline(180, color="k", ls=":", lw=1); ax.set_ylabel("first sustained departure from session rest band (s after onset)")
    ax.set_title(f"{c}\nper-participant median over sessions; red triangles = no departure (censored at 180 s)", fontsize=8)
fig.suptitle("ds007554: response timing (band = +-2 robust units of the session's pooled rest, 3 consecutive valid 10-s bins). Recovery: NOT ESTIMABLE (no post-task rest).", fontsize=9)
fig.tight_layout(); fig.savefig("results/figures/fig2_participant_timing_censoring.png", dpi=150); plt.close(fig)

# ---- Figure 3: burden vs performance (ds007554 event-matched files; EEGMAT change vs counting performance)
fig, axes = plt.subplots(1, 3, figsize=(14, 4))
mm = R[(R.clock_source == "event_matched") & R.error_rate_task.notna()]
axes[0].scatter(mm.eeg_parietal_alpha_burden, mm.error_rate_task, c=["#4c72b0" if t == "nback" else "#c44e52" for t in mm.task], s=22)
axes[0].set_xlabel("parietal alpha burden during task (|z| x s)"); axes[0].set_ylabel("task error rate (misses+false alarms per event)")
axes[0].set_title(f"ds007554 event-matched files (n={len(mm)}, participants={mm.pid.nunique()})\nblue=2-back, red=2-back+arithmetic", fontsize=8)
axes[1].scatter(mm.hr_resp_own_rest_phys, mm.error_rate_task, c=["#4c72b0" if t == "nback" else "#c44e52" for t in mm.task], s=22)
axes[1].set_xlabel("HR task minus own pre-task rest (bpm)"); axes[1].set_ylabel("task error rate"); axes[1].set_title("cardiac response vs performance (same files)", fontsize=8)
axes[2].scatter(E.hr_delta, E["Number of subtractions"], s=22, color="#c44e52", label="HR change (bpm)")
ax2 = axes[2].twiny(); ax2.scatter(E.eeg_parietal_alpha_delta, E["Number of subtractions"], s=22, color="#4c72b0", marker="s", label="parietal alpha change (log10)")
axes[2].set_xlabel("EEGMAT: HR task minus baseline (bpm), red"); ax2.set_xlabel("parietal log10 alpha change, blue squares"); axes[2].set_ylabel("subtractions per 4 min")
rho = ES["associations"]; axes[2].set_title(f"EEGMAT N=36: Spearman rho HR {rho['hr']['spearman_rho_vs_subtractions']:.2f} (n={rho['hr']['n']}), alpha {rho['eeg_parietal_alpha']['spearman_rho_vs_subtractions']:.2f}", fontsize=8)
fig.suptitle("Burden / response magnitude versus measured performance. No relationship is claimed unless the tables support it.", fontsize=9)
fig.tight_layout(); fig.savefig("results/figures/fig3_burden_vs_performance.png", dpi=150); plt.close(fig)

# ---- Figure 4: added-value comparison (participant-weighted MAE with paired bootstrap CI vs context model)
P = S["prediction"]
fig, ax = plt.subplots(figsize=(10, 4.2))
if "participant_weighted_mae" in P:
    order = ["persistence", "condition_time_only", "context_past_performance", "context_plus_peripheral", "context_plus_peripheral_plus_eeg", "control_mismatched_physiology", "control_temporal_shift_3bins"]
    means = [P["participant_weighted_mae"][k]["mean"] for k in order]
    ax.bar(range(len(order)), means, color=["#7f7f7f", "#7f7f7f", "#4c72b0", "#dd8452", "#c44e52", "#bbbbbb", "#bbbbbb"])
    for i, k in enumerate(order):
        if k in P["paired_difference_vs_context_past_performance"]:
            d = P["paired_difference_vs_context_past_performance"][k]
            ax.text(i, means[i] + 0.002, f"diff vs context\n{d['mean']:+.4f}\n[{d['ci_low']:+.4f}, {d['ci_high']:+.4f}]", ha="center", fontsize=7)
    ax.set_xticks(range(len(order))); ax.set_xticklabels([k.replace("_", "\n") for k in order], fontsize=7)
    ax.set_ylabel("participant-weighted MAE of next-30-s error rate"); ax.set_ylim(0, max(means) * 1.35)
    ax.set_title(f"ds007554 held-out added-value test: {P['status']}. N={P['n_participants']} participants, {P['n_files']} files, {P['n_rows']} windows; target mean {P['target_mean']:.3f}, sd {P['target_sd']:.3f}", fontsize=8)
else:
    ax.text(0.5, 0.5, f"NOT RUN: {P['status']}", ha="center", va="center", fontsize=14); ax.axis("off")
fig.tight_layout(); fig.savefig("results/figures/fig4_added_value_comparison.png", dpi=150); plt.close(fig)
print("figures written")
