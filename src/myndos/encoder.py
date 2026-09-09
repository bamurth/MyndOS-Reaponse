"""Encoder interface for window-level representations.

Tonight's only implemented encoder is the handcrafted feature encoder (band powers, HR, RMSSD).
It is NOT a foundation model. `BIOTFrozenEncoder` documents the audited contract for a released
BIOT checkpoint (github.com/ycq091044/BIOT, MIT; EEG-PREST-16-channels.ckpt, 13.8 MB, 200 Hz,
16 bipolar 10-20 montages, 10-s windows) and raises until torch and the checkpoint are available.
Status tonight: audited, NOT RUN (see RESULTS.md).
"""
from __future__ import annotations

import numpy as np
from .signal import eeg_bin_features, channel_groups

BIOT_16_MONTAGE = ["FP1-F7", "F7-T7", "T7-P7", "P7-O1", "FP2-F8", "F8-T8", "T8-P8", "P8-O2",
                   "FP1-F3", "F3-C3", "C3-P3", "P3-O1", "FP2-F4", "F4-C4", "C4-P4", "P4-O2"]
LEGACY_NAMES = {"T3": "T7", "T4": "T8", "T5": "P7", "T6": "P8"}


class Encoder:
    name = "base"

    def encode(self, eeg: np.ndarray, fs: float, names: list[str], t0: float, t1: float) -> np.ndarray:
        raise NotImplementedError


class HandcraftedEncoder(Encoder):
    """Log band power by channel group; the same features used in the analyses."""
    name = "handcrafted_bandpower"

    def encode(self, eeg, fs, names, t0, t1):
        f = eeg_bin_features(eeg, fs, names, t0, t1, channel_groups(names))
        keys = sorted(k for k in f if k.startswith("eeg_") and k not in ("eeg_ok", "eeg_bad_ch_frac"))
        return np.array([f[k] for k in keys], dtype=float)


def bipolar_montage(eeg: np.ndarray, names: list[str], pairs: list[str] = BIOT_16_MONTAGE) -> np.ndarray:
    """Derive bipolar channels from monopolar recordings (legacy T3/T4/T5/T6 mapped to T7/T8/P7/P8)."""
    up = {LEGACY_NAMES.get(n.upper().replace("EEG ", "").strip(), n.upper().replace("EEG ", "").strip()): i for i, n in enumerate(names)}
    rows = []
    for p in pairs:
        a, b = p.split("-")
        if a not in up or b not in up:
            raise KeyError(f"montage {p} not derivable from {sorted(up)}")
        rows.append(eeg[up[a]] - eeg[up[b]])
    return np.vstack(rows)


class BIOTFrozenEncoder(Encoder):
    name = "biot_frozen"

    def __init__(self, checkpoint_path: str, in_channels: int = 16):
        try:
            import torch  # noqa: F401
        except ImportError as e:
            raise RuntimeError("torch not installed; BIOT encoder not run") from e
        raise NotImplementedError("BIOT integration audited but not executed tonight; see RESULTS.md")
