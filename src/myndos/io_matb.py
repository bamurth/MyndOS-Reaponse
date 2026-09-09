"""Empatica E4 and MATB-II loaders for the PRIMARY dataset (neuro-stress-resilience-hci).

STATUS: the primary dataset was unreachable from the execution environment
(physionet.org blocked by network policy; not on the AWS mirror). These parsers
follow the published E4 CSV format and are covered by synthetic tests only.
They have NOT been run on real primary files. See STATUS.md.
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd


def read_e4_regular(path: str) -> tuple[np.ndarray, np.ndarray, float, float]:
    """E4 regularly sampled file (BVP/EDA/HR/TEMP/ACC): row 1 epoch start, row 2 fs, then samples.

    Returns (t_epoch_s, values, t0_epoch, fs). ACC returns 3 columns.
    """
    raw = pd.read_csv(path, header=None)
    t0 = float(raw.iloc[0, 0])
    fs = float(raw.iloc[1, 0])
    v = raw.iloc[2:].to_numpy(dtype=float)
    if v.shape[1] == 1:
        v = v[:, 0]
    t = t0 + np.arange(v.shape[0]) / fs
    return t, v, t0, fs


def read_e4_ibi(path: str) -> tuple[np.ndarray, np.ndarray, float]:
    """IBI.csv: first row 'epoch, IBI'; then rows 'seconds since epoch, interval'. Irregular."""
    raw = pd.read_csv(path, header=None)
    t0 = float(raw.iloc[0, 0])
    body = raw.iloc[1:].to_numpy(dtype=float)
    if body.size == 0:
        return np.array([]), np.array([]), t0
    return t0 + body[:, 0], body[:, 1], t0


def read_e4_tags(path: str) -> np.ndarray:
    """tags.csv: one epoch time per row (button presses / event marks)."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return np.array([])
    return pd.read_csv(path, header=None).iloc[:, 0].to_numpy(dtype=float)


def expected_matb_segments(working_start_epoch: float, block_s: float = 360.0) -> list[tuple[float, float, str]]:
    """Expected block boundaries relative to the working-start tag. Actual markers govern
    when present; these are only used to *propose* windows for audit against markers."""
    labels = ["working_baseline", "challenge_1", "recovery_1", "challenge_2", "recovery_2"]
    return [(working_start_epoch + i * block_s, working_start_epoch + (i + 1) * block_s, lab)
            for i, lab in enumerate(labels)]


def stream_combined_csv_rows(path: str, wanted_rows_1based: list[int]) -> dict[int, np.ndarray]:
    """Stream selected numeric rows from the channels-as-rows combined CSV without
    allocating a wide DataFrame. Row numbering is 1-based as in the dataset README."""
    wanted = set(wanted_rows_1based)
    out: dict[int, np.ndarray] = {}
    with open(path, "r") as fh:
        for i, line in enumerate(fh, start=1):
            if i in wanted:
                out[i] = np.array([float(v) if v not in ("", "nan", "NaN") else np.nan for v in line.rstrip("\n").split(",")])
                if len(out) == len(wanted):
                    break
    return out
