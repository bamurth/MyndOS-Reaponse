"""EEGMAT (PhysioNet eegmat 1.0.0) loader."""
from __future__ import annotations

import os
import glob
import numpy as np
import pandas as pd
import pyedflib

ROOT = "data/raw/eegmat/eeg-during-mental-arithmetic-tasks-1.0.0"


def subjects(root: str = ROOT) -> list[str]:
    return sorted({os.path.basename(f).split("_")[0] for f in glob.glob(f"{root}/Subject*_1.edf")})


def subject_info(root: str = ROOT) -> pd.DataFrame:
    return pd.read_csv(f"{root}/subject-info.csv")


def load_edf(path: str) -> dict:
    """Return dict(eeg=(n_ch, n) uV, eeg_names, ecg (mV), fs, duration_s, start)."""
    r = pyedflib.EdfReader(path)
    labels = r.getSignalLabels()
    fs = float(r.getSampleFrequency(0))
    eeg_idx = [i for i, l in enumerate(labels) if l.startswith("EEG") and "A2-A1" not in l]
    ecg_idx = [i for i, l in enumerate(labels) if "ECG" in l.upper()]
    if not ecg_idx:
        raise ValueError(f"no ECG channel in {path}")
    assert all(float(r.getSampleFrequency(i)) == fs for i in eeg_idx + ecg_idx)
    eeg = np.vstack([r.readSignal(i) for i in eeg_idx])
    ecg = r.readSignal(ecg_idx[0])
    out = {"eeg": eeg, "eeg_names": [labels[i].replace("EEG ", "") for i in eeg_idx], "ecg": ecg,
           "ecg_units": r.getPhysicalDimension(ecg_idx[0]), "eeg_units": r.getPhysicalDimension(eeg_idx[0]),
           "fs": fs, "duration_s": float(r.getFileDuration()), "start": r.getStartdatetime(), "path": path}
    r.close()
    return out
