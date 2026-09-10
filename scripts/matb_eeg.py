"""PRIMARY dataset Checkpoint 2: concurrent EEG for a small matched cohort, one participant at a time.

Input: EEGfNIRSeye_*/pXX/pXX.csv (channels as rows, ~600 MB, 250 Hz). Documented 1-based rows: time 1; fNIRS 2-33;
EEG 34-65 (32 channels in the order of EEG_32_Channel_mapping.xyz); pupil/gaze 66-73; event markers 74. Files of
participants whose Tobii data were recorded separately have 66 rows with the markers in row 66 (verified on p28).
Only the needed rows are streamed (myndos.io_matb.stream_combined_csv_rows); no wide DataFrame is built.

Chronology (frozen): the EEG stream has its own clock. Its working-start marker is the EARLIEST marker with a marker near its +360-s transition and at least two of
its four expected transitions within 15 s; that marker anchors task time zero on the EEG clock
(t_task = t_eeg - t_eeg0), which is matched to the wrist tag / MATB elapsed time by construction of the experiment, not
by any signal correlation. Actual EEG markers govern the EEG block boundaries; each transition's deviation from the
nominal 360-s grid is recorded as the cross-device uncertainty for that boundary, and a boundary deviating by more than
10 s makes the adjacent challenge/recovery timing estimates 'ambiguous' (excluded). Eye rows are audited (row indices,
ranges) but not analysed: they are on the same rows/clock for p01-p24 per README, still unproven for analysis.
Features: 0.5-40 Hz band-pass + 60-Hz notch (US mains; the released EEG already has no 55-65 Hz power), then a
per-participant CHANNEL screen over the whole recording (frozen after the p01 QC table, before any outcome: a channel is
retained iff its robust SD (1.4826*MAD of the filtered signal) is within 1-40 uV and its 99th-percentile |amplitude| is
<= 300 uV; p01 had 12 channels at 175-15,000 uV and 2 flat ones), then the per-10-s-bin artifact screen on the retained
channels (150 uV peak, flat < 0.5 uV, <= 25 % bad), log10 Welch power for theta/alpha/beta by frontal/central/parietal/
occipital groups over retained channels (>= 8 retained channels and >= 1 frontal, central and parietal channel required; an empty occipital group gives NaN occipital features). Same reference,
band and recovery rules as the wrist pipeline (scale floor 0.05 log10 units).
Usage: .venv/bin/python scripts/matb_eeg.py p01 [p02 ...]   (rebuilds cohort outputs from all cached participants)
"""
import sys, os, glob, json, hashlib
sys.path.insert(0, "src"); sys.path.insert(0, "scripts")
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from myndos.io_matb import stream_combined_csv_rows, eeg_channel_names, COMBINED_ROWS
from myndos.signal import eeg_preprocess, eeg_bin_features, channel_groups
from myndos.binning import make_bins
from myndos.metrics import robust_reference, normalize, response_magnitude, first_sustained_departure, burden, recovery

ROOT = "data/raw/matb"; BIN = 10.0; BLOCK_S = 360.0; SEED = 0
BLOCKS = ["working_baseline", "challenge_1", "recovery_1", "challenge_2", "recovery_2"]
EEG_FEATS = ["eeg_frontal_theta", "eeg_frontal_alpha", "eeg_central_alpha", "eeg_parietal_alpha", "eeg_occipital_alpha", "eeg_central_beta", "eeg_parietal_beta"]
FLOOR = 0.05
os.makedirs("results/audit", exist_ok=True); os.makedirs("results/tables", exist_ok=True); os.makedirs("results/figures", exist_ok=True); os.makedirs("data/features", exist_ok=True)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def official_sha(rel):
    for line in open(f"{ROOT}/SHA256SUMS.txt"):
        s, f = line.split()
        if f == rel:
            return s
    return None


def find_working_start(mt: np.ndarray, tol: float = 15.0):
    """Working start = EARLIEST marker that has a marker within 60 s of its +360-s transition and at least two of its
    four expected transitions (+360, +720, +1080, +1440 s) within ``tol``. Returns (index, deviations of the four
    transitions from the grid (NaN when no marker within 60 s), candidates). Deviations beyond 10 s mark that boundary
    ambiguous downstream (timing estimates dropped for the adjacent cycle); NaN falls back to the nominal grid.
    Rationale (frozen after p20: 5 markers with the first transition 16 s late): experimenter presses can be tens of
    seconds off; the anchor must not jump to a later transition marker just because one press was late."""
    cands = []
    for i in range(mt.size):
        devs = []
        for k in range(1, 5):
            target = mt[i] + k * BLOCK_S
            j = int(np.argmin(np.abs(mt - target)))
            devs.append(float(mt[j] - target) if abs(mt[j] - target) <= 60.0 else np.nan)
        n_within = int(np.sum([np.isfinite(d) and abs(d) <= tol for d in devs]))
        if np.isfinite(devs[0]) and n_within >= 2:
            cands.append((i, devs))
    if not cands:
        return None, None, cands
    return cands[0][0], cands[0][1], cands


def process(pid: str) -> dict:
    files = glob.glob(f"{ROOT}/EEGfNIRSeye_*/{pid}/{pid}.csv")
    a = {"participant": pid}
    if not files:
        a["status"] = "file absent"; return a
    path = files[0]; rel = os.path.relpath(path, ROOT); a["file"] = rel; a["bytes"] = os.path.getsize(path)
    a["sha256_ok"] = sha256(path) == official_sha(rel)
    if not a["sha256_ok"]:
        a["status"] = "checksum FAILED (partial or corrupt file)"; return a
    want = [COMBINED_ROWS["time"]] + COMBINED_ROWS["eeg"] + COMBINED_ROWS["eye"] + [COMBINED_ROWS["marker"]]
    rows = stream_combined_csv_rows(path, want)
    a["n_rows_read"] = len(rows); a["rows_missing"] = [r for r in want if r not in rows]
    # Two released layouts: 74 rows (eye rows 66-73, markers 74; p01-p24 with synchronous eye tracking) or 66 rows
    # (no eye rows, markers in row 66; participants whose Tobii data were recorded separately, per their Note.txt).
    if COMBINED_ROWS["marker"] in rows:
        a["layout"] = "74-row (eye rows 66-73, markers row 74)"; marker_row = COMBINED_ROWS["marker"]; eye_row_ids = COMBINED_ROWS["eye"]
    elif 66 in rows and all(r not in rows for r in range(67, 75)):
        a["layout"] = "66-row (no eye rows, markers row 66)"; marker_row = 66; eye_row_ids = []
    else:
        a["status"] = f"unrecognised layout: rows present {sorted(rows)}"; return a
    if any(r not in rows for r in [COMBINED_ROWS["time"]] + COMBINED_ROWS["eeg"]):
        a["status"] = f"required rows missing: {a['rows_missing']}"; return a
    mkv = rows[marker_row]; a["marker_row_is_binary"] = bool(np.all(np.isin(np.unique(mkv[np.isfinite(mkv)]), [0.0, 1.0])))
    if not a["marker_row_is_binary"]:
        a["status"] = f"marker row {marker_row} is not a 0/1 event row"; return a
    t = rows[COMBINED_ROWS["time"]]; n = t.size
    a["n_samples"] = int(n); a["lengths_equal"] = all(rows[r].size == n for r in rows)
    dt = np.diff(t); a["fs"] = float(1 / np.median(dt)); a["time_monotonic"] = bool(np.all(dt > 0)); a["max_time_gap_s"] = float(dt.max()); a["span_s"] = float(t[-1] - t[0])
    fs = a["fs"]
    names = eeg_channel_names(f"{ROOT}/EEG_32_Channel_mapping.xyz"); a["n_eeg_names"] = len(names)
    eeg_raw = np.vstack([rows[r] for r in COMBINED_ROWS["eeg"]])
    a["eeg_shape"] = list(eeg_raw.shape); a["eeg_n_nan"] = int(np.isnan(eeg_raw).sum())
    eeg_raw = np.nan_to_num(eeg_raw)
    eeg = eeg_preprocess(eeg_raw, fs, notch=60.0)
    sd = eeg.std(axis=1); a["eeg_filtered_sd_uV_median"] = float(np.median(sd)); a["eeg_filtered_sd_uV_min"] = float(sd.min()); a["eeg_filtered_sd_uV_max"] = float(sd.max())
    a["flat_channels"] = [names[i] for i in np.flatnonzero(sd < 0.5)]
    rsd = np.median(np.abs(eeg - np.median(eeg, axis=1, keepdims=True)), axis=1) * 1.4826; p99 = np.percentile(np.abs(eeg), 99, axis=1)
    keep = (rsd >= 1.0) & (rsd <= 40.0) & (p99 <= 300.0)
    a["channel_robust_sd_uV"] = np.round(rsd, 1).tolist(); a["channel_p99_uV"] = np.round(p99, 1).tolist()
    a["channels_retained"] = [n_ for n_, k in zip(names, keep) if k]; a["channels_rejected"] = [n_ for n_, k in zip(names, keep) if not k]
    a["n_channels_retained"] = int(keep.sum())
    fw, Pw = __import__("scipy.signal", fromlist=["welch"]).welch(eeg_raw[keep][:, int(100 * fs):int(400 * fs)] if keep.any() else eeg_raw[:, :int(300 * fs)], fs=fs, nperseg=int(2 * fs), axis=1)
    a["raw_power_55_65Hz_over_8_13Hz"] = float(np.mean(Pw[:, (fw >= 55) & (fw < 65)]) / max(np.mean(Pw[:, (fw >= 8) & (fw < 13)]), 1e-12))
    eeg = eeg[keep]; names = [n_ for n_, k in zip(names, keep) if k]
    groups_all = {g: channel_groups(names).get(g, []) for g in ("frontal", "central", "parietal", "occipital")}
    a["retained_per_group"] = {g: len(v) for g, v in groups_all.items()}
    if keep.sum() < 8 or any(len(groups_all[g]) == 0 for g in ("frontal", "central", "parietal")):
        a["status"] = f"EEG unusable: {int(keep.sum())} retained channels, groups {list(groups_all)}"
    # plausibility of the channel order: alpha power should be larger over parietal/occipital than frontal in most people
    eye_rows = [rows[r] for r in eye_row_ids if r in rows]
    if eye_rows:
        eye = np.vstack(eye_rows); a["eye_rows_nonconstant"] = int((np.nanstd(eye, axis=1) > 0).sum())
        a["eye_row_ranges"] = [[float(np.nanmin(e)), float(np.nanmax(e))] for e in eye]
    else:
        a["eye_rows_nonconstant"] = 0; a["eye_row_ranges"] = []
    mk = rows[marker_row]; idx = np.flatnonzero(mk != 0)
    if a.get("status", "").startswith("EEG unusable"):
        return a
    # collapse runs of consecutive nonzero samples into single events (marker value = first sample of the run)
    ev_t, ev_v = [], []
    for i in idx:
        if ev_t and i - ev_t[-1][1] <= 1:
            ev_t[-1][1] = i; continue
        ev_t.append([i, i]); ev_v.append(float(mk[i]))
    mt = np.array([t[s] for s, _ in ev_t]); a["n_markers"] = int(mt.size); a["marker_times_s"] = np.round(mt, 3).tolist(); a["marker_values"] = ev_v
    a["marker_intervals_s"] = np.round(np.diff(mt), 2).tolist()
    ws_i, devs, cands = find_working_start(mt)
    a["n_working_start_candidates"] = len(cands)
    if ws_i is None:
        a["status"] = "ambiguous: no marker followed by transitions at +360 and +720 s"; return a
    t0 = float(mt[ws_i]); a["eeg_working_start_s"] = t0; a["transition_deviation_s"] = devs
    a["rest_marker_before_start_s"] = float(t0 - mt[ws_i - 1]) if ws_i > 0 else np.nan
    a["eeg_coverage_after_start_s"] = float(t[-1] - t0)
    # actual EEG block boundaries from markers (nominal grid + recorded deviation)
    bounds = [t0] + [t0 + k * BLOCK_S + (devs[k - 1] if np.isfinite(devs[k - 1]) else 0.0) for k in range(1, 5)] + [min(t0 + 5 * BLOCK_S, float(t[-1]))]
    a["max_abs_transition_deviation_s"] = float(np.nanmax(np.abs(devs)))
    t_last = float(t[-1]); bounds = [min(b_, t_last) for b_ in bounds]  # recording may stop early (e.g. p16 'stopped after 24 minutes')
    segs = [(bounds[i], bounds[i + 1], BLOCKS[i]) for i in range(5) if bounds[i + 1] - bounds[i] >= BIN]
    a["blocks_truncated"] = [BLOCKS[i] for i in range(5) if t0 + (i + 1) * BLOCK_S > t_last + 1.0]
    if ws_i > 0 and t0 - mt[ws_i - 1] >= 30:
        segs = [(max(mt[ws_i - 1], t0 - 60.0), t0, "quiet_rest")] + segs
    a["timing_ambiguous_boundaries"] = [BLOCKS[k] for k in range(1, 5) if not np.isfinite(devs[k - 1]) or abs(devs[k - 1]) > 10.0]
    bins = make_bins(segs, width=BIN); groups = groups_all  # empty occipital group -> occipital features NaN
    out = []
    for b in bins.itertuples():
        f = eeg_bin_features(eeg, fs, names, b.t_start - t[0], b.t_end - t[0], groups)
        out.append({"pid": pid, "file": pid, "condition": b.condition, "seg_index": b.seg_index, "elapsed": b.elapsed, "t_end": b.t_end - t0,
                    "t_end_nominal": round((b.t_end - t0) / BIN) * BIN, "cycle": {"challenge_1": 1, "recovery_1": 1, "challenge_2": 2, "recovery_2": 2}.get(b.condition, 0), **f})
    df = pd.DataFrame(out); df.to_parquet(f"data/features/matb_eeg_bins_{pid}.parquet")
    a["n_bins"] = int(len(df)); a["eeg_ok_fraction"] = float(df.eeg_ok.mean())
    a["eeg_ok_fraction_by_block"] = df.groupby("condition").eeg_ok.mean().round(3).to_dict()
    ok = df[df.eeg_ok]; a["alpha_parietal_minus_frontal_log10"] = float((ok.eeg_parietal_alpha - ok.eeg_frontal_alpha).median()) if len(ok) else np.nan
    a["status"] = "ok"
    return a


def metrics_for(pid, g, ambiguous_blocks):
    out = []
    base = g[g.condition == "working_baseline"]; refA = base[base.elapsed > 180.0]; refC = g[(g.condition == "recovery_1") & (g.elapsed > 180.0)]
    for c in EEG_FEATS:
        med, sc, fl = robust_reference(refA[c].to_numpy())
        if np.isfinite(sc) and sc < FLOOR: sc, fl = FLOOR, True
        medC, scC, flC = robust_reference(refC[c].to_numpy())
        if np.isfinite(scC) and scC < FLOOR: scC = FLOOR
        for cyc in (1, 2):
            ch = g[g.condition == f"challenge_{cyc}"].sort_values("elapsed"); rc = g[g.condition == f"recovery_{cyc}"].sort_values("elapsed")
            r = {"pid": pid, "feature": c, "cycle": cyc, "n_ref_bins": int(refA[c].notna().sum()), "ref_median": med, "ref_scale": sc, "scale_flag": fl,
                 "n_challenge_valid": int(ch[c].notna().sum()), "n_recovery_valid": int(rc[c].notna().sum()),
                 "resp_phys": response_magnitude(ch[c].to_numpy(), refA[c].to_numpy())}
            zc = normalize(ch[c].to_numpy(), med, sc); zr = normalize(rc[c].to_numpy(), med, sc)
            r["resp_z"] = float(np.nanmedian(zc)) if np.isfinite(zc).any() else np.nan; r["burden"] = burden(zc, BIN)
            amb = (f"challenge_{cyc}" in ambiguous_blocks) or (f"recovery_{cyc}" in ambiguous_blocks)
            for band in (1.5, 2.0, 2.5):
                td = first_sustained_departure(zc, ch.elapsed.to_numpy(), band=band, k=3)
                rec = recovery(zr, rc.elapsed.to_numpy(), band=band, k=3, excursion=np.isfinite(td))
                r[f"t_depart_b{band}"] = np.nan if amb else td; r[f"return_time_b{band}"] = np.nan if amb else rec["return_time"]
                r[f"status_b{band}"] = "ambiguous_timing" if amb else rec["status"]
                if band == 2.0:
                    for s_ in (60, 180, 360): r[f"residual_{s_}"] = rec[f"residual_{s_}"]
            if cyc == 2:
                r["resp_phys_preref"] = response_magnitude(ch[c].to_numpy(), refC[c].to_numpy())
            out.append(r)
    return out


def cohort():
    A = rebuild_audit_csv()
    files = sorted(glob.glob("data/features/matb_eeg_bins_*.parquet"))
    if not files: return
    E = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    eeg_cols = [c for c in E.columns if c.startswith("eeg_") and c not in ("eeg_ok", "eeg_bad_ch_frac")]
    E.loc[~E.eeg_ok, eeg_cols] = np.nan
    E.to_parquet("data/features/matb_eeg_bins.parquet")
    amb = {}
    if len(A) and "timing_ambiguous_boundaries" in A:
        for r in A.itertuples():
            v = r.timing_ambiguous_boundaries
            if isinstance(v, (list, tuple, np.ndarray)): amb[r.participant] = [str(x) for x in v]
            elif v is None or (isinstance(v, float) and np.isnan(v)) or str(v) in ("[]", "", "nan"): amb[r.participant] = []
            else: amb[r.participant] = [x.strip(" '\"") for x in str(v).strip("[]").split(",") if x.strip()]
    M = pd.DataFrame([m for pid, g in E.groupby("pid") for m in metrics_for(pid, g, amb.get(pid, []))])
    M.to_csv("results/tables/matb_eeg_participant_metrics.csv", index=False)
    # merge with the wrist/behaviour bins on nominal task time (bin end) for the matched cohort
    W = pd.read_parquet("data/features/matb_bins.parquet") if os.path.exists("data/features/matb_bins.parquet") else None
    S = {"seed": SEED, "n_participants": int(E.pid.nunique()), "participants": sorted(E.pid.unique().tolist()),
         "eeg_ok_fraction": float(E.eeg_ok.mean()), "n_bins": int(len(E)),
         "prediction_with_eeg": {"status": f"NOT RUN: matched EEG cohort N={E.pid.nunique()} < 20 (insufficient-N); descriptives only, per PLAN.md"}}
    def summ(v):
        v = pd.Series(v).dropna(); return {"n": int(v.size), "median": float(v.median()) if v.size else np.nan, "q25": float(v.quantile(.25)) if v.size else np.nan, "q75": float(v.quantile(.75)) if v.size else np.nan}
    S["response_log10_power"] = {c: {f"cycle_{cyc}": summ(M[(M.feature == c) & (M.cycle == cyc)].resp_phys) for cyc in (1, 2)} for c in EEG_FEATS}
    S["per_participant_response_log10"] = {c: M[M.feature == c].pivot(index="pid", columns="cycle", values="resp_phys").round(3).to_dict() for c in EEG_FEATS}
    S["departure_recovery_band2"] = {f"{c}_cycle_{cyc}": M[(M.feature == c) & (M.cycle == cyc)]["status_b2.0"].value_counts().to_dict() | {"departed": int(np.isfinite(M[(M.feature == c) & (M.cycle == cyc)]["t_depart_b2.0"]).sum())} for c in EEG_FEATS for cyc in (1, 2)}
    S["scale_flags"] = {c: int(M[(M.feature == c) & (M.cycle == 1)].scale_flag.sum()) for c in EEG_FEATS}
    if W is not None:
        wcols = ["pid", "condition", "t_end", "elapsed", "seg_index", "cycle", "hr", "hr_e4_raw", "ibi_cov", "eda", "motion", "temp", "abs_err"]
        Wm = W[W.pid.isin(E.pid.unique())][[c for c in wcols if c in W.columns]].copy(); Wm["t_end_nominal"] = Wm.t_end.round(1)
        E2 = E.copy(); E2["t_end_nominal"] = E2.t_end_nominal.round(1)
        J = E2.merge(Wm.drop(columns=["t_end", "elapsed", "seg_index", "cycle"]), on=["pid", "condition", "t_end_nominal"], how="inner", suffixes=("", "_wrist"))
        J.to_parquet("data/features/matb_multimodal_bins.parquet")
        S["matched_bins"] = int(len(J)); S["matched_participants"] = int(J.pid.nunique())
        # matched-cohort added-value test with EEG (PLAN.md: only with >= 20 usable participants; otherwise insufficient-N)
        if J.pid.nunique() >= 20:
            import matb_pipeline as mp
            Mw = pd.read_csv("results/tables/matb_participant_metrics.csv")
            S["prediction_with_eeg"] = mp.prediction_test(J, Mw, eeg_cols=[c for c in EEG_FEATS if c != "eeg_occipital_alpha"], out_csv="results/tables/matb_eeg_prediction_participant_mae.csv")
            S["prediction_with_eeg"]["cohort"] = "matched EEG+wrist+behaviour bins on the nominal task clock"
        else:
            S["prediction_with_eeg"] = {"status": f"NOT RUN: matched EEG cohort N={J.pid.nunique()} < 20 (insufficient-N); descriptives only, per PLAN.md"}
        # within-participant Spearman between EEG features and concurrent task error across all task bins (descriptive only)
        from scipy import stats
        rho = {}
        for c in ["eeg_parietal_alpha", "eeg_frontal_theta", "eeg_central_beta"]:
            rho[c] = {pid: float(stats.spearmanr(g[c], g.abs_err, nan_policy="omit").statistic) for pid, g in J[J.condition != "quiet_rest"].groupby("pid") if g[c].notna().sum() >= 30}
        S["within_participant_spearman_eeg_vs_abs_err"] = rho
    json.dump(S, open("results/tables/matb_eeg_summary.json", "w"), indent=2, default=float)
    # ---- figure M6: small multiples, one panel per participant (z of parietal alpha and frontal theta vs reference A), task clock
    pids = sorted(E.pid.unique()); ncol = 5; nrow = int(np.ceil(len(pids) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.2 * ncol, 2.0 * nrow), sharex=True, sharey=True, squeeze=False)
    for ax, pid in zip(axes.ravel(), pids):
        g = E[E.pid == pid].sort_values("t_end"); base = g[(g.condition == "working_baseline") & (g.elapsed > 180)]
        for c, col in (("eeg_parietal_alpha", "#1f4e79"), ("eeg_frontal_theta", "#dd8452")):
            med, sc, _ = robust_reference(base[c].to_numpy()); sc = max(sc, FLOOR) if np.isfinite(sc) else np.nan
            ax.plot(g.t_end, normalize(g[c].to_numpy(), med, sc), color=col, lw=0.7)
        for cond, gg in g.groupby("condition"):
            if cond.startswith("challenge"): ax.axvspan(gg.t_end.min() - BIN, gg.t_end.max(), color="#f4c7c3", alpha=0.5, lw=0)
        ax.axhspan(-2, 2, color="#a6d96a", alpha=0.15, lw=0); ax.set_title(f"{pid}  ok {int(g.eeg_ok.sum())}/{len(g)}", fontsize=7); ax.tick_params(labelsize=6)
    for ax in axes.ravel()[len(pids):]: ax.axis("off")
    axes[0, 0].set_ylim(-8, 8); axes[0, 0].plot([], [], color="#1f4e79", label="parietal alpha (z vs ref A)"); axes[0, 0].plot([], [], color="#dd8452", label="frontal theta (z)"); axes[0, 0].legend(fontsize=6, loc="upper left")
    fig.suptitle(f"PRIMARY MATB-II EEG, {len(pids)} participants: 10-s artifact-screened log band power standardized to the final 3 min of working baseline (green = +-2 band, red = challenge). x = seconds since working start (EEG marker clock).", fontsize=8)
    fig.tight_layout(); fig.savefig("results/figures/figM6_eeg_timecourses.png", dpi=130); plt.close(fig)
    print(json.dumps({k: S[k] for k in S if k not in ("per_participant_response_log10",)}, indent=1, default=float))
    print(pd.DataFrame({c: S["per_participant_response_log10"][c] for c in ["eeg_parietal_alpha", "eeg_frontal_theta", "eeg_central_beta"]}).round(3))


AUDIT_DIR = "results/audit/matb_eeg_audit_rows"


def rebuild_audit_csv():
    os.makedirs(AUDIT_DIR, exist_ok=True)
    rows = [json.load(open(f)) for f in sorted(glob.glob(f"{AUDIT_DIR}/*.json"))]
    A = pd.DataFrame(rows)
    if len(A): A.to_csv("results/audit/matb_eeg_audit.csv", index=False)
    return A


def main(pids, run_cohort=True):
    os.makedirs(AUDIT_DIR, exist_ok=True)
    for pid in pids:
        a = process(pid); print(pid, {k: a[k] for k in a if k in ("status", "sha256_ok", "n_samples", "fs", "span_s", "n_markers", "marker_times_s", "marker_values", "marker_intervals_s", "eeg_working_start_s", "transition_deviation_s", "eeg_ok_fraction", "flat_channels", "alpha_parietal_minus_frontal_log10", "eeg_filtered_sd_uV_median", "n_channels_retained")})
        json.dump(a, open(f"{AUDIT_DIR}/{pid}.json", "w"), default=float)
    rebuild_audit_csv()
    if run_cohort:
        cohort()


if __name__ == "__main__":
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    if "--cohort-only" in sys.argv:
        rebuild_audit_csv(); cohort()
    else:
        main(args or ["p01"], run_cohort="--no-cohort" not in sys.argv)
