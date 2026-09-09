"""ds007554 chronology audit: EDF headers, stream durations, and push-button vs stimulus-target
event matching for the two button tasks. Writes results/audit/ds007554_files.csv and
results/audit/ds007554_button_alignment.csv. Offsets are REPORTED here; acceptance rules are frozen:
unique best shift on a 0.25-s grid over [-30, +30] s, best hits >= 8, best hits >= 2x the median hits
over the grid, and second-best peak (outside +-1.5 s of best) <= 0.6x best.
"""
import sys, os, json
sys.path.insert(0, "src")
import numpy as np, pandas as pd, pyedflib
from myndos.io_ds007554 import index_files, load_events, load_physio, button_onsets

idx = index_files()
frows, arows = [], []
for r in idx.itertuples():
    e = pyedflib.EdfReader(r.eeg); st = e.getStartdatetime(); dur = e.getFileDuration(); n = e.signals_in_file; fs = e.getSampleFrequency(0); e.close()
    js = json.load(open(r.eeg.replace("_eeg.edf", "_eeg.json")))
    ev = load_events(r.events) if r.events_exists else None
    row = {"sub": r.sub, "ses": r.ses, "task": r.task, "edf_start": str(st), "edf_duration_s": dur, "edf_n_signals": n, "edf_fs": fs,
           "json_fs": js.get("SamplingFrequency"), "json_duration_s": js.get("RecordingDuration"),
           "n_events": len(ev) if ev is not None else np.nan, "first_event_s": ev.onset.min() if ev is not None else np.nan,
           "last_event_s": ev.onset.max() if ev is not None else np.nan, "ecg_exists": r.ecg_exists, "button_exists": r.button_exists}
    if r.ecg_exists:
        try:
            x, pfs, pj = load_physio(r.ecg); row.update({"ecg_fs": pfs, "ecg_duration_s": len(x) / pfs, "ecg_start_declared": pj.get("StartTime")})
        except Exception as ex:
            row["ecg_error"] = str(ex)[:80]
    frows.append(row)
    if r.button_exists and ev is not None:
        sig, bfs, _ = load_physio(r.button); press = button_onsets(sig, bfs)
        tg = ev[ev.trial_type == "target"].onset.values
        grid = np.arange(-30, 30.01, 0.25); hits = np.array([sum(1 for o in tg if np.any((press - k >= o) & (press - k < o + 1.5))) for k in grid])
        b = int(np.argmax(hits)); best = grid[b]; med = np.median(hits)
        far = np.abs(grid - best) > 1.5; second = hits[far].max() if far.any() else 0
        accepted = (hits[b] >= 8) and (hits[b] >= 2 * max(med, 1)) and (second <= 0.6 * hits[b])
        # RT distribution at the accepted offset
        rts = [((press - best)[(press - best >= o) & (press - best < o + 1.5)][0] - o) for o in tg if np.any((press - best >= o) & (press - best < o + 1.5))]
        arows.append({"sub": r.sub, "ses": r.ses, "task": r.task, "n_targets": len(tg), "n_presses": len(press), "best_shift_s": best,
                      "hits_at_best": int(hits[b]), "median_hits_grid": float(med), "second_peak_hits": int(second), "accepted": bool(accepted),
                      "rt_median_s": float(np.median(rts)) if rts else np.nan, "button_duration_s": len(sig) / bfs})
F = pd.DataFrame(frows); A = pd.DataFrame(arows)
F.to_csv("results/audit/ds007554_files.csv", index=False); A.to_csv("results/audit/ds007554_button_alignment.csv", index=False)
print("files", len(F), "with ecg", F.ecg_exists.sum(), "button files", len(A))
print(F.groupby("task").edf_duration_s.describe()[["count", "min", "max"]])
print("events first onset", F.first_event_s.describe()[["min", "max"]].to_dict(), "ecg dur", F.ecg_duration_s.describe()[["min", "max"]].to_dict())
print("EDF start dates per (sub,ses): span in days"); s = F.copy(); s["d"] = pd.to_datetime(s.edf_start)
print(s.groupby(["sub", "ses"]).d.agg(lambda x: (x.max() - x.min()).days).describe())
print(A.accepted.value_counts()); print(A[A.accepted].best_shift_s.describe()); print("RT median (accepted)", A[A.accepted].rt_median_s.describe()[["min", "50%", "max"]].to_dict())
