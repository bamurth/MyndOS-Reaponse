"""PRIMARY dataset pipeline (neuro-stress-resilience-hci 1.0.0): Checkpoint 1 of PLAN.md.

NOT RUN TONIGHT: physionet.org was blocked by the environment network policy and the dataset is not
on the AWS Open Data mirror. This script implements the audited E4 wrist path against the published
E4 format and exits cleanly when data are absent. When access is granted:
  mkdir -p data/raw/matb && cd data/raw/matb && \
  wget -r -N -c -np -nH --cut-dirs=3 https://physionet.org/files/neuro-stress-resilience-hci/1.0.0/
Then run: .venv/bin/python scripts/matb_pipeline.py

Frozen analysis choices (PLAN.md): trailing 10-s bins that never cross block boundaries; reference =
final three valid minutes of working baseline (sensitivity: whole block); median/1.4826*MAD; band +-2
(sens. 1.5/2.5); recovery = 3 consecutive valid in-band bins; censoring; no HRV from sparse IBI.
The MATB-II performance-file format is unverified and must be inspected before `load_matb_performance`
is trusted.
"""
import sys, os, glob, json
sys.path.insert(0, "src")
import numpy as np, pandas as pd
from myndos.io_matb import read_e4_regular, read_e4_ibi, read_e4_tags, expected_matb_segments
from myndos.binning import make_bins
from myndos.metrics import robust_reference, normalize, response_magnitude, first_sustained_departure, burden, recovery

ROOT = "data/raw/matb"
BLOCKS = ["working_baseline", "challenge_1", "recovery_1", "challenge_2", "recovery_2"]


def find_participants():
    return sorted({os.path.basename(os.path.dirname(f)) for f in glob.glob(f"{ROOT}/**/EDA.csv", recursive=True)})


def load_matb_performance(pdir: str) -> pd.DataFrame | None:
    """Placeholder: locate a MATB-II performance CSV and return columns [t_task_s, abs_error].
    The real column names must be verified against the dataset README before use."""
    cands = glob.glob(f"{pdir}/**/*MATB*.csv", recursive=True) + glob.glob(f"{pdir}/**/*matb*.csv", recursive=True)
    if not cands:
        return None
    raise NotImplementedError(f"MATB performance file found ({cands[0]}); inspect its columns and implement the parser before use")


def audit_participant(pdir: str) -> dict:
    a = {"participant": os.path.basename(pdir)}
    for name in ["EDA", "HR", "BVP", "ACC", "TEMP"]:
        p = f"{pdir}/{name}.csv"
        if os.path.exists(p):
            t, v, t0, fs = read_e4_regular(p)
            a[f"{name}_t0"] = t0; a[f"{name}_fs"] = fs; a[f"{name}_duration_s"] = float(t[-1] - t[0]) if len(t) else 0.0
            a[f"{name}_n_nan"] = int(np.isnan(v).sum())
    if os.path.exists(f"{pdir}/IBI.csv"):
        tt, ibi, t0 = read_e4_ibi(f"{pdir}/IBI.csv"); a["IBI_n"] = int(len(ibi)); a["IBI_coverage"] = float(ibi.sum() / max(a.get("HR_duration_s", 1), 1))
    tags = read_e4_tags(f"{pdir}/tags.csv"); a["tags"] = tags.tolist(); a["n_tags"] = int(tags.size)
    # clock consistency: all regular files should share t0 within 1 s
    t0s = [a[k] for k in a if k.endswith("_t0")]
    a["t0_spread_s"] = float(max(t0s) - min(t0s)) if t0s else np.nan
    a["working_start_tag"] = float(tags[0]) if tags.size else np.nan
    a["exclude_reason"] = "" if tags.size else "no working-start tag; cannot anchor blocks without inferring from signals"
    return a


def main():
    if not os.path.isdir(ROOT) or not find_participants():
        print("PRIMARY DATA ABSENT: data/raw/matb has no E4 participant folders. Nothing run. See STATUS.md for the access blocker.")
        return 0
    audits, rows = [], []
    for pid in find_participants():
        pdir = glob.glob(f"{ROOT}/**/{pid}", recursive=True)[0]
        a = audit_participant(pdir); audits.append(a)
        if a["exclude_reason"]:
            continue
        segs = expected_matb_segments(a["working_start_tag"])
        bins = make_bins(segs, width=10.0)
        t, hr, _, _ = read_e4_regular(f"{pdir}/HR.csv"); te, eda, _, _ = read_e4_regular(f"{pdir}/EDA.csv")
        ta, acc, _, _ = read_e4_regular(f"{pdir}/ACC.csv"); mot = np.linalg.norm(np.diff(acc, axis=0), axis=1) if acc.ndim == 2 else np.abs(np.diff(acc))
        for b in bins.itertuples():
            m = (t >= b.t_start) & (t < b.t_end); me = (te >= b.t_start) & (te < b.t_end); ma = (ta[1:] >= b.t_start) & (ta[1:] < b.t_end)
            rows.append({"pid": pid, "condition": b.condition, "t_end": b.t_end - a["working_start_tag"], "elapsed": b.elapsed,
                         "hr": float(np.nanmean(hr[m])) if m.sum() >= 5 else np.nan, "eda": float(np.nanmedian(eda[me])) if me.sum() >= 20 else np.nan,
                         "motion": float(np.nanmean(mot[ma])) if ma.sum() >= 100 else np.nan})
    pd.DataFrame(audits).to_csv("results/audit/matb_alignment_audit.csv", index=False)
    df = pd.DataFrame(rows); df.to_parquet("data/features/matb_bins.parquet")
    metrics = []
    for pid, g in df.groupby("pid"):
        base = g[g.condition == "working_baseline"]; ref = base[base.elapsed > 180]  # final three minutes
        for c in ["hr", "eda", "motion"]:
            med, sc, flag = robust_reference(ref[c].to_numpy())
            for cyc in (1, 2):
                ch = g[g.condition == f"challenge_{cyc}"]; rc = g[g.condition == f"recovery_{cyc}"]
                z_ch = normalize(ch[c].to_numpy(), med, sc); z_rc = normalize(rc[c].to_numpy(), med, sc)
                exc = np.isfinite(first_sustained_departure(z_ch, ch.elapsed.to_numpy()))
                r = recovery(z_rc, rc.elapsed.to_numpy(), excursion=exc)
                metrics.append({"pid": pid, "feature": c, "cycle": cyc, "scale_flag": flag, "resp_phys": response_magnitude(ch[c].to_numpy(), ref[c].to_numpy()),
                                "t_depart": first_sustained_departure(z_ch, ch.elapsed.to_numpy()), "burden": burden(z_ch, 10.0), **r})
    pd.DataFrame(metrics).to_csv("results/tables/matb_participant_metrics.csv", index=False)
    print("MATB peripheral pipeline complete:", df.pid.nunique(), "participants")
    return 0


if __name__ == "__main__":
    sys.exit(main())
