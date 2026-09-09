"""Frozen response/recovery metrics (see PLAN.md section 4).

All estimators operate on one feature's per-bin series (time = bin end).
Missing bins are NaN and *break* sustained-return sequences.
"""
from __future__ import annotations

import numpy as np

MAD_SCALE = 1.4826


def robust_reference(ref: np.ndarray, min_scale: float | None = None) -> tuple[float, float, bool]:
    """Median and 1.4826*MAD of the reference values (NaNs ignored).

    Returns (median, scale, near_zero_flag). If MAD is ~0, ``scale`` is replaced
    by the reference IQR/1.349 when that is positive, and the flag is set; if both
    are zero the scale is NaN and the feature must not be normalized.
    """
    r = np.asarray(ref, dtype=float)
    r = r[np.isfinite(r)]
    if r.size < 3:
        return np.nan, np.nan, True
    med = float(np.median(r))
    mad = float(np.median(np.abs(r - med))) * MAD_SCALE
    flag = False
    tiny = 1e-9 if min_scale is None else min_scale
    if mad <= tiny:
        flag = True
        iqr = float(np.subtract(*np.percentile(r, [75, 25]))) / 1.349
        mad = iqr if iqr > tiny else np.nan
    return med, mad, flag


def normalize(x: np.ndarray, med: float, scale: float) -> np.ndarray:
    if not np.isfinite(scale) or scale <= 0:
        return np.full_like(np.asarray(x, dtype=float), np.nan)
    return (np.asarray(x, dtype=float) - med) / scale


def response_magnitude(challenge: np.ndarray, ref: np.ndarray) -> float:
    """Challenge median minus reference median (physical units)."""
    c = np.asarray(challenge, float); r = np.asarray(ref, float)
    if np.isfinite(c).sum() == 0 or np.isfinite(r).sum() == 0:
        return np.nan
    return float(np.nanmedian(c) - np.nanmedian(r))


def first_sustained_departure(z: np.ndarray, t: np.ndarray, band: float = 2.0, k: int = 3) -> float:
    """Time of the first run of ``k`` consecutive valid bins with |z| > band.

    Returns NaN when no such run exists (response timing not estimable).
    """
    z = np.asarray(z, float); t = np.asarray(t, float)
    run = 0
    for i in range(z.size):
        if np.isfinite(z[i]) and abs(z[i]) > band:
            run += 1
            if run == k:
                return float(t[i - k + 1])
        else:
            run = 0
    return np.nan


def burden(z: np.ndarray, dt: float) -> float:
    """Integral of |z| over valid bins (robust-units x seconds). NaN if no valid bins."""
    z = np.asarray(z, float)
    if np.isfinite(z).sum() == 0:
        return np.nan
    return float(np.nansum(np.abs(z)) * dt)


def recovery(z: np.ndarray, t_rel: np.ndarray, band: float = 2.0, k: int = 3,
             residual_at: tuple[float, ...] = (60.0, 180.0, 360.0), excursion: bool = True) -> dict:
    """Recovery metrics on a recovery segment (t_rel = seconds since demand decreased).

    * residual_<s>: z of the last *valid* bin ending in (s - 30, s]; NaN if none (a missing final
      snapshot must not erase the endpoint, but nothing older than 30 s may stand in for it).
    * return_time: end time of the first run of ``k`` consecutive *valid* bins
      with |z| <= band. Missing bins break the run.
    * status: 'returned', 'censored' (no return before the segment ends),
      or 'not_estimable' (no excursion was measured in the preceding challenge).
    """
    z = np.asarray(z, float); t_rel = np.asarray(t_rel, float)
    out = {"return_time": np.nan, "status": "not_estimable" if not excursion else "censored",
           "observed_duration": float(t_rel[-1]) if t_rel.size else np.nan}
    for s in residual_at:
        m = np.flatnonzero((t_rel <= s + 1e-9) & (t_rel > s - 30.0 + 1e-9) & np.isfinite(z))
        out[f"residual_{int(s)}"] = float(z[m[-1]]) if m.size else np.nan
    if not excursion:
        return out
    run = 0
    for i in range(z.size):
        if np.isfinite(z[i]) and abs(z[i]) <= band:
            run += 1
            if run == k:
                out["return_time"] = float(t_rel[i])
                out["status"] = "returned"
                break
        else:
            run = 0
    return out
