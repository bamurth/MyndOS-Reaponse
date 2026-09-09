"""Signal processing: ECG R-peaks, beat quality, EEG band power, artifact screening.

All functions are pure numpy/scipy so that tests can run on synthetic fixtures.
Nothing here infers clock offsets from signal correlations.
"""
from __future__ import annotations

import numpy as np
from scipy import signal as sps

# ---------------------------------------------------------------- ECG -------

def bandpass(x: np.ndarray, fs: float, lo: float, hi: float, order: int = 3) -> np.ndarray:
    nyq = 0.5 * fs
    hi = min(hi, 0.95 * nyq)
    b, a = sps.butter(order, [lo / nyq, hi / nyq], btype="band")
    return sps.filtfilt(b, a, x)


def detect_r_peaks(ecg: np.ndarray, fs: float, min_rr_s: float = 0.30) -> np.ndarray:
    """Pan–Tompkins-style R-peak detector; polarity agnostic.

    Returns sample indices of detected beats. Quality is judged separately by
    :func:`rr_quality`; this function only proposes candidates.
    """
    ecg = np.asarray(ecg, dtype=float)
    if ecg.size < int(2 * fs) or np.nanstd(ecg) == 0:
        return np.array([], dtype=int)
    ecg = np.nan_to_num(ecg - np.nanmedian(ecg))
    bp = bandpass(ecg, fs, 5.0, 25.0)
    der = np.gradient(bp)
    sq = der ** 2
    win = max(1, int(round(0.150 * fs)))
    integ = np.convolve(sq, np.ones(win) / win, mode="same")
    # adaptive threshold: fraction of a robust high quantile, recomputed in 10-s chunks
    thr = np.empty_like(integ)
    chunk = int(10 * fs)
    for s in range(0, integ.size, chunk):
        seg = integ[s:s + chunk]
        q = np.quantile(seg, 0.98) if seg.size else 0.0
        thr[s:s + chunk] = 0.3 * q
    peaks, _ = sps.find_peaks(integ, height=thr, distance=int(min_rr_s * fs))
    # refine each candidate to the maximum of |bp| within +-60 ms
    r = int(0.06 * fs)
    refined = []
    for p in peaks:
        a, b = max(0, p - r), min(bp.size, p + r + 1)
        refined.append(a + int(np.argmax(np.abs(bp[a:b]))))
    refined = np.unique(np.asarray(refined, dtype=int))
    if refined.size > 1:
        keep = np.concatenate([[True], np.diff(refined) >= int(min_rr_s * fs)])
        refined = refined[keep]
    return refined


def rr_quality(peaks: np.ndarray, fs: float, rr_min: float = 0.33, rr_max: float = 2.0,
               max_rel_jump: float = 0.30) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (rr_times_s, rr_s, valid_mask).

    rr_times are the times of the *second* beat of each interval. An interval is
    valid when it is physiologically plausible and does not jump by more than
    ``max_rel_jump`` relative to the local median of the surrounding 9 intervals.
    """
    peaks = np.asarray(peaks, dtype=float)
    if peaks.size < 3:
        return np.array([]), np.array([]), np.array([], dtype=bool)
    t = peaks / fs
    rr = np.diff(t)
    tt = t[1:]
    valid = (rr >= rr_min) & (rr <= rr_max)
    k = 4
    loc = np.array([np.median(rr[max(0, i - k):i + k + 1]) for i in range(rr.size)])
    valid &= np.abs(rr - loc) <= max_rel_jump * loc
    return tt, rr, valid


def beat_features(rr_t: np.ndarray, rr: np.ndarray, valid: np.ndarray, t0: float, t1: float,
                  min_valid_hr: int = 6, min_valid_hrv: int = 20, min_coverage_hrv: float = 0.9) -> dict:
    """HR and RMSSD in [t0, t1). HR requires ``min_valid_hr`` valid intervals.

    RMSSD requires ``min_valid_hrv`` valid, *consecutive-in-time* intervals and
    that valid intervals cover at least ``min_coverage_hrv`` of the window; it is
    NaN otherwise. Window length is the caller's business.
    """
    m = (rr_t >= t0) & (rr_t < t1)
    v = m & valid
    n_valid = int(v.sum())
    out = {"n_beats": int(m.sum()), "n_valid": n_valid,
           "coverage": float(rr[v].sum() / (t1 - t0)) if (t1 > t0) else np.nan,
           "hr": np.nan, "rmssd": np.nan, "hr_valid": False, "hrv_valid": False}
    if n_valid >= min_valid_hr:
        out["hr"] = 60.0 / float(np.mean(rr[v]))
        out["hr_valid"] = True
    if n_valid >= min_valid_hrv and out["coverage"] >= min_coverage_hrv and out["coverage"] <= 1.05:
        idx = np.flatnonzero(v)
        consec = np.diff(idx) == 1
        d = np.diff(rr[idx])[consec]
        if d.size >= min_valid_hrv - 1:
            out["rmssd"] = float(np.sqrt(np.mean(d ** 2)) * 1000.0)
            out["hrv_valid"] = True
    return out

# ---------------------------------------------------------------- EEG -------

BANDS = {"theta": (4.0, 8.0), "alpha": (8.0, 13.0), "beta": (13.0, 30.0)}


def channel_groups(names: list[str]) -> dict[str, list[int]]:
    """Declared channel groups by 10-20 label prefix. Unmatched channels are ignored."""
    groups: dict[str, list[int]] = {"frontal": [], "central": [], "parietal": [], "occipital": []}
    for i, n in enumerate(names):
        u = n.upper().replace("EEG ", "").strip()
        if u.startswith(("FP", "AF", "F")):
            groups["frontal"].append(i)
        elif u.startswith(("C", "T")):  # C*, CP*, T*, TP*
            groups["central"].append(i)
        elif u.startswith(("P",)):
            groups["parietal"].append(i)
        elif u.startswith(("O",)):
            groups["occipital"].append(i)
    return {g: idx for g, idx in groups.items() if idx}


def eeg_preprocess(x: np.ndarray, fs: float, notch: float | None = 50.0) -> np.ndarray:
    """Zero-phase 0.5–40 Hz band-pass (and 50-Hz notch) on channels x samples."""
    x = np.asarray(x, dtype=float)
    x = x - np.mean(x, axis=1, keepdims=True)
    nyq = 0.5 * fs
    b, a = sps.butter(3, [0.5 / nyq, min(40.0, 0.9 * nyq) / nyq], btype="band")
    y = sps.filtfilt(b, a, x, axis=1)
    if notch and notch < nyq:
        bn, an = sps.iirnotch(notch / nyq, 30.0)
        y = sps.filtfilt(bn, an, y, axis=1)
    return y


def window_artifact_mask(win: np.ndarray, amp_uv: float = 150.0, flat_uv: float = 0.5,
                         max_bad_frac: float = 0.25) -> tuple[bool, np.ndarray]:
    """Per-window screen. Returns (window_ok, channel_ok).

    A channel is bad in this window when its peak absolute amplitude exceeds
    ``amp_uv`` (ocular/muscle/motion) or its std is below ``flat_uv`` (flat/
    disconnected). The window is rejected if more than ``max_bad_frac`` of the
    channels are bad.
    """
    pk = np.max(np.abs(win), axis=1)
    sd = np.std(win, axis=1)
    ch_ok = (pk <= amp_uv) & (sd >= flat_uv)
    return bool(np.mean(~ch_ok) <= max_bad_frac), ch_ok


def bandpower_window(win: np.ndarray, fs: float, bands: dict = BANDS, seg_s: float = 2.0) -> dict[str, np.ndarray]:
    """Welch band power (uV^2) per channel for each band; returns {band: (n_ch,)}."""
    nper = int(seg_s * fs)
    f, p = sps.welch(win, fs=fs, nperseg=min(nper, win.shape[1]), axis=1)
    out = {}
    for b, (lo, hi) in bands.items():
        m = (f >= lo) & (f < hi)
        out[b] = np.trapezoid(p[:, m], f[m], axis=1)
    return out


def eeg_bin_features(eeg: np.ndarray, fs: float, names: list[str], t0: float, t1: float,
                     groups: dict[str, list[int]] | None = None) -> dict:
    """Log10 band power by channel group for the window [t0, t1) of a preprocessed array."""
    a, b = int(round(t0 * fs)), int(round(t1 * fs))
    win = eeg[:, max(a, 0):max(b, 0)]
    groups = groups or channel_groups(names)
    if win.shape[1] < int(fs):  # window (partly) outside the recording: no feature, flagged not ok
        feats = {"eeg_ok": False, "eeg_bad_ch_frac": np.nan}
        for g in groups:
            for band in BANDS:
                feats[f"eeg_{g}_{band}"] = np.nan
        return feats
    ok, ch_ok = window_artifact_mask(win)
    feats = {"eeg_ok": ok, "eeg_bad_ch_frac": float(np.mean(~ch_ok))}
    if not ok:
        for g in groups:
            for band in BANDS:
                feats[f"eeg_{g}_{band}"] = np.nan
        return feats
    bp = bandpower_window(win, fs)
    for g, idx in groups.items():
        idx_ok = [i for i in idx if ch_ok[i]]
        for band in BANDS:
            feats[f"eeg_{g}_{band}"] = float(np.log10(np.mean(bp[band][idx_ok]) + 1e-12)) if idx_ok else np.nan
    return feats
