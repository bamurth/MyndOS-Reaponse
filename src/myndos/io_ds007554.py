"""OpenNeuro ds007554 (CMx7-MM) loader. Raw BIDS exports; no offline preprocessing applied by the authors.

Clock model (from the alignment audit in results/audit/):
* EEG EDF and events.tsv share the EEG clock (events are given relative to EEG start).
* ECG and push-button are Delsys streams sharing the Delsys clock. Their physio.json
  declares StartTime 0, but push-button presses lag stimulus targets by a per-file
  offset of several seconds, so the Delsys-to-EEG offset is UNKNOWN. We never shift
  streams by inferred offsets; cross-device pairing is flagged `clock_verified=False`.
"""
from __future__ import annotations

import os
import glob
import json
import re
import numpy as np
import pandas as pd
import pyedflib

ROOT = "data/raw/ds007554"
TASKS = ["passivemotor", "motorimagery", "activemotor", "mentalarithmetic", "nback", "nbackarithmetic", "full"]
# Declared demand ordering used only as an ordinal covariate (README task hierarchy).
TASK_DEMAND_RANK = {t: i for i, t in enumerate(TASKS)}
BUTTON_TASKS = ["nback", "nbackarithmetic"]
LOAD_COLS = {"nback": "Nback", "mentalarithmetic": "Arithmetic", "motorimagery": "MotorImagery",
             "passivemotor": "PassiveMotor", "nbackarithmetic": "NbackArithmetic", "activemotor": "ActiveMotor",
             "full": "Full"}


def index_files(root: str = ROOT) -> pd.DataFrame:
    rows = []
    for f in sorted(glob.glob(f"{root}/sub-*/ses-*/eeg/*_eeg.edf")):
        m = re.search(r"(sub-\d+)_(ses-\d+)_task-(\w+)_eeg\.edf", os.path.basename(f))
        sub, ses, task = m.groups()
        beh = f"{root}/{sub}/{ses}/beh/{sub}_{ses}_task-{task}"
        rows.append({"sub": sub, "ses": ses, "task": task, "eeg": f,
                     "events": f.replace("_eeg.edf", "_events.tsv"),
                     "ecg": beh + "_recording-ECG_physio.tsv.gz",
                     "button": beh + "_recording-pushbutton_physio.tsv.gz"})
    df = pd.DataFrame(rows)
    for c in ["events", "ecg", "button"]:
        df[c + "_exists"] = df[c].map(os.path.exists)
    return df


def load_eeg(path: str) -> dict:
    r = pyedflib.EdfReader(path)
    labels = r.getSignalLabels()
    fs = float(r.getSampleFrequency(0))
    x = np.vstack([r.readSignal(i) for i in range(r.signals_in_file)])
    units = r.getPhysicalDimension(0)
    start = r.getStartdatetime()
    dur = float(r.getFileDuration())
    r.close()
    js = json.load(open(path.replace("_eeg.edf", "_eeg.json")))
    ch = pd.read_csv(path.replace("_eeg.edf", "_channels.tsv"), sep="\t")
    eeg_mask = (ch["type"] == "EEG").values if len(ch) == len(labels) else np.array([True] * len(labels))
    names = list(ch["name"]) if len(ch) == len(labels) else labels
    return {"eeg": x[eeg_mask], "eeg_names": [n for n, k in zip(names, eeg_mask) if k], "fs": fs,
            "fs_json": float(js.get("SamplingFrequency", fs)), "units": units, "start": start,
            "duration_s": dur, "n_signals": len(labels)}


def load_events(path: str) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t")


def load_physio(path: str) -> tuple[np.ndarray, float, dict]:
    js = json.load(open(path.replace(".tsv.gz", ".json")))
    x = pd.read_csv(path, sep="\t", header=None)
    return x.iloc[:, 0].values.astype(float), float(js["SamplingFrequency"]), js


def button_onsets(sig: np.ndarray, fs: float) -> np.ndarray:
    """Press onset times (s, Delsys clock). Pressed = the rarer of the two voltage states."""
    thr = (np.nanmin(sig) + np.nanmax(sig)) / 2
    hi = sig > thr
    pressed = hi if hi.mean() < 0.5 else ~hi
    ups = np.flatnonzero(np.diff(pressed.astype(int)) == 1) + 1
    return ups / fs


def phenotype(root: str = ROOT) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    part = pd.read_csv(f"{root}/participants.tsv", sep="\t")
    load = pd.read_csv(f"{root}/phenotype/cognitive_load.tsv", sep="\t", na_values=["n/a"])
    kss = pd.read_csv(f"{root}/phenotype/kss_values.tsv", sep="\t", na_values=["n/a"])
    return part, load, kss
