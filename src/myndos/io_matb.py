"""Empatica E4 and MATB-II loaders for the PRIMARY dataset (neuro-stress-resilience-hci 1.0.0).

Verified on real files on 2026-09-09 (see results/audit/matb_alignment_audit.csv):
* E4 regular files: row 1 = session start (unix s, UTC), row 2 = fs, then samples; ACC has 3 columns.
  HR.csv starts 10 s after the other files (Empatica's HR warm-up); IBI is irregular and sparse.
* tags.csv: one unix time per row; README: "Event marker (Working Baseline start)".
* MATB-II/pXXresman.csv: header ELAPSED_TIME,TANK_A,TANK_B,TANK_C,TANK_D,DIFF_A,DIFF_B (UTF-8 BOM),
  ELAPSED_TIME as mm:ss.s at a 10-s cadence from the start of the working baseline; 179-180 rows
  (00:10 .. 29:50/30:00). DIFF_A/B == TANK_A/B - 2500 (the RESMAN target level) in every file checked.
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
                vals = line.rstrip("\r\n").split(",")
                out[i] = np.array([v if v not in ("", "nan", "NaN") else "nan" for v in vals], dtype=float)
                if len(out) == len(wanted):
                    break
    return out


def eeg_channel_names(xyz_path: str) -> list[str]:
    """Official 32-channel order from EEG_32_Channel_mapping.xyz (index, x, y, z, label)."""
    names = []
    with open(xyz_path) as fh:
        for line in fh:
            parts = line.split()
            if len(parts) >= 5:
                names.append(parts[4])
    return names


# Documented 1-based rows of the combined EEG/fNIRS/eye CSV (README + owner brief)
COMBINED_ROWS = {"time": 1, "fnirs": list(range(2, 34)), "eeg": list(range(34, 66)), "eye": list(range(66, 74)), "marker": 74}


MATB_TARGET_LEVEL = 2500  # RESMAN target for tanks A and B (DIFF_A/B == TANK - 2500 in the released files)


def parse_elapsed(s: str) -> float:
    """'mm:ss.s' or 'hh:mm:ss.s' -> seconds."""
    parts = str(s).strip().split(":")
    if len(parts) == 2:
        return float(parts[0]) * 60.0 + float(parts[1])
    if len(parts) == 3:
        return float(parts[0]) * 3600.0 + float(parts[1]) * 60.0 + float(parts[2])
    raise ValueError(f"unrecognised ELAPSED_TIME {s!r}")


def read_matb_resman(path: str) -> pd.DataFrame:
    """MATB-II RESMAN performance log.

    Returns columns: t_task_s (seconds since working-baseline start), tank_a..tank_d, diff_a, diff_b,
    abs_err = mean(|diff_a|, |diff_b|) (mean absolute deviation from the 2500 target across the two
    controlled tanks), and diff_consistent (DIFF == TANK - 2500 for that row).
    Rows are 10-s snapshots; the "mean absolute target deviation over a fixed interval" of PLAN.md
    is therefore the mean of the snapshots inside the interval.
    """
    raw = pd.read_csv(path, encoding="utf-8-sig")
    raw.columns = [c.strip().upper() for c in raw.columns]
    need = ["ELAPSED_TIME", "TANK_A", "TANK_B", "TANK_C", "TANK_D", "DIFF_A", "DIFF_B"]
    missing = [c for c in need if c not in raw.columns]
    if missing:
        raise ValueError(f"{path}: missing columns {missing}; got {list(raw.columns)}")
    df = pd.DataFrame({"t_task_s": raw["ELAPSED_TIME"].map(parse_elapsed).astype(float)})
    for c in ["TANK_A", "TANK_B", "TANK_C", "TANK_D", "DIFF_A", "DIFF_B"]:
        df[c.lower()] = pd.to_numeric(raw[c], errors="coerce").astype(float)
    df["diff_consistent"] = ((df.diff_a == df.tank_a - MATB_TARGET_LEVEL) & (df.diff_b == df.tank_b - MATB_TARGET_LEVEL))
    df["abs_err"] = 0.5 * (df.diff_a.abs() + df.diff_b.abs())
    return df


def matb_cadence_anomalies(t: np.ndarray, nominal: float = 10.0, tol: float = 0.5) -> np.ndarray:
    """Indices i where t[i]-t[i-1] deviates from the nominal cadence by more than tol seconds."""
    t = np.asarray(t, float)
    if t.size < 2:
        return np.array([], dtype=int)
    d = np.diff(t)
    return np.flatnonzero(np.abs(d - nominal) > tol) + 1
