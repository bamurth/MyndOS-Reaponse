"""PRIMARY dataset pipeline (neuro-stress-resilience-hci 1.0.0, Roy & Nuamah): PLAN.md Checkpoint 1.

Wrist (Empatica E4) physiology + MATB-II RESMAN performance for the full cohort. EEG is handled by
scripts/matb_eeg.py (Checkpoint 2). Raw files live under data/raw/matb/{PPG/pXX, MATB-II} (gitignored),
fetched by scripts/download_matb.sh and verified against the official SHA256SUMS.txt.

Chronology (frozen before any outcome was inspected):
* Task time zero = the E4 tag (README: "Event marker (Working Baseline start)"); MATB-II ELAPSED_TIME
  counts from the same instant. t_epoch = tag + elapsed. No clock offset is inferred from signals.
* Blocks: 5 x 360 s from the tag (working_baseline, challenge_1, recovery_1, challenge_2, recovery_2),
  matching the 1,790-1,800 s span of every RESMAN log. Quiet rest = up to 60 s before the tag.
* Exclusion: no tag; more than one tag whose extras do not sit at expected 360-s transitions (+-10 s);
  E4 session shorter than tag + 1,790 s; MATB log shorter than 1,790 s or with cadence anomalies inside
  a block used for timing; missing E4 file -> that feature only.
Analysis choices (PLAN.md): trailing 10-s bins that never cross block boundaries; reference A = final three
valid minutes of working baseline (elapsed > 180 s); sensitivity B = whole working baseline; for cycle 2 the
immediately preceding state (C = final three minutes of recovery 1) is reported separately; median/1.4826*MAD
with near-zero flag; band +-2 (sensitivity 1.5/2.5), k = 3 consecutive valid bins; recovery residual at
60/180/360 s; censoring; no HRV (IBI is sparse); no EEG here.
Pulse quality (frozen after inspecting raw BVP of p01/p02/p05/p09 only, before any outcome): the vendor HR.csv keeps
emitting values when the PPG carries no pulse (p01 shows 100-165 bpm with 1.5 % accepted beats). A 10-s bin's HR is
valid only when Empatica's own accepted inter-beat intervals (IBI.csv) cover >= 50 % of that bin; hr_e4_raw is kept
for transparency and hr_ibi (60 / mean accepted IBI) as a sensitivity column.
Scale floors (frozen, resolution-based): the robust scale is never allowed below hr 1 bpm, eda 0.02 uS, temp 0.05 degC,
motion 0.02 (1/64 g), abs_err 5 fuel units; a floored reference is flagged (scale_flag).
Tags: a cluster of button presses within 10 s is one double-press; the first press is used and the spread is recorded
as tag_uncertainty_s; timing estimates are dropped when it exceeds 5 s. Extra tags outside a cluster and not at an
expected 360-s transition exclude the participant.
"""
import sys, os, glob, json
sys.path.insert(0, "src")
import numpy as np, pandas as pd
from scipy import stats
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from myndos.io_matb import (read_e4_regular, read_e4_ibi, read_e4_tags, read_matb_resman, matb_cadence_anomalies,
                            expected_matb_segments)
from myndos.binning import make_bins
from myndos.metrics import robust_reference, normalize, response_magnitude, first_sustained_departure, burden, recovery
from myndos.modeling import (make_targets, nested_ridge_predict, participant_mae, paired_bootstrap,
                             shuffle_physiology_across_participants, temporal_shift_within_person)

SEED = 0
ROOT = "data/raw/matb"
BLOCKS = ["working_baseline", "challenge_1", "recovery_1", "challenge_2", "recovery_2"]
FEATS = ["hr", "eda", "motion", "temp", "abs_err"]
SCALE_FLOOR = {"hr": 1.0, "eda": 0.02, "temp": 0.05, "motion": 0.02, "abs_err": 5.0}
IBI_MIN_COV = 0.5
UNITS = {"hr": "bpm (E4 HR.csv, bins with >=50% accepted-beat coverage)", "eda": "uS", "motion": "1/64 g per sample (mean |d acc|)", "temp": "degC", "abs_err": "fuel units from 2500 target"}
BANDS = (1.5, 2.0, 2.5)
BLOCK_S = 360.0; BIN = 10.0; MIN_TASK_S = 1790.0
os.makedirs("results/audit", exist_ok=True); os.makedirs("results/tables", exist_ok=True)
os.makedirs("results/figures", exist_ok=True); os.makedirs("data/features", exist_ok=True)


def participants():
    return sorted(os.path.basename(p) for p in glob.glob(f"{ROOT}/PPG/p*") if os.path.isdir(p))


# ------------------------------------------------------------------ audit ------------------------------------
def audit_participant(pid: str) -> tuple[dict, dict]:
    pdir = f"{ROOT}/PPG/{pid}"; a = {"participant": pid}; sig = {}
    reasons = []
    for name in ["EDA", "HR", "BVP", "ACC", "TEMP"]:
        p = f"{pdir}/{name}.csv"
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            a[f"{name}_present"] = False; continue
        t, v, t0, fs = read_e4_regular(p); sig[name] = (t, v, t0, fs)
        a[f"{name}_present"] = True; a[f"{name}_t0"] = t0; a[f"{name}_fs"] = fs; a[f"{name}_n"] = int(v.shape[0])
        a[f"{name}_duration_s"] = float(v.shape[0] / fs); a[f"{name}_n_nan"] = int(np.isnan(v).sum())
    t0s = {k: sig[k][2] for k in sig if k != "HR"}
    a["session_t0"] = float(min(t0s.values())) if t0s else np.nan
    a["t0_spread_nonHR_s"] = float(max(t0s.values()) - min(t0s.values())) if t0s else np.nan
    a["HR_t0_minus_session_t0_s"] = float(sig["HR"][2] - a["session_t0"]) if "HR" in sig and t0s else np.nan
    a["session_end_s"] = float(max(sig[k][0][-1] for k in sig) - a["session_t0"]) if sig else np.nan
    if os.path.exists(f"{pdir}/IBI.csv") and os.path.getsize(f"{pdir}/IBI.csv") > 0:
        tt, ibi, _ = read_e4_ibi(f"{pdir}/IBI.csv"); sig["IBI"] = (tt, ibi)
        a["IBI_n"] = int(ibi.size); a["IBI_sum_s"] = float(ibi.sum())
    else:
        a["IBI_n"] = 0; a["IBI_sum_s"] = 0.0
    tags = read_e4_tags(f"{pdir}/tags.csv"); a["n_tags"] = int(tags.size)
    a["tags_rel_session_s"] = ";".join(f"{x - a['session_t0']:.2f}" for x in tags) if tags.size and np.isfinite(a["session_t0"]) else ""
    if tags.size == 0:
        reasons.append("no working-start tag")
        a["working_start_epoch"] = np.nan
    else:
        a["working_start_epoch"] = float(tags[0])
        rel = tags - tags[0]
        cluster = rel[rel <= 10.0]; a["tag_uncertainty_s"] = float(cluster.max())  # double-press spread (0 if single)
        extras = rel[rel > 10.0]
        ok = [np.min(np.abs(e - np.arange(1, 6) * BLOCK_S)) <= 10.0 for e in extras]
        a["extra_tags_at_transitions"] = all(ok) if extras.size else True
        if extras.size and not all(ok):
            reasons.append(f"{extras.size} extra tag(s) not at expected transitions: {np.round(extras, 1).tolist()}")
        a["timing_estimable"] = a["tag_uncertainty_s"] <= 5.0
    a["quiet_rest_before_tag_s"] = float(a["working_start_epoch"] - a["session_t0"]) if tags.size and t0s else np.nan
    a["e4_coverage_after_tag_s"] = float(a["session_end_s"] - a["quiet_rest_before_tag_s"]) if tags.size and t0s else np.nan
    if tags.size and t0s and a["e4_coverage_after_tag_s"] < MIN_TASK_S:
        reasons.append(f"E4 covers only {a['e4_coverage_after_tag_s']:.0f} s after the tag (< {MIN_TASK_S:.0f})")
    a["IBI_coverage_of_task"] = float(a["IBI_sum_s"] / MIN_TASK_S)
    # signal sanity
    if "EDA" in sig:
        v = sig["EDA"][1]; a["EDA_frac_zero"] = float(np.mean(v == 0)); a["EDA_min"] = float(np.nanmin(v)); a["EDA_max"] = float(np.nanmax(v))
    if "BVP" in sig:
        v = sig["BVP"][1]; a["BVP_absmax"] = float(np.nanmax(np.abs(v))); a["BVP_frac_flat"] = float(np.mean(np.diff(v) == 0))
    if "TEMP" in sig:
        v = sig["TEMP"][1]; a["TEMP_min"] = float(np.nanmin(v)); a["TEMP_max"] = float(np.nanmax(v))
        if a["TEMP_max"] < 25 or a["TEMP_min"] > 40: reasons.append("TEMP outside 25-40 degC: wristband contact suspect")
    if "HR" in sig:
        v = sig["HR"][1]; a["HR_min"] = float(np.nanmin(v)); a["HR_max"] = float(np.nanmax(v))
    # MATB
    mp = f"{ROOT}/MATB-II/{pid}resman.csv"; a["MATB_present"] = os.path.exists(mp)
    if a["MATB_present"]:
        m = read_matb_resman(mp); sig["MATB"] = m
        a["MATB_rows"] = int(len(m)); a["MATB_first_s"] = float(m.t_task_s.iloc[0]); a["MATB_last_s"] = float(m.t_task_s.iloc[-1])
        anom = matb_cadence_anomalies(m.t_task_s.to_numpy()); a["MATB_cadence_anomalies"] = ";".join(f"{m.t_task_s.iloc[i]:.1f}" for i in anom)
        a["MATB_diff_consistent"] = bool(m.diff_consistent.all()); a["MATB_n_nan"] = int(m[["diff_a", "diff_b"]].isna().sum().sum())
        if a["MATB_last_s"] < MIN_TASK_S: reasons.append(f"MATB log ends at {a['MATB_last_s']:.0f} s")
        if anom.size: reasons.append("MATB cadence anomalies")
    else:
        reasons.append("no MATB log")
    a["exclude_reason"] = "; ".join(reasons)
    a["usable"] = not reasons
    a["alignment_rule"] = "t_epoch = E4 tag + MATB elapsed; blocks 5x360 s from tag; no signal-derived offset"
    return a, sig


# ------------------------------------------------------------------ bins -------------------------------------
def bin_features(pid: str, a: dict, sig: dict) -> pd.DataFrame:
    ws = a["working_start_epoch"]
    segs = expected_matb_segments(ws, BLOCK_S)
    if a["quiet_rest_before_tag_s"] >= 30:
        segs = [(ws - min(60.0, a["quiet_rest_before_tag_s"]), ws, "quiet_rest")] + segs
    bins = make_bins(segs, width=BIN)
    ibi_t, ibi = sig.get("IBI", (np.array([]), np.array([])))
    t_hr, hr, _, _ = sig["HR"] if "HR" in sig else (np.array([]),) * 4
    t_ed, eda, _, _ = sig["EDA"] if "EDA" in sig else (np.array([]),) * 4
    t_tp, tp, _, _ = sig["TEMP"] if "TEMP" in sig else (np.array([]),) * 4
    if "ACC" in sig:
        t_ac, acc, _, _ = sig["ACC"]; mag = np.linalg.norm(acc, axis=1); mot = np.abs(np.diff(mag)); t_mot = t_ac[1:]
    else:
        t_mot, mot = np.array([]), np.array([])
    m = sig["MATB"]; mt = m.t_task_s.to_numpy(); merr = m.abs_err.to_numpy()
    rows = []
    for b in bins.itertuples():
        r = {"pid": pid, "file": pid, "condition": b.condition, "seg_index": b.seg_index, "elapsed": b.elapsed,
             "t_end": b.t_end - ws, "cycle": {"challenge_1": 1, "recovery_1": 1, "challenge_2": 2, "recovery_2": 2}.get(b.condition, 0)}
        s = (t_hr >= b.t_start) & (t_hr < b.t_end); r["hr_e4_raw"] = float(np.nanmean(hr[s])) if s.sum() >= 8 else np.nan
        si = (ibi_t >= b.t_start) & (ibi_t < b.t_end); cov = float(ibi[si].sum() / BIN) if ibi.size else 0.0
        r["hr"] = r["hr_e4_raw"] if cov >= IBI_MIN_COV else np.nan
        r["hr_ibi"] = float(60.0 / np.mean(ibi[si])) if cov >= IBI_MIN_COV and si.sum() >= 5 else np.nan
        s = (t_ed >= b.t_start) & (t_ed < b.t_end); r["eda"] = float(np.nanmedian(eda[s])) if s.sum() >= 32 else np.nan
        r["eda_flat"] = bool(s.sum() >= 32 and np.nanmax(eda[s]) - np.nanmin(eda[s]) == 0)
        s = (t_tp >= b.t_start) & (t_tp < b.t_end); r["temp"] = float(np.nanmean(tp[s])) if s.sum() >= 32 else np.nan
        s = (t_mot >= b.t_start) & (t_mot < b.t_end); r["motion"] = float(np.nanmean(mot[s])) if s.sum() >= 256 else np.nan
        r["ibi_cov"] = cov
        # MATB snapshot at the bin end (task clock); NaN for quiet rest and when no snapshot within 0.5 s
        te = b.t_end - ws
        k = np.flatnonzero(np.abs(mt - te) <= 0.5)
        r["abs_err"] = float(merr[k[0]]) if k.size and b.condition != "quiet_rest" else np.nan
        rows.append(r)
    df = pd.DataFrame(rows)
    df.loc[df.eda_flat, "eda"] = np.nan  # flat 10-s EDA = sensor not reading
    return df


# ------------------------------------------------------------------ metrics ----------------------------------
def floored_reference(x, feature):
    med, sc, flag = robust_reference(np.asarray(x, float))
    if np.isfinite(sc) and sc < SCALE_FLOOR[feature]:
        sc, flag = SCALE_FLOOR[feature], True
    return med, sc, flag


def participant_metrics(pid: str, g: pd.DataFrame, timing_ok: bool = True) -> list[dict]:
    out = []
    base = g[g.condition == "working_baseline"]
    refA = base[base.elapsed > 180.0]; refB = base; refC = g[(g.condition == "recovery_1") & (g.elapsed > 180.0)]
    for c in FEATS:
        medA, scA, flA = floored_reference(refA[c], c); medB, scB, flB = floored_reference(refB[c], c)
        medC, scC, flC = floored_reference(refC[c], c)
        for cyc in (1, 2):
            ch = g[g.condition == f"challenge_{cyc}"].sort_values("elapsed"); rc = g[g.condition == f"recovery_{cyc}"].sort_values("elapsed")
            r = {"pid": pid, "feature": c, "unit": UNITS[c], "cycle": cyc, "n_ref_bins": int(refA[c].notna().sum()),
                 "ref_median": medA, "ref_scale": scA, "scale_flag": flA, "n_challenge_valid": int(ch[c].notna().sum()), "n_recovery_valid": int(rc[c].notna().sum()),
                 "resp_phys": response_magnitude(ch[c].to_numpy(), refA[c].to_numpy()), "resp_phys_refB": response_magnitude(ch[c].to_numpy(), refB[c].to_numpy()),
                 "challenge_median": float(np.nanmedian(ch[c])) if ch[c].notna().any() else np.nan, "recovery_median": float(np.nanmedian(rc[c])) if rc[c].notna().any() else np.nan}
            zc = normalize(ch[c].to_numpy(), medA, scA); zr = normalize(rc[c].to_numpy(), medA, scA)
            r["resp_z"] = float(np.nanmedian(zc)) if np.isfinite(zc).any() else np.nan
            r["burden"] = burden(zc, BIN); r["burden_recovery"] = burden(zr, BIN)
            for band in BANDS:
                td = first_sustained_departure(zc, ch.elapsed.to_numpy(), band=band, k=3); r[f"t_depart_b{band}"] = td
                rec = recovery(zr, rc.elapsed.to_numpy(), band=band, k=3, excursion=np.isfinite(td))
                r[f"return_time_b{band}"] = rec["return_time"]; r[f"status_b{band}"] = rec["status"]
                if band == 2.0:
                    for s in (60, 180, 360): r[f"residual_{s}"] = rec[f"residual_{s}"]
            # sensitivity B (whole baseline) at band 2
            zcB = normalize(ch[c].to_numpy(), medB, scB); zrB = normalize(rc[c].to_numpy(), medB, scB)
            tdB = first_sustained_departure(zcB, ch.elapsed.to_numpy(), band=2.0, k=3); recB = recovery(zrB, rc.elapsed.to_numpy(), band=2.0, k=3, excursion=np.isfinite(tdB))
            r["t_depart_refB"] = tdB; r["return_time_refB"] = recB["return_time"]; r["status_refB"] = recB["status"]; r["scale_flag_refB"] = flB
            # cycle 2 relative to the immediately preceding state (reference C = final 3 min of recovery 1)
            if cyc == 2:
                r["resp_phys_preref"] = response_magnitude(ch[c].to_numpy(), refC[c].to_numpy()); r["scale_flag_preref"] = flC
                zcC = normalize(ch[c].to_numpy(), medC, scC); zrC = normalize(rc[c].to_numpy(), medC, scC)
                tdC = first_sustained_departure(zcC, ch.elapsed.to_numpy(), band=2.0, k=3); recC = recovery(zrC, rc.elapsed.to_numpy(), band=2.0, k=3, excursion=np.isfinite(tdC))
                r["t_depart_preref"] = tdC; r["return_time_preref"] = recC["return_time"]; r["status_preref"] = recC["status"]; r["burden_preref"] = burden(zcC, BIN)
            r["timing_estimable"] = timing_ok
            if not timing_ok:  # ambiguous working-start tag: magnitudes kept, timing dropped
                for k in list(r):
                    if k.startswith(("t_depart", "return_time")): r[k] = np.nan
                    if k.startswith("status"): r[k] = "ambiguous_timing"
            out.append(r)
    return out


# ------------------------------------------------------------------ figures ----------------------------------
SHADE = {"quiet_rest": "#dddddd", "challenge_1": "#f4c7c3", "challenge_2": "#f4c7c3"}


def shade_blocks(ax, df_one):
    for cond, gg in df_one.groupby("condition"):
        if cond in SHADE: ax.axvspan(gg.t_end.min() - BIN, gg.t_end.max(), color=SHADE[cond], alpha=0.5, lw=0)
    for k in range(1, 5): ax.axvline(k * BLOCK_S, color="k", lw=0.6, ls=":")


def fig_first_participant(df, M, pid):
    g = df[df.pid == pid]
    fig, axes = plt.subplots(len(FEATS), 1, figsize=(12, 11), sharex=True)
    for ax, c in zip(axes, FEATS):
        shade_blocks(ax, g); ax.plot(g.t_end, g[c], color="#1f4e79", lw=1.2, marker=".", ms=3)
        m1 = M[(M.pid == pid) & (M.feature == c) & (M.cycle == 1)]
        if len(m1) and np.isfinite(m1.ref_scale.iloc[0]):
            med, sc = m1.ref_median.iloc[0], m1.ref_scale.iloc[0]
            ax.axhspan(med - 2 * sc, med + 2 * sc, color="#a6d96a", alpha=0.25, lw=0, label="reference band +-2 robust units (final 3 min of working baseline)")
            ax.axhline(med, color="#4d9221", lw=0.8)
        ax.set_ylabel(f"{c}\n[{UNITS[c]}]", fontsize=8)
    axes[0].legend(fontsize=7, loc="upper left")
    axes[-1].set_xlabel("seconds since working-baseline start (E4 tag = MATB time zero)")
    fig.suptitle(f"PRIMARY MATB-II {pid}: wrist physiology and RESMAN target error, 10-s bins. Grey = quiet rest, red = challenge (RESMAN+COMMS), white = RESMAN only.", fontsize=9)
    fig.tight_layout(); fig.savefig("results/figures/figM1_first_participant_timecourse.png", dpi=150); plt.close(fig)


def fig_cohort(df, M):
    # z relative to reference A per participant, cohort median + IQR over the full 30-min timeline
    Z = df.copy()
    for c in FEATS:
        ref = M[(M.feature == c) & (M.cycle == 1)].set_index("pid")
        Z[f"z_{c}"] = [(v - ref.ref_median.get(p, np.nan)) / ref.ref_scale.get(p, np.nan) if p in ref.index and np.isfinite(ref.ref_scale.get(p, np.nan)) and ref.ref_scale.get(p, np.nan) > 0 else np.nan for p, v in zip(Z.pid, Z[c])]
    task = Z[Z.condition != "quiet_rest"]
    fig, axes = plt.subplots(len(FEATS), 1, figsize=(12, 11), sharex=True)
    for ax, c in zip(axes, FEATS):
        shade_blocks(ax, task); gg = task.groupby("t_end")[f"z_{c}"]
        med, q1, q3, n = gg.median(), gg.quantile(.25), gg.quantile(.75), gg.count()
        ax.fill_between(med.index, q1, q3, color="#1f4e79", alpha=0.18, lw=0); ax.plot(med.index, med, color="#1f4e79", lw=1.6)
        ax.axhspan(-2, 2, color="#a6d96a", alpha=0.2, lw=0); ax.axhline(0, color="#4d9221", lw=0.8)
        ax.set_ylabel(f"{c}\n(robust units vs ref A)", fontsize=8); ax.text(0.01, 0.85, f"participants per bin: {int(n.min())}-{int(n.max())}", transform=ax.transAxes, fontsize=7)
    axes[-1].set_xlabel("seconds since working-baseline start")
    fig.suptitle(f"PRIMARY MATB-II cohort (N={task.pid.nunique()} usable): median and IQR of per-participant baseline-standardized 10-s bins. Reference A = final 3 min of working baseline.", fontsize=9)
    fig.tight_layout(); fig.savefig("results/figures/figM2_cohort_event_aligned_response.png", dpi=150); plt.close(fig)
    return Z


def fig_recovery(M):
    feats = ["hr", "eda", "motion", "abs_err"]
    fig, axes = plt.subplots(1, len(feats), figsize=(15, 4.6), sharey=True)
    for ax, c in zip(axes, feats):
        for j, cyc in enumerate((1, 2)):
            m = M[(M.feature == c) & (M.cycle == cyc)]
            rng = np.random.default_rng(cyc)
            ret = m[m["status_b2.0"] == "returned"]; cen = m[m["status_b2.0"] == "censored"]; ne = m[m["status_b2.0"] == "not_estimable"]
            ax.scatter(j + rng.uniform(-.2, .2, len(ret)), ret["return_time_b2.0"], s=16, color="#1f4e79", label="returned (3 valid bins in band)" if j == 0 else None)
            ax.scatter(j + rng.uniform(-.2, .2, len(cen)), np.full(len(cen), 375), s=18, marker="^", color="#c44e52", label="no return within 360 s (right-censored)" if j == 0 else None)
            ax.scatter(j + rng.uniform(-.2, .2, len(ne)), np.full(len(ne), 395), s=18, marker="x", color="#7f7f7f", label="no excursion in challenge (not estimable)" if j == 0 else None)
            ax.text(j, 410, f"ret {len(ret)} / cens {len(cen)} / n.e. {len(ne)}", ha="center", fontsize=7)
        ax.set_xticks([0, 1]); ax.set_xticklabels(["cycle 1", "cycle 2"]); ax.set_title(c, fontsize=9); ax.set_ylim(0, 430)
    axes[0].set_ylabel("return time (s after demand decreased)"); axes[0].legend(fontsize=6.5, loc="lower left")
    fig.suptitle("PRIMARY MATB-II: per-participant recovery (band +-2 robust units of reference A; 3 consecutive valid 10-s bins). Censoring and non-excursions shown, never imputed.", fontsize=9)
    fig.tight_layout(); fig.savefig("results/figures/figM3_participant_recovery_censoring.png", dpi=150); plt.close(fig)


def fig_burden_perf(M, perf):
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.3))
    for ax, c in zip(axes[:2], ["hr", "eda"]):
        for cyc, col in ((1, "#1f4e79"), (2, "#c44e52")):
            m = M[(M.feature == c) & (M.cycle == cyc)].set_index("pid"); p = perf.set_index("pid")
            x = m.burden; y = p[f"abs_err_challenge_{cyc}"].reindex(m.index)
            ok = x.notna() & y.notna()
            rho = stats.spearmanr(x[ok], y[ok]).statistic if ok.sum() >= 5 else np.nan
            ax.scatter(x[ok], y[ok], s=18, color=col, label=f"cycle {cyc}: rho={rho:.2f} (n={int(ok.sum())})")
        ax.set_xlabel(f"{c} burden during challenge (|z| x s)"); ax.set_ylabel("mean abs target error during challenge"); ax.legend(fontsize=7)
    p = perf
    axes[2].scatter(p.abs_err_working_baseline, p.abs_err_challenge_1, s=18, color="#1f4e79", label="challenge 1")
    axes[2].scatter(p.abs_err_working_baseline, p.abs_err_challenge_2, s=18, color="#c44e52", label="challenge 2")
    lim = np.nanmax(p[["abs_err_working_baseline", "abs_err_challenge_1", "abs_err_challenge_2"]].to_numpy()) * 1.05
    axes[2].plot([0, lim], [0, lim], color="k", lw=0.6, ls=":"); axes[2].set_xlabel("mean abs target error, working baseline"); axes[2].set_ylabel("mean abs target error, challenge"); axes[2].legend(fontsize=7)
    fig.suptitle(f"PRIMARY MATB-II: physiological burden versus measured RESMAN performance (N={perf.pid.nunique()}). Spearman rho across participants; no relationship is claimed unless the tables support it.", fontsize=9)
    fig.tight_layout(); fig.savefig("results/figures/figM4_burden_vs_performance.png", dpi=150); plt.close(fig)


def fig_added_value(P):
    fig, ax = plt.subplots(figsize=(10, 4.2))
    if "participant_weighted_mae" in P:
        order = [k for k in ["persistence", "condition_time_only", "context_past_performance", "context_plus_peripheral", "control_mismatched_physiology", "control_temporal_shift_3bins"] if k in P["participant_weighted_mae"]]
        means = [P["participant_weighted_mae"][k]["mean"] for k in order]
        ax.bar(range(len(order)), means, color=["#7f7f7f", "#7f7f7f", "#1f4e79", "#dd8452", "#bbbbbb", "#bbbbbb"][:len(order)])
        for i, k in enumerate(order):
            d = P["paired_difference_vs_context_past_performance"].get(k)
            if d: ax.text(i, means[i], f"d={d['mean']:+.1f}\n[{d['ci_low']:+.1f},{d['ci_high']:+.1f}]", ha="center", va="bottom", fontsize=7)
        ax.set_xticks(range(len(order))); ax.set_xticklabels(order, rotation=20, fontsize=7, ha="right"); ax.set_ylabel("participant-weighted MAE (fuel units)")
        ax.set_title(f"PRIMARY MATB-II next-30-s abs target error, held-out participants (N={P['n_participants']}, {P['status']}). Paired participant-bootstrap difference vs context+past performance.", fontsize=8)
    else:
        ax.text(0.5, 0.5, f"NOT RUN: {P.get('status', '')}", ha="center", va="center", transform=ax.transAxes)
    fig.tight_layout(); fig.savefig("results/figures/figM5_added_value_comparison.png", dpi=150); plt.close(fig)


# ------------------------------------------------------------------ prediction --------------------------------
def prediction_test(df: pd.DataFrame, M: pd.DataFrame) -> dict:
    P = df[df.condition != "quiet_rest"].copy().sort_values(["pid", "t_end"])
    P["y"] = make_targets(P, horizon=30.0, value_col="abs_err")
    g = P.groupby("pid", sort=False)
    P["perf_last30"] = g.abs_err.transform(lambda s: s.rolling(3, min_periods=1).mean())
    P["perf_cum"] = g.abs_err.transform(lambda s: s.expanding().mean())
    P["perf_slope"] = g.abs_err.transform(lambda s: s.rolling(6, min_periods=3).apply(lambda v: np.polyfit(np.arange(len(v)), v, 1)[0], raw=True))
    P["is_challenge"] = P.condition.str.startswith("challenge").astype(float)
    for c in ["hr", "eda", "motion", "temp"]:
        P[f"{c}_last30"] = g[c].transform(lambda s: s.rolling(3, min_periods=1).mean())
        ref = M[(M.feature == c) & (M.cycle == 1)].set_index("pid")
        P[f"{c}_z"] = [(v - ref.ref_median.get(p, np.nan)) / ref.ref_scale.get(p, np.nan) if p in ref.index and np.isfinite(ref.ref_scale.get(p, np.nan)) and ref.ref_scale.get(p, np.nan) > 0 else np.nan for p, v in zip(P.pid, P[c])]
    ctx = ["is_challenge", "cycle", "elapsed", "seg_index", "perf_last30", "perf_cum", "perf_slope"]
    periph = [f"{c}{s}" for c in ["hr", "eda", "motion", "temp"] for s in ("", "_last30", "_z")] + ["ibi_cov", "hr_e4_raw"]
    D = P.dropna(subset=["y", "perf_last30"]).copy(); n_pid = D.pid.nunique()
    out = {"n_rows": int(len(D)), "n_participants": int(n_pid), "horizon_s": 30, "seed": SEED,
           "target": "mean RESMAN abs target error over the next 30 s (3 snapshots), within condition",
           "note": "Personal reference (ref A) used for *_z features is the pre-challenge working baseline of the same participant (disclosed calibration); it uses no future bins of any target.",
           "status": "run" if n_pid >= 20 else f"insufficient-N (n_participants={n_pid} < 20): exploratory only"}
    if n_pid < 8:
        return out
    y = D.y.to_numpy(); pids = D.pid.to_numpy()
    def run(cols, data=None, seed=SEED):
        X = (data if data is not None else D)[cols].to_numpy(float)
        return nested_ridge_predict(X, y, pids, n_outer=min(10, n_pid), n_inner=min(5, n_pid - 2), seed=seed)
    preds = {"persistence": D.perf_last30.to_numpy(), "condition_time_only": run(["is_challenge", "cycle", "elapsed", "seg_index"]),
             "context_past_performance": run(ctx), "context_plus_peripheral": run(ctx + periph)}
    S = shuffle_physiology_across_participants(D.assign(elapsed_bin=(D.elapsed // 30).astype(int)), periph, ["condition", "elapsed_bin"], seed=SEED)
    preds["control_mismatched_physiology"] = run(ctx + periph, S)
    T = temporal_shift_within_person(D, periph, shift_bins=3); preds["control_temporal_shift_3bins"] = run(ctx + periph, T)
    maes = {k: participant_mae(y, v, pids) for k, v in preds.items()}; ref = maes["context_past_performance"]
    out["participant_weighted_mae"] = {k: {"mean": float(v.mean()), "sd": float(v.std())} for k, v in maes.items()}
    out["paired_difference_vs_context_past_performance"] = {k: paired_bootstrap(v - ref, seed=SEED) for k, v in maes.items() if k != "context_past_performance"}
    out["target_mean"] = float(np.mean(y)); out["target_sd"] = float(np.std(y))
    pd.DataFrame(maes).to_csv("results/tables/matb_prediction_participant_mae.csv")
    return out


# ------------------------------------------------------------------ main -------------------------------------
def main(only: list[str] | None = None):
    pids = participants() if not only else only
    if not pids:
        print("PRIMARY DATA ABSENT: data/raw/matb/PPG has no participant folders. Run scripts/download_matb.sh."); return 0
    audits, frames = [], []
    for pid in pids:
        a, sig = audit_participant(pid); audits.append(a)
        if a["usable"]:
            frames.append(bin_features(pid, a, sig))
    A = pd.DataFrame(audits)
    A["timing_estimable"] = A["timing_estimable"].fillna(False).astype(bool) if "timing_estimable" in A else False
    A.to_csv("results/audit/matb_alignment_audit.csv", index=False)
    print(f"audit: {len(A)} participants, usable {int(A.usable.sum())}; excluded: {A.loc[~A.usable, ['participant', 'exclude_reason']].to_dict('records')}")
    if not frames:
        return 0
    df = pd.concat(frames, ignore_index=True); df.to_parquet("data/features/matb_bins.parquet")
    timing_ok = A.set_index("participant").timing_estimable.to_dict()
    M = pd.DataFrame([r for pid, g in df.groupby("pid") for r in participant_metrics(pid, g, bool(timing_ok.get(pid, True)))])
    M.to_csv("results/tables/matb_participant_metrics.csv", index=False)
    perf = df[df.condition != "quiet_rest"].pivot_table(index="pid", columns="condition", values="abs_err", aggfunc="mean")
    perf.columns = [f"abs_err_{c}" for c in perf.columns]; perf = perf.reset_index()
    perf.to_csv("results/tables/matb_performance_by_block.csv", index=False)
    # ---- summary
    S = {"seed": SEED, "n_participants_audited": int(len(A)), "n_usable": int(A.usable.sum()), "excluded": A.loc[~A.usable, ["participant", "exclude_reason"]].to_dict("records"),
         "chronology": "t_epoch = E4 tag + MATB ELAPSED_TIME; five 360-s blocks from the tag; quiet rest = <=60 s before the tag",
         "hrv": "not computed: E4 IBI coverage of the task is sparse (see audit IBI_coverage_of_task)",
         "ibi_coverage_of_task": {"median": float(A.IBI_coverage_of_task.median()), "min": float(A.IBI_coverage_of_task.min()), "max": float(A.IBI_coverage_of_task.max())},
         "units": UNITS, "pulse_quality_rule": f"HR bin valid iff accepted-beat (IBI) coverage >= {IBI_MIN_COV} of the bin",
         "hr_bins_valid_fraction_by_participant": df[df.condition != "quiet_rest"].groupby("pid").hr.apply(lambda s: float(s.notna().mean())).round(3).to_dict(),
         "scale_floors": SCALE_FLOOR, "tag_uncertainty_s": A.set_index("participant").tag_uncertainty_s.round(2).to_dict(),
         "n_timing_ambiguous": int((~A.loc[A.usable, "timing_estimable"]).sum())}
    def summ(v):
        v = pd.Series(v).dropna(); return {"n": int(v.size), "median": float(v.median()) if v.size else np.nan, "q25": float(v.quantile(.25)) if v.size else np.nan, "q75": float(v.quantile(.75)) if v.size else np.nan}
    S["response_magnitude_phys"] = {c: {f"cycle_{cyc}": summ(M[(M.feature == c) & (M.cycle == cyc)].resp_phys) for cyc in (1, 2)} for c in FEATS}
    S["response_magnitude_phys_bootstrap"] = {c: {f"cycle_{cyc}": paired_bootstrap(M[(M.feature == c) & (M.cycle == cyc)].set_index("pid").resp_phys, seed=SEED) for cyc in (1, 2)} for c in FEATS}
    S["response_z_median"] = {c: {f"cycle_{cyc}": summ(M[(M.feature == c) & (M.cycle == cyc)].resp_z) for cyc in (1, 2)} for c in FEATS}
    S["burden"] = {c: {f"cycle_{cyc}": summ(M[(M.feature == c) & (M.cycle == cyc)].burden) for cyc in (1, 2)} for c in FEATS}
    S["departure_and_recovery_by_band"] = {}
    for band in BANDS:
        d = {}
        for c in FEATS:
            for cyc in (1, 2):
                m = M[(M.feature == c) & (M.cycle == cyc)]; st = m[f"status_b{band}"].value_counts().to_dict()
                d[f"{c}_cycle_{cyc}"] = {"n": int(len(m)), "departed": int(np.isfinite(m[f"t_depart_b{band}"]).sum()), "t_depart_median_s": float(np.nanmedian(m[f"t_depart_b{band}"])) if np.isfinite(m[f"t_depart_b{band}"]).any() else np.nan,
                                        "returned": int(st.get("returned", 0)), "censored": int(st.get("censored", 0)), "not_estimable": int(st.get("not_estimable", 0)),
                                        "return_time_median_s_among_returned": float(m.loc[m[f"status_b{band}"] == "returned", f"return_time_b{band}"].median()) if st.get("returned", 0) else np.nan}
        S["departure_and_recovery_by_band"][f"band_{band}"] = d
    S["recovery_residuals_z_band2"] = {c: {f"cycle_{cyc}": {f"residual_{s}": summ(M[(M.feature == c) & (M.cycle == cyc)][f"residual_{s}"]) for s in (60, 180, 360)} for cyc in (1, 2)} for c in FEATS}
    S["sensitivity_reference_B_whole_baseline"] = {c: {f"cycle_{cyc}": M[(M.feature == c) & (M.cycle == cyc)].status_refB.value_counts().to_dict() for cyc in (1, 2)} for c in FEATS}
    S["cycle2_vs_immediately_preceding_state_refC"] = {c: {"resp_phys": summ(M[(M.feature == c) & (M.cycle == 2)].resp_phys_preref), "status": M[(M.feature == c) & (M.cycle == 2)].status_preref.value_counts().to_dict()} for c in FEATS}
    rep = {}
    for c in FEATS:
        m1 = M[(M.feature == c) & (M.cycle == 1)].set_index("pid"); m2 = M[(M.feature == c) & (M.cycle == 2)].set_index("pid")
        rep[c] = {"resp_phys_c2_minus_c1": paired_bootstrap(m2.resp_phys - m1.resp_phys, seed=SEED), "burden_c2_minus_c1": paired_bootstrap(m2.burden - m1.burden, seed=SEED),
                  "return_time_c2_minus_c1_both_returned": paired_bootstrap((m2["return_time_b2.0"] - m1["return_time_b2.0"]).dropna(), seed=SEED)}
    S["repeated_challenge_change"] = rep
    S["scale_flags_near_zero_mad"] = {c: int(M[(M.feature == c) & (M.cycle == 1)].scale_flag.sum()) for c in FEATS}
    pf = perf.set_index("pid")
    S["performance_abs_err_by_block"] = {c: summ(pf[c]) for c in pf.columns}
    S["performance_challenge_minus_baseline"] = {f"cycle_{cyc}": paired_bootstrap(pf[f"abs_err_challenge_{cyc}"] - pf.abs_err_working_baseline, seed=SEED) for cyc in (1, 2)}
    S["performance_recovery_minus_baseline"] = {f"cycle_{cyc}": paired_bootstrap(pf[f"abs_err_recovery_{cyc}"] - pf.abs_err_working_baseline, seed=SEED) for cyc in (1, 2)}
    assoc = {}
    for c in ["hr", "eda", "motion", "temp"]:
        for cyc in (1, 2):
            m = M[(M.feature == c) & (M.cycle == cyc)].set_index("pid"); y = pf[f"abs_err_challenge_{cyc}"].reindex(m.index)
            for x_name in ("burden", "resp_phys"):
                x = m[x_name]; ok = x.notna() & y.notna()
                if ok.sum() >= 5:
                    r = stats.spearmanr(x[ok], y[ok]); assoc[f"{c}_{x_name}_vs_abs_err_challenge_{cyc}"] = {"n": int(ok.sum()), "spearman_rho": float(r.statistic), "p": float(r.pvalue)}
    S["burden_vs_performance_spearman"] = assoc
    S["prediction"] = prediction_test(df, M)
    json.dump(S, open("results/tables/matb_summary.json", "w"), indent=2, default=float)
    # ---- figures
    fig_first_participant(df, M, pids[0]); fig_cohort(df, M); fig_recovery(M); fig_burden_perf(M, perf); fig_added_value(S["prediction"])
    print(json.dumps({k: S[k] for k in ["n_usable", "excluded", "ibi_coverage_of_task", "scale_flags_near_zero_mad"]}, indent=1, default=float))
    print("response magnitude (physical units), median by cycle:"); print(pd.DataFrame({c: {k: v["median"] for k, v in S["response_magnitude_phys"][c].items()} for c in FEATS}).round(3))
    print("band 2 departure/recovery:"); print(pd.DataFrame(S["departure_and_recovery_by_band"]["band_2.0"]).T)
    print("performance by block:"); print(pd.DataFrame(S["performance_abs_err_by_block"]).round(1))
    print("prediction:"); print(json.dumps(S["prediction"], indent=1, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or None))
